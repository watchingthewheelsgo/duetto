"""Ticker mapping service - CIK to Ticker conversion."""

import asyncio
import json
from pathlib import Path
from typing import Optional

import aiohttp
from loguru import logger


# SEC company tickers JSON URL
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"


class TickerMapper:
    """Map SEC CIK to stock ticker symbols."""

    def __init__(self, cache_dir: Optional[Path] = None):
        self._cache_dir = cache_dir or Path.home() / ".duetto" / "cache"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_file = self._cache_dir / "company_tickers.json"

        self._cik_to_ticker: dict[str, str] = {}
        self._ticker_to_cik: dict[str, str] = {}
        self._cik_to_name: dict[str, str] = {}
        self._loaded = False

    async def load(self, force_refresh: bool = False) -> None:
        """Load ticker data from cache or SEC."""
        if self._loaded and not force_refresh:
            return

        # Try loading from cache first
        if not force_refresh and self._cache_file.exists():
            try:
                await self._load_from_cache()
                logger.info(f"Loaded {len(self._cik_to_ticker)} tickers from cache")
                self._loaded = True
                return
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")

        # Fetch from SEC
        try:
            await self._fetch_from_sec()
        except Exception as e:
            logger.warning(f"Failed to fetch tickers from SEC: {e}")
            
        self._loaded = True

    async def _load_from_cache(self) -> None:
        """Load ticker data from cache file."""
        with open(self._cache_file) as f:
            data = json.load(f)

        # Format: {"0": {"cik_str": "320193", "ticker": "AAPL", "title": "Apple Inc"}}
        for entry in data.values():
            cik = entry["cik_str"]
            ticker = entry["ticker"]
            name = entry["title"]

            # Pad CIK to 10 digits for SEC URLs
            padded_cik = str(cik).zfill(10)

            self._cik_to_ticker[padded_cik] = ticker
            self._cik_to_ticker[cik] = ticker  # Also store unpadded
            self._ticker_to_cik[ticker.upper()] = cik
            self._cik_to_name[padded_cik] = name
            self._cik_to_name[cik] = name

    async def _fetch_from_sec(self) -> None:
        """Fetch ticker data from SEC."""
        headers = {"User-Agent": "Duetto/1.0 (your-email@example.com)"}

        async with aiohttp.ClientSession() as session:
            async with session.get(SEC_TICKERS_URL, headers=headers, ssl=False) as response:
                if response.status != 200:
                    raise Exception(f"Failed to fetch tickers: HTTP {response.status}")

                content = await response.text()

        # Save to cache
        self._cache_file.write_text(content)

        # Parse and load
        data = json.loads(content)
        for entry in data.values():
            cik = entry["cik_str"]
            ticker = entry["ticker"]
            name = entry["title"]

            padded_cik = str(cik).zfill(10)

            self._cik_to_ticker[padded_cik] = ticker
            self._cik_to_ticker[cik] = ticker
            self._ticker_to_cik[ticker.upper()] = cik
            self._cik_to_name[padded_cik] = name
            self._cik_to_name[cik] = name

        logger.info(f"Loaded {len(self._cik_to_ticker)} tickers from SEC")

    def cik_to_ticker(self, cik: str) -> Optional[str]:
        """Convert CIK to ticker symbol."""
        # Handle both padded and unpadded CIK
        padded = cik.zfill(10)
        return self._cik_to_ticker.get(padded) or self._cik_to_ticker.get(cik)

    def ticker_to_cik(self, ticker: str) -> Optional[str]:
        """Convert ticker symbol to CIK."""
        return self._ticker_to_cik.get(ticker.upper())

    def cik_to_name(self, cik: str) -> Optional[str]:
        """Convert CIK to company name."""
        padded = cik.zfill(10)
        return self._cik_to_name.get(padded) or self._cik_to_name.get(cik)

    def lookup_by_name(self, name: str) -> Optional[tuple[str, str]]:
        """Look up ticker and CIK by company name (exact match)."""
        name_lower = name.lower()
        for cik, company_name in self._cik_to_name.items():
            if company_name.lower() == name_lower:
                ticker = self._cik_to_ticker.get(cik)
                if ticker:
                    return ticker, cik
        return None

    def search_by_name(self, name: str, limit: int = 5) -> list[tuple[str, str, str]]:
        """Search for company by partial name."""
        name_lower = name.lower()
        results = []

        for cik, company_name in self._cik_to_name.items():
            if name_lower in company_name.lower():
                ticker = self._cik_to_ticker.get(cik)
                if ticker:
                    results.append((ticker, cik, company_name))
                    if len(results) >= limit:
                        break

        return results


    def ticker_to_name(self, ticker: str) -> Optional[str]:
        """Convert ticker symbol to company name."""
        cik = self.ticker_to_cik(ticker.upper())
        if cik:
            return self.cik_to_name(cik)
        return None

# Global singleton
_ticker_mapper: Optional[TickerMapper] = None


async def get_ticker_mapper() -> TickerMapper:
    """Get or create the global TickerMapper instance."""
    global _ticker_mapper
    if _ticker_mapper is None:
        _ticker_mapper = TickerMapper()
        await _ticker_mapper.load()
    return _ticker_mapper

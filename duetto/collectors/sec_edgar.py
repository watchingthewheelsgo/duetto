"""SEC EDGAR data collector for real-time filings."""

import asyncio
import hashlib
import re
from datetime import datetime
from typing import AsyncIterator, Optional

import aiohttp
import feedparser
from bs4 import BeautifulSoup
from loguru import logger

from duetto.config import settings
from duetto.config import settings
from duetto.schemas import Alert, AlertType, AlertPriority
from duetto.utils import LRUCache, get_ticker_mapper
from .base import BaseCollector


# SEC EDGAR RSS feeds
SEC_FEEDS = {
    "8-K": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&company=&dateb=&owner=include&count=100&output=atom",
    "S-3": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=S-3&company=&dateb=&owner=include&count=100&output=atom",
    "4": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4&company=&dateb=&owner=include&count=100&output=atom",
}

# Keywords for high-priority 8-K events
HIGH_PRIORITY_KEYWORDS = [
    "merger", "acquisition", "acquire", "buyout", "tender offer",
    "definitive agreement", "fda approval", "fda clearance",
    "bankruptcy", "chapter 11", "chapter 7",
]

MEDIUM_PRIORITY_KEYWORDS = [
    "offering", "placement", "securities", "registration",
    "partnership", "license", "contract", "agreement",
]


class SECEdgarCollector(BaseCollector):
    """Collector for SEC EDGAR filings via RSS feeds."""

    def __init__(self):
        self._running = False
        self._seen_ids = LRUCache[str](capacity=10000)
        self._session: Optional[aiohttp.ClientSession] = None
        self._ticker_mapper = None  # Will be loaded in start()
        self._ticker_cache: dict[str, Optional[str]] = {}  # CIK -> ticker cache

    async def start(self) -> None:
        """Start the collector."""
        headers = {"User-Agent": settings.sec_user_agent}
        self._session = aiohttp.ClientSession(headers=headers)
        self._running = True

        # Load ticker mapper
        if self._ticker_mapper is None:
            self._ticker_mapper = await get_ticker_mapper()

        logger.info("SEC EDGAR collector started")

    async def stop(self) -> None:
        """Stop the collector."""
        self._running = False
        if self._session:
            await self._session.close()
        logger.info("SEC EDGAR collector stopped")

    async def collect(self) -> AsyncIterator[Alert]:
        """Collect alerts from SEC EDGAR RSS feeds."""
        if not self._session:
            await self.start()

        for form_type, feed_url in SEC_FEEDS.items():
            try:
                async for alert in self._fetch_feed(form_type, feed_url):
                    yield alert
            except Exception as e:
                logger.error(f"Error fetching {form_type} feed: {e}")

            # Rate limiting
            await asyncio.sleep(settings.sec_rate_limit)

    async def _fetch_feed(self, form_type: str, feed_url: str) -> AsyncIterator[Alert]:
        """Fetch and parse a single RSS feed."""
        if not self._session:
            return

        try:
            async with self._session.get(feed_url) as response:
                if response.status != 200:
                    logger.warning(f"Failed to fetch {form_type} feed: HTTP {response.status}")
                    return

                content = await response.text()
                
                # Run feedparser in a separate thread to avoid blocking the event loop
                loop = asyncio.get_running_loop()
                feed = await loop.run_in_executor(None, feedparser.parse, content)

                for entry in feed.entries:
                    alert_id = self._generate_id(entry)

                    # Skip already seen entries using LRU Cache
                    if not self._seen_ids.add(alert_id):
                        continue

                    alert = self._parse_entry(form_type, entry, alert_id)
                    if alert:
                        yield alert

        except Exception as e:
            logger.exception(f"Exception during {form_type} feed fetch/parse")

    def _generate_id(self, entry: dict) -> str:
        """Generate unique ID for an entry."""
        unique_str = f"{entry.get('id', '')}{entry.get('title', '')}"
        return hashlib.md5(unique_str.encode()).hexdigest()[:16]

    def _parse_entry(self, form_type: str, entry: dict, alert_id: str) -> Optional[Alert]:
        """Parse RSS entry into Alert."""
        try:
            title = entry.get("title", "")
            summary = entry.get("summary", "")
            link = entry.get("link", "")

            # Extract company name and ticker from title
            # Format: "8-K - Company Name (0001234567) (Filer)"
            company, ticker = self._extract_company_info(title)

            # Determine alert type
            alert_type = self._get_alert_type(form_type)

            # Determine priority based on content
            priority = self._determine_priority(title, summary)

            # Parse timestamp
            timestamp = datetime.utcnow()
            if "updated_parsed" in entry:
                try:
                    timestamp = datetime(*entry.updated_parsed[:6])
                except Exception:
                    logger.warning(f"Could not parse timestamp for entry: {title}")

            return Alert(
                id=alert_id,
                type=alert_type,
                priority=priority,
                ticker=ticker,
                company=company,
                title=f"{form_type}: {company}",
                summary=self._clean_summary(summary),
                url=link,
                source="SEC EDGAR",
                timestamp=timestamp,
                raw_data={"form_type": form_type, "entry": dict(entry)},
            )
        except Exception as e:
            logger.error(f"Error parsing entry {alert_id}: {e}")
            return None

    def _extract_company_info(self, title: str) -> tuple[str, Optional[str]]:
        """Extract company name and ticker from SEC filing title."""
        # Pattern: "8-K - Company Name (CIK) (Filer)"
        cik_match = re.search(r"\((\d+)\)", title)
        name_match = re.search(r"- (.+?) \(\d+\)", title)

        cik = cik_match.group(1) if cik_match else None
        company = name_match.group(1).strip() if name_match else title

        # Try to get ticker from CIK
        ticker = None
        if cik and self._ticker_mapper:
            # Check cache first
            if cik in self._ticker_cache:
                ticker = self._ticker_cache[cik]
            else:
                ticker = self._ticker_mapper.cik_to_ticker(cik)
                self._ticker_cache[cik] = ticker

            # Try to get company name from ticker mapper for consistency
            if ticker:
                mapped_name = self._ticker_mapper.cik_to_name(cik)
                if mapped_name:
                    company = mapped_name

        return company, ticker

    def _get_alert_type(self, form_type: str) -> AlertType:
        """Map SEC form type to AlertType."""
        mapping = {
            "8-K": AlertType.SEC_8K,
            "S-3": AlertType.SEC_S3,
            "4": AlertType.SEC_FORM4,
        }
        return mapping.get(form_type, AlertType.SEC_8K)

    def _determine_priority(self, title: str, summary: str) -> AlertPriority:
        """Determine alert priority based on content."""
        text = f"{title} {summary}".lower()

        for keyword in HIGH_PRIORITY_KEYWORDS:
            if keyword in text:
                return AlertPriority.HIGH

        for keyword in MEDIUM_PRIORITY_KEYWORDS:
            if keyword in text:
                return AlertPriority.MEDIUM

        return AlertPriority.LOW

    def _clean_summary(self, summary: str) -> str:
        """Clean HTML from summary."""
        if not summary:
            return ""
        try:
            soup = BeautifulSoup(summary, "lxml")
            text = soup.get_text(separator=" ", strip=True)
            return text[:500] if len(text) > 500 else text
        except Exception:
            return summary[:500]

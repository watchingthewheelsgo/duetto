"""FDA data collector for drug approvals and PDUFA dates."""

import asyncio
import hashlib
from datetime import datetime
from typing import AsyncIterator, Optional

import aiohttp
from bs4 import BeautifulSoup
from loguru import logger

from duetto.config import settings
from duetto.models import Alert, AlertType, AlertPriority
from duetto.utils import LRUCache
from .base import BaseCollector


# FDA data sources
# We will construct yearly URLs dynamically, e.g. https://www.fda.gov/drugs/novel-drug-approvals-fda/novel-drug-approvals-2025
FDA_BASE_URL = "https://www.fda.gov/drugs/novel-drug-approvals-fda/novel-drug-approvals"


class FDACollector(BaseCollector):
    """Collector for FDA drug approvals and events."""

    def __init__(self):
        self._running = False
        self._seen_ids = LRUCache[str](capacity=10000)
        self._session: Optional[aiohttp.ClientSession] = None

    async def start(self) -> None:
        """Start the collector."""
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; Duetto/1.0; +https://github.com/duetto)"
        }
        self._session = aiohttp.ClientSession(headers=headers)
        self._running = True
        logger.info("FDA collector started")

    async def stop(self) -> None:
        """Stop the collector."""
        self._running = False
        if self._session:
            await self._session.close()
        logger.info("FDA collector stopped")

    async def collect(self) -> AsyncIterator[Alert]:
        """Collect alerts from FDA sources."""
        if not self._session:
            await self.start()

        # Collect from FDA approvals page
        try:
            async for alert in self._fetch_approvals():
                yield alert
        except Exception as e:
            logger.error(f"Error fetching FDA approvals: {e}")

    async def _fetch_approvals(self) -> AsyncIterator[Alert]:
        """Fetch recent FDA drug approvals."""
        if not self._session:
            return

        # Try current year first, then previous year if needed (e.g. early Jan)
        current_year = datetime.now().year
        years_to_check = [current_year, current_year - 1]

        for year in years_to_check:
            url = f"{FDA_BASE_URL}-{year}"
            try:
                async with self._session.get(url) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to fetch FDA approvals for {year}: HTTP {response.status}")
                        continue

                    html = await response.text()
                    soup = BeautifulSoup(html, "lxml")

                    # Find the approvals table
                    # The table might be nested in a div
                    table = soup.find("table")
                    if not table:
                        logger.warning(f"FDA approvals table not found on {year} page.")
                        continue

                    rows = table.find_all("tr")[1:]  # Skip header

                    count = 0
                    for row in rows[:20]:  # Only process recent entries
                        cells = row.find_all("td")
                        if len(cells) < 4:
                            continue

                        alert = self._parse_approval_row(cells, url)
                        # Pass url to parse_row to use as base for relative links
                        if alert and self._seen_ids.add(alert.id):
                            yield alert
                            count += 1
                    
                    if count > 0:
                        # If we found data for the current year, we might not need to check previous year
                        # unless we want to be very thorough. For now, let's stop if we found data.
                        break

            except Exception as e:
                logger.error(f"Error parsing FDA approvals for {year}: {e}")

    def _parse_approval_row(self, cells, base_url: str) -> Optional[Alert]:
        """Parse a row from FDA approvals table."""
        try:
            drug_name = cells[0].get_text(strip=True)
            active_ingredient = cells[1].get_text(strip=True) if len(cells) > 1 else ""
            approval_date = cells[2].get_text(strip=True) if len(cells) > 2 else ""
            company = cells[3].get_text(strip=True) if len(cells) > 3 else "Unknown"

            # Generate unique ID
            alert_id = hashlib.md5(f"{drug_name}{approval_date}".encode()).hexdigest()[:16]

            # Find link if available
            link = cells[0].find("a")
            if link and link.get("href"):
                url = link['href']
                if url.startswith("/"):
                    url = f"https://www.fda.gov{url}"
            else:
                url = base_url

            return Alert(
                id=alert_id,
                type=AlertType.FDA_APPROVAL,
                priority=AlertPriority.HIGH,
                ticker=None,  # Would need mapping database
                company=company,
                title=f"FDA Approval: {drug_name}",
                summary=f"{drug_name} ({active_ingredient}) approved on {approval_date}. Company: {company}",
                url=url,
                source="FDA",
                timestamp=datetime.utcnow(),
                raw_data={
                    "drug_name": drug_name,
                    "active_ingredient": active_ingredient,
                    "approval_date": approval_date,
                    "company": company,
                },
            )
        except Exception as e:
            logger.error(f"Error parsing FDA row: {e}")
            return None

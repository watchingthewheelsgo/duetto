"""SEC EDGAR data collector for real-time filings."""

import asyncio
import hashlib
import re
from datetime import datetime
from typing import AsyncIterator, Optional

import aiohttp
import feedparser
from bs4 import BeautifulSoup

from duetto.config import settings
from duetto.models import Alert, AlertType, AlertPriority
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
        self._seen_ids: set[str] = set()
        self._session: Optional[aiohttp.ClientSession] = None

    async def start(self) -> None:
        """Start the collector."""
        headers = {"User-Agent": settings.sec_user_agent}
        self._session = aiohttp.ClientSession(headers=headers)
        self._running = True

    async def stop(self) -> None:
        """Stop the collector."""
        self._running = False
        if self._session:
            await self._session.close()

    async def collect(self) -> AsyncIterator[Alert]:
        """Collect alerts from SEC EDGAR RSS feeds."""
        if not self._session:
            await self.start()

        for form_type, feed_url in SEC_FEEDS.items():
            try:
                async for alert in self._fetch_feed(form_type, feed_url):
                    yield alert
            except Exception as e:
                print(f"Error fetching {form_type} feed: {e}")

            # Rate limiting
            await asyncio.sleep(settings.sec_rate_limit)

    async def _fetch_feed(self, form_type: str, feed_url: str) -> AsyncIterator[Alert]:
        """Fetch and parse a single RSS feed."""
        async with self._session.get(feed_url) as response:
            if response.status != 200:
                return

            content = await response.text()
            feed = feedparser.parse(content)

            for entry in feed.entries:
                alert_id = self._generate_id(entry)

                # Skip already seen entries
                if alert_id in self._seen_ids:
                    continue

                self._seen_ids.add(alert_id)

                # Keep seen_ids from growing too large
                if len(self._seen_ids) > 10000:
                    self._seen_ids = set(list(self._seen_ids)[-5000:])

                alert = self._parse_entry(form_type, entry, alert_id)
                if alert:
                    yield alert

    def _generate_id(self, entry: dict) -> str:
        """Generate unique ID for an entry."""
        unique_str = f"{entry.get('id', '')}{entry.get('title', '')}"
        return hashlib.md5(unique_str.encode()).hexdigest()[:16]

    def _parse_entry(self, form_type: str, entry: dict, alert_id: str) -> Optional[Alert]:
        """Parse RSS entry into Alert."""
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
                pass

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

    def _extract_company_info(self, title: str) -> tuple[str, Optional[str]]:
        """Extract company name from SEC filing title."""
        # Pattern: "8-K - Company Name (CIK) (Filer)"
        match = re.search(r"- (.+?) \(\d+\)", title)
        company = match.group(1).strip() if match else title

        # Try to find ticker (not always in SEC data)
        ticker = None
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
        soup = BeautifulSoup(summary, "lxml")
        text = soup.get_text(separator=" ", strip=True)
        return text[:500] if len(text) > 500 else text

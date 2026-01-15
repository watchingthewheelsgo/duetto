"""Core alert engine that orchestrates data collection and delivery."""

import asyncio
from typing import Optional

from duetto.collectors import SECEdgarCollector, FDACollector
from duetto.filters import AlertFilter
from duetto.models import Alert, AlertPriority
from duetto.config import settings
from .websocket_manager import WebSocketManager


class AlertEngine:
    """Main engine for collecting, filtering, and delivering alerts."""

    def __init__(self, ws_manager: WebSocketManager):
        self.ws_manager = ws_manager
        self.filter = AlertFilter(min_priority=AlertPriority.LOW)

        # Initialize collectors
        self._sec_collector = SECEdgarCollector()
        self._fda_collector = FDACollector()

        self._running = False
        self._recent_alerts: list[Alert] = []
        self._max_recent = 100

    async def start(self) -> None:
        """Start the alert engine."""
        self._running = True
        await self._sec_collector.start()
        await self._fda_collector.start()
        print("Alert engine started")

    async def stop(self) -> None:
        """Stop the alert engine."""
        self._running = False
        await self._sec_collector.stop()
        await self._fda_collector.stop()
        print("Alert engine stopped")

    async def run(self) -> None:
        """Main loop for collecting and processing alerts."""
        await self.start()

        try:
            while self._running:
                # Collect from SEC EDGAR
                await self._collect_sec()

                # Collect from FDA (less frequently)
                if settings.monitor_fda:
                    await self._collect_fda()

                # Wait before next poll
                await asyncio.sleep(settings.sec_poll_interval)

        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()

    async def _collect_sec(self) -> None:
        """Collect alerts from SEC EDGAR."""
        try:
            async for alert in self._sec_collector.collect():
                await self._process_alert(alert)
        except Exception as e:
            print(f"SEC collection error: {e}")

    async def _collect_fda(self) -> None:
        """Collect alerts from FDA."""
        try:
            async for alert in self._fda_collector.collect():
                await self._process_alert(alert)
        except Exception as e:
            print(f"FDA collection error: {e}")

    async def _process_alert(self, alert: Alert) -> None:
        """Process and deliver a single alert."""
        # Enhance with classification
        alert = self.filter.enhance_alert(alert)

        # Check if passes filter
        if not self.filter.should_pass(alert):
            return

        # Store in recent alerts
        self._recent_alerts.insert(0, alert)
        if len(self._recent_alerts) > self._max_recent:
            self._recent_alerts = self._recent_alerts[:self._max_recent]

        # Broadcast to connected clients
        await self.ws_manager.broadcast(alert)
        print(f"[{alert.priority.value.upper()}] {alert.title}")

    def get_recent_alerts(self, limit: int = 50) -> list[Alert]:
        """Get recent alerts."""
        return self._recent_alerts[:limit]

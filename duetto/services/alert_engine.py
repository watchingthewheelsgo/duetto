"""Core alert engine that orchestrates data collection and delivery."""

import asyncio
from typing import Optional

from loguru import logger

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
        logger.info("Alert engine started")

    async def stop(self) -> None:
        """Stop the alert engine."""
        self._running = False
        await self._sec_collector.stop()
        await self._fda_collector.stop()
        logger.info("Alert engine stopped")

    async def run(self) -> None:
        """Main loop for collecting and processing alerts."""
        await self.start()

        try:
            # Create concurrent tasks for different collectors
            tasks = [self._run_sec_loop()]
            
            if settings.monitor_fda:
                tasks.append(self._run_fda_loop())
                
            await asyncio.gather(*tasks)

        except asyncio.CancelledError:
            logger.info("Alert engine run loop cancelled")
        except Exception as e:
            logger.exception("Unexpected error in alert engine")
        finally:
            await self.stop()

    async def _run_sec_loop(self) -> None:
        """Dedicated loop for SEC collection."""
        logger.info(f"Starting SEC collection loop (interval: {settings.sec_poll_interval}s)")
        while self._running:
            try:
                await self._collect_sec()
            except Exception as e:
                logger.error(f"Error in SEC loop: {e}")
            
            await asyncio.sleep(settings.sec_poll_interval)

    async def _run_fda_loop(self) -> None:
        """Dedicated loop for FDA collection."""
        logger.info(f"Starting FDA collection loop (interval: {settings.fda_poll_interval}s)")
        while self._running:
            try:
                await self._collect_fda()
            except Exception as e:
                logger.error(f"Error in FDA loop: {e}")
            
            # Use FDA specific poll interval
            await asyncio.sleep(settings.fda_poll_interval)

    async def _collect_sec(self) -> None:
        """Collect alerts from SEC EDGAR."""
        try:
            async for alert in self._sec_collector.collect():
                await self._process_alert(alert)
        except Exception as e:
            logger.error(f"SEC collection error: {e}")

    async def _collect_fda(self) -> None:
        """Collect alerts from FDA."""
        try:
            async for alert in self._fda_collector.collect():
                await self._process_alert(alert)
        except Exception as e:
            logger.error(f"FDA collection error: {e}")

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
        
        # Log high priority alerts
        log_msg = f"[{alert.priority.value.upper()}] {alert.title}"
        if alert.priority == AlertPriority.HIGH:
            logger.success(log_msg)
        else:
            logger.info(log_msg)

    def get_recent_alerts(self, limit: int = 50) -> list[Alert]:
        """Get recent alerts."""
        return self._recent_alerts[:limit]

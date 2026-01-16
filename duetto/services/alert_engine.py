"""Core alert engine that orchestrates data collection and delivery."""

import asyncio
from typing import Optional

from loguru import logger

from duetto.collectors import SECEdgarCollector, FDACollector
from duetto.filters import AlertFilter
from duetto.models import Alert, AlertPriority
from duetto.config import settings
from duetto.services.feishu import FeishuService
from duetto.services.notifications import (
    Notifier,
    MultiNotifier,
    TelegramNotifier,
    EmailNotifier,
    WebhookNotifier,
    RuleBasedProvider,
    OpenAIProvider,
    AnthropicProvider,
)
from .websocket_manager import WebSocketManager


class AlertEngine:
    """Main engine for collecting, filtering, and delivering alerts."""

    def __init__(self, ws_manager: WebSocketManager):
        self.ws_manager = ws_manager
        self.filter = AlertFilter(min_priority=AlertPriority.LOW)

        # Initialize collectors
        self._sec_collector = SECEdgarCollector()
        self._fda_collector = FDACollector()
        self._feishu_service = FeishuService()

        # Initialize AI provider
        self._ai_provider = self._create_ai_provider()

        # Initialize notifier
        self._notifier = self._create_notifier()

        self._running = False
        self._recent_alerts: list[Alert] = []
        self._max_recent = 100

    def _create_ai_provider(self):
        """Create AI provider based on settings."""
        provider_type = settings.ai_provider.lower()

        if provider_type == "openai" and settings.openai_api_key:
            return OpenAIProvider(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
                model=settings.openai_model,
            )
        elif provider_type == "anthropic" and settings.anthropic_api_key:
            return AnthropicProvider(
                api_key=settings.anthropic_api_key,
                model=settings.anthropic_model,
            )
        else:
            # Default to rule-based (no API required)
            return RuleBasedProvider()

    def _create_notifier(self) -> Optional[Notifier]:
        """Create notifier based on settings."""
        notifiers = []

        # Telegram
        if settings.telegram_bot_token and settings.telegram_chat_id:
            notifiers.append(
                TelegramNotifier(
                    bot_token=settings.telegram_bot_token,
                    chat_id=settings.telegram_chat_id,
                    with_ai=settings.enable_ai_in_notifications,
                    ai_provider=self._ai_provider,
                )
            )
            logger.info("Telegram notifier initialized")

        # Email
        if settings.smtp_host and settings.email_to:
            to_emails = [e.strip() for e in settings.email_to.split(",")]
            notifiers.append(
                EmailNotifier(
                    smtp_host=settings.smtp_host,
                    smtp_port=settings.smtp_port,
                    username=settings.smtp_username,
                    password=settings.smtp_password,
                    from_email=settings.email_from or settings.smtp_username,
                    to_emails=to_emails,
                    with_ai=settings.enable_ai_in_notifications,
                    ai_provider=self._ai_provider,
                )
            )
            logger.info("Email notifier initialized")

        # Webhook
        if settings.webhook_url:
            notifiers.append(
                WebhookNotifier(
                    webhook_url=settings.webhook_url,
                    format=settings.webhook_format,
                )
            )
            logger.info(f"{settings.webhook_format.capitalize()} webhook notifier initialized")

        if notifiers:
            return MultiNotifier(notifiers)

        logger.info("No external notifiers configured")
        return None

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
        if self._feishu_service:
            await self._feishu_service.stop()
        
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

        # Broadcast to connected WebSocket clients
        await self.ws_manager.broadcast(alert)

        # Send to external notifiers (Telegram, Email, etc.)
        if self._notifier and self._should_notify(alert):
            # Get AI suggestion if enabled
            ai_suggestion = None
            if settings.enable_ai_in_notifications and self._ai_provider:
                try:
                    ai_suggestion = await self._ai_provider.analyze(alert)
                except Exception as e:
                    logger.warning(f"AI analysis failed: {e}")

            await self._notifier.send(alert, ai_suggestion)

        # Send to Feishu (High Priority or FDA)
        if alert.priority == AlertPriority.HIGH or "FDA" in alert.source:
             asyncio.create_task(self._feishu_service.send_alert(alert))

        # Log high priority alerts
        log_msg = f"[{alert.priority.value.upper()}] {alert.title}"
        if alert.priority == AlertPriority.HIGH:
            logger.success(log_msg)
        else:
            logger.info(log_msg)

    def _should_notify(self, alert: Alert) -> bool:
        """Check if alert should be sent to external notifiers."""
        min_priority = settings.notify_min_priority.lower()
        priority_order = [AlertPriority.LOW, AlertPriority.MEDIUM, AlertPriority.HIGH]

        alert_level = priority_order.index(alert.priority)
        min_level = priority_order.index(
            AlertPriority.HIGH if min_priority == "high"
            else AlertPriority.MEDIUM if min_priority == "medium"
            else AlertPriority.LOW
        )

        return alert_level >= min_level

    def get_recent_alerts(self, limit: int = 50) -> list[Alert]:
        """Get recent alerts."""
        return self._recent_alerts[:limit]

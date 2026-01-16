"""Notification services for delivering alerts to various channels."""

import asyncio
from abc import ABC, abstractmethod
from typing import Optional

import aiohttp
from loguru import logger

from duetto.models import Alert
from .template import AlertTemplate


class Notifier(ABC):
    """Base class for notification services."""

    @abstractmethod
    async def send(self, alert: Alert, ai_suggestion: Optional[str] = None) -> bool:
        """Send an alert notification."""
        pass


class TelegramNotifier(Notifier):
    """Send alerts to Telegram channel or chat."""

    API_BASE = "https://api.telegram.org/bot{token}/"

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        with_ai: bool = False,
        ai_provider: Optional["AIProvider"] = None,
    ):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.with_ai = with_ai
        self.ai_provider = ai_provider
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def send(self, alert: Alert, ai_suggestion: Optional[str] = None) -> bool:
        """Send alert to Telegram."""
        try:
            # Get AI suggestion if enabled
            if self.with_ai and self.ai_provider and not ai_suggestion:
                ai_suggestion = await self.ai_provider.analyze(alert)

            # Format message
            message = AlertTemplate.format_telegram(alert, self.with_ai, ai_suggestion)

            # Send to Telegram
            session = await self._get_session()
            url = self.API_BASE.format(token=self.bot_token) + "sendMessage"

            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "Markdown",
                "disable_web_page_preview": False,
            }

            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    logger.info(f"Sent alert to Telegram: {alert.title}")
                    return True
                else:
                    error = await response.text()
                    logger.error(f"Telegram error: {error}")
                    return False

        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")
            return False

    async def test_connection(self) -> bool:
        """Test Telegram connection."""
        try:
            session = await self._get_session()
            url = self.API_BASE.format(token=self.bot_token) + "getMe"

            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Connected to Telegram bot: @{data.get('result', {}).get('username')}")
                    return True
                return False
        except Exception as e:
            logger.error(f"Telegram connection test failed: {e}")
            return False


class EmailNotifier(Notifier):
    """Send alerts via email."""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
        from_email: str,
        to_emails: list[str],
        with_ai: bool = False,
        ai_provider: Optional["AIProvider"] = None,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_email = from_email
        self.to_emails = to_emails
        self.with_ai = with_ai
        self.ai_provider = ai_provider

    async def send(self, alert: Alert, ai_suggestion: Optional[str] = None) -> bool:
        """Send alert via email."""
        try:
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText

            # Get AI suggestion if enabled
            if self.with_ai and self.ai_provider and not ai_suggestion:
                ai_suggestion = await self.ai_provider.analyze(alert)

            # Format email
            html_content = AlertTemplate.format_email(alert, self.with_ai, ai_suggestion)

            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"[{alert.priority.upper()}] {alert.title}"
            msg["From"] = self.from_email
            msg["To"] = ", ".join(self.to_emails)

            msg.attach(MIMEText(html_content, "html"))

            # Send in thread pool to avoid blocking
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, self._send_smtp, msg)

            if result:
                logger.info(f"Sent email alert: {alert.title}")
            return result

        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
            return False

    def _send_smtp(self, msg) -> bool:
        """Send email via SMTP (runs in thread pool)."""
        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            return True
        except Exception as e:
            logger.error(f"SMTP error: {e}")
            return False


class WebhookNotifier(Notifier):
    """Send alerts to generic webhook (Discord, Slack, custom)."""

    def __init__(
        self,
        webhook_url: str,
        format: str = "discord",  # discord, slack, json
    ):
        self.webhook_url = webhook_url
        self.format = format
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def send(self, alert: Alert, ai_suggestion: Optional[str] = None) -> bool:
        """Send alert to webhook."""
        try:
            session = await self._get_session()

            if self.format == "discord":
                payload = AlertTemplate.format_discord(alert, False, ai_suggestion)
                headers = {"Content-Type": "application/json"}
            elif self.format == "slack":
                payload = AlertTemplate.format_slack(alert, False, ai_suggestion)
                headers = {"Content-Type": "application/json"}
            else:  # json
                payload = alert.model_dump()
                headers = {"Content-Type": "application/json"}

            async with session.post(self.webhook_url, data=payload, headers=headers) as response:
                if response.status in (200, 204):
                    logger.info(f"Sent webhook alert: {alert.title}")
                    return True
                else:
                    logger.error(f"Webhook error: HTTP {response.status}")
                    return False

        except Exception as e:
            logger.error(f"Failed to send webhook notification: {e}")
            return False


class MultiNotifier(Notifier):
    """Send alerts to multiple notifiers."""

    def __init__(self, notifiers: list[Notifier]):
        self.notifiers = notifiers

    async def send(self, alert: Alert, ai_suggestion: Optional[str] = None) -> bool:
        """Send alert to all configured notifiers."""
        results = await asyncio.gather(
            *[n.send(alert, ai_suggestion) for n in self.notifiers],
            return_exceptions=True,
        )

        success_count = sum(1 for r in results if r is True)
        logger.info(f"Sent alert to {success_count}/{len(self.notifiers)} notifiers")

        return success_count > 0

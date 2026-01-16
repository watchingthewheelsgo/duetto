"""Feishu (Lark) notification service."""

from typing import Any, Optional

import aiohttp
from loguru import logger

from duetto.config import settings
from duetto.models import Alert, AlertPriority


class FeishuService:
    """Service for sending notifications to Feishu/Lark."""

    def __init__(self):
        self._webhook_url = settings.feishu_webhook_url
        self._session: Optional[aiohttp.ClientSession] = None

    async def start(self) -> None:
        """Start the service."""
        if not self._webhook_url:
            return
        
        self._session = aiohttp.ClientSession()
        logger.info("Feishu notification service started")

    async def stop(self) -> None:
        """Stop the service."""
        if self._session:
            await self._session.close()
            logger.info("Feishu notification service stopped")

    async def send_alert(self, alert: Alert) -> None:
        """Send an alert to Feishu."""
        if not self._webhook_url:
            return
            
        if not self._session:
            await self.start()

        try:
            payload = self._build_card_payload(alert)
            async with self._session.post(self._webhook_url, json=payload) as response:
                if response.status != 200:
                    resp_text = await response.text()
                    logger.error(f"Failed to send Feishu notification: HTTP {response.status} - {resp_text}")
                else:
                    logger.debug(f"Sent Feishu notification for {alert.id}")
        except Exception as e:
            logger.error(f"Error sending Feishu notification: {e}")

    def _build_card_payload(self, alert: Alert) -> dict[str, Any]:
        """Build Feishu interactive card payload."""
        # Determine color based on priority
        color = "blue"
        if alert.priority == AlertPriority.HIGH:
            color = "red"
        elif alert.priority == AlertPriority.MEDIUM:
            color = "orange"

        # Format timestamp
        time_str = alert.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")

        return {
            "msg_type": "interactive",
            "card": {
                "config": {
                    "wide_screen_mode": True
                },
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": alert.title
                    },
                    "template": color
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": f"**Company**: {alert.company}\n**Ticker**: {alert.ticker or 'N/A'}\n**Time**: {time_str}"
                        }
                    },
                    {
                        "tag": "hr"
                    },
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": alert.summary
                        }
                    },
                    {
                        "tag": "action",
                        "actions": [
                            {
                                "tag": "button",
                                "text": {
                                    "tag": "plain_text",
                                    "content": "View Source"
                                },
                                "url": alert.url,
                                "type": "primary"
                            }
                        ]
                    }
                ]
            }
        }

"""Feishu notifier."""

import aiohttp
from loguru import logger
from duetto.config import settings
from duetto.schemas import NotificationTemplate, NotificationLevel
from .base import BaseNotifier

class FeishuNotifier(BaseNotifier):
    """Sends notifications to Feishu/Lark via Webhook."""
    
    async def send(self, template: NotificationTemplate) -> bool:
        webhook = settings.feishu.webhook_url
        if not webhook:
            return False
            
        card = self._build_card(template)
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook, json=card) as response:
                    if response.status != 200:
                        logger.error(f"Feishu send failed: {response.status}")
                        return False
            return True
        except Exception as e:
            logger.error(f"Feishu send error: {e}")
            return False

    def _build_card(self, t: NotificationTemplate) -> dict:
        # Map Level to Color
        color_map = {
            NotificationLevel.INFO: "blue",
            NotificationLevel.SUCCESS: "green",
            NotificationLevel.WARNING: "orange",
            NotificationLevel.ERROR: "red",
            NotificationLevel.CRITICAL: "carmine" # or red
        }
        color = color_map.get(t.level, "blue")
        
        elements = [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": t.body
                }
            }
        ]
        
        # Add Fields
        if t.fields:
            field_lines = [f"**{f['key']}**: {f['value']}" for f in t.fields]
            elements.append({
                 "tag": "div",
                 "text": {
                     "tag": "lark_md",
                     "content": "\n".join(field_lines)
                 }
            })

        # Add Action Button
        if t.link:
            elements.append({
                "tag": "action",
                "actions": [{
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": t.link_text or "View source"},
                    "url": t.link,
                    "type": "primary"
                }]
            })

        return {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": t.title},
                    "template": color
                },
                "elements": elements
            }
        }

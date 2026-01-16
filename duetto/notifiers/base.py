"""Base notifier interface."""

from abc import ABC, abstractmethod
from typing import Optional, Any
from duetto.schemas import Alert, NotificationTemplate, NotificationLevel

class BaseNotifier(ABC):
    """Interface for sending notifications."""
    
    @abstractmethod
    async def send(self, template: NotificationTemplate) -> bool:
        """Send a formatted notification."""
        pass
        
    def create_template(self, alert: Alert) -> NotificationTemplate:
        """Convert Alert to standard Template."""
        level = NotificationLevel.INFO
        if alert.priority == "high": level = NotificationLevel.CRITICAL
        elif alert.priority == "medium": level = NotificationLevel.WARNING
        
        fields = []
        if alert.ticker:
             fields.append({"key": "Ticker", "value": alert.ticker})
        if alert.source:
             fields.append({"key": "Source", "value": alert.source})
             
        # Add AI summary if present
        ai_text = ""
        if alert.enrichment_data and "ai_summary" in alert.enrichment_data:
            ai_text = f"\n\n🤖 Analysis: {alert.enrichment_data['ai_summary']}"
        
        return NotificationTemplate(
            title=alert.title,
            body=f"{alert.summary}{ai_text}",
            level=level,
            link=alert.url,
            fields=fields
        )

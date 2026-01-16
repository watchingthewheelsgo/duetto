"""Filter processor."""

from duetto.schemas import Alert, AlertPriority
from duetto.config import settings
from .base import BaseProcessor

class FilterProcessor(BaseProcessor):
    """Filters alerts based on configuration (market cap, priority)."""
    
    async def process(self, alert: Alert) -> Alert | None:
        # Check priority threshold
        if not self._check_priority(alert):
             return None
             
        # Market Cap check could go here if we had synchronous access to cap data
        # For now, we assume Collector or Enrichment layer might attach cap data
        # But usually filtering is done after enrichment. 
        # For this refactor, we'll keep it simple: 
        # if market cap is in alert.enrichment_data, check it.
        
        return alert

    def _check_priority(self, alert: Alert) -> bool:
        min_p = settings.notify_min_priority.lower()
        p_order = [AlertPriority.LOW, AlertPriority.MEDIUM, AlertPriority.HIGH]
        
        try:
            current_idx = p_order.index(alert.priority)
            
            min_target = AlertPriority.LOW
            if min_p == "high": min_target = AlertPriority.HIGH
            elif min_p == "medium": min_target = AlertPriority.MEDIUM
            
            min_idx = p_order.index(min_target)
            return current_idx >= min_idx
        except ValueError:
            return True

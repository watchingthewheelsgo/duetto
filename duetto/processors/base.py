"""Base processor interface."""

from abc import ABC, abstractmethod
from typing import List, Optional
from duetto.schemas import Alert

class BaseProcessor(ABC):
    """Interface for processing alerts (filtering, enrichment, etc)."""
    
    @abstractmethod
    async def process(self, alert: Alert) -> Optional[Alert]:
        """
        Process an alert. 
        Return modified alert, or None to drop it.
        """
        pass

class ProcessorPipeline:
    """Chains multiple processors together."""
    
    def __init__(self, processors: List[BaseProcessor]):
        self.processors = processors
        
    async def run(self, alert: Alert) -> Optional[Alert]:
        current_alert = alert
        for p in self.processors:
            if not current_alert:
                return None
            current_alert = await p.process(current_alert)
        return current_alert

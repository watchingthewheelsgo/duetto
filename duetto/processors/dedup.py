"""Deduplication processor."""

from duetto.utils.cache import LRUCache # Assuming existing utility
from duetto.schemas import Alert
from .base import BaseProcessor

class DedupProcessor(BaseProcessor):
    """Drops alerts that have been seen recently."""
    
    def __init__(self, capacity: int = 1000):
        # We can implement a simple in-memory set if LRUCache is not compatible, 
        # but let's try to reuse or build simple one.
        self.seen = set() # Simple set for ID tracking in MVP
        self.max_size = capacity
        
    async def process(self, alert: Alert) -> Alert | None:
        if alert.id in self.seen:
            return None
            
        self.seen.add(alert.id)
        if len(self.seen) > self.max_size:
            self.seen.pop() # Remove arbitrary item (set is unordered, strictly not LRU but prevents leak)
            
        return alert

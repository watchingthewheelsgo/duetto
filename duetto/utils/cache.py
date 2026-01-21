"""LRU Cache implementation."""

from typing import TypeVar, Generic, OrderedDict

T = TypeVar('T')

class LRUCache(Generic[T]):
    """Simple LRU (Least Recently Used) cache."""

    def __init__(self, capacity: int = 1000):
        self.capacity = capacity
        # We store keys to order, can use OrderedDict for O(1) ops
        self._cache = OrderedDict()

    def add(self, item: T) -> bool:
        """
        Add item. Returns True if the item was added (not already present),
        False if it already existed.
        """
        if item in self._cache:
            self._cache.move_to_end(item)
            return False
            
        self._cache[item] = True
        if len(self._cache) > self.capacity:
            self._cache.popitem(last=False)
        return True

    def __contains__(self, item: T) -> bool:
        """Check if item is in cache."""
        return item in self._cache

    def __len__(self) -> int:
        """Return cache size."""
        return len(self._cache)

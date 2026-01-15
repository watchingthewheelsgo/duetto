"""Utility classes and functions."""

from collections import deque
from typing import Generic, TypeVar, Hashable

T = TypeVar("T", bound=Hashable)


class LRUCache(Generic[T]):
    """
    A simple LRU cache for tracking seen IDs.
    Uses a set for O(1) lookups and a deque for maintaining order.
    """

    def __init__(self, capacity: int = 10000):
        self.capacity = capacity
        self._set: set[T] = set()
        self._queue: deque[T] = deque()

    def add(self, item: T) -> bool:
        """
        Add an item to the cache.
        Returns True if the item was new and added, False if it was already present.
        """
        if item in self._set:
            return False

        self._set.add(item)
        self._queue.append(item)

        # Evict if over capacity
        if len(self._set) > self.capacity:
            removed = self._queue.popleft()
            self._set.remove(removed)
            
        return True

    def __contains__(self, item: T) -> bool:
        return item in self._set

    def __len__(self) -> int:
        return len(self._set)

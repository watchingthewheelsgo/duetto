"""LRU Cache implementation."""


class LRUCache:
    """Simple LRU (Least Recently Used) cache."""

    def __init__(self, capacity: int = 1000):
        self.capacity = capacity
        self.cache: dict = {}

    def add(self, key: str) -> bool:
        """
        Add a key to the cache.
        Returns True if the key was added (not already present),
        False if it already existed.
        """
        if key in self.cache:
            # Move to end (most recently used)
            self.cache.pop(key)
            self.cache[key] = True
            return False

        self.cache[key] = True

        # Evict oldest if over capacity
        if len(self.cache) > self.capacity:
            # Remove oldest (first item)
            oldest = next(iter(self.cache))
            del self.cache[oldest]

        return True

    def __contains__(self, key: str) -> bool:
        """Check if key is in cache."""
        return key in self.cache

    def __len__(self) -> int:
        """Return cache size."""
        return len(self.cache)

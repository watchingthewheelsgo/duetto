"""Base collector interface."""

from abc import ABC, abstractmethod
from typing import AsyncIterator

from duetto.models import Alert


class BaseCollector(ABC):
    """Base class for data collectors."""

    @abstractmethod
    async def start(self) -> None:
        """Start the collector."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop the collector."""
        pass

    @abstractmethod
    async def collect(self) -> AsyncIterator[Alert]:
        """Collect alerts from the source."""
        pass

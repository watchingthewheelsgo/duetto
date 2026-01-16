"""Test processors."""

import pytest
import asyncio
from datetime import datetime
from duetto.schemas import Alert, AlertType, AlertPriority
from duetto.processors.dedup import DedupProcessor
from duetto.processors.filter import FilterProcessor

@pytest.fixture
def sample_alert():
    return Alert(
        id="test_1",
        type=AlertType.STOCK_MOV,
        priority=AlertPriority.HIGH,
        company="Test Corp",
        title="Test Alert",
        summary="Summary",
        url="http://test.com",
        source="Test"
    )

@pytest.mark.asyncio
async def test_dedup_processor(sample_alert):
    processor = DedupProcessor()
    
    # First pass should pass
    result1 = await processor.process(sample_alert)
    assert result1 is not None
    assert result1.id == "test_1"
    
    # Second pass should be dropped
    result2 = await processor.process(sample_alert)
    assert result2 is None

@pytest.mark.asyncio
async def test_filter_map_cap():
    # To implement once filter has logic
    pass

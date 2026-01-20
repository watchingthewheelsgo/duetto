"""Main Orchestration Engine."""

import asyncio
from typing import List
from loguru import logger

from duetto.config import settings
from duetto.schemas import Alert
from duetto.collectors.base import BaseCollector
# Import collectors - assuming we fix their imports later
# For now we use dummy imports or assume existing ones adapted
from duetto.collectors.sec_edgar import SECEdgarCollector 
# from duetto.collectors.tradingview import TradingViewCollector # Will fix next

from duetto.processors.base import ProcessorPipeline
from duetto.processors.dedup import DedupProcessor
from duetto.processors.filter import FilterProcessor
# from duetto.processors.ai_enricher import AIEnricher # Future

from duetto.notifiers.base import BaseNotifier
from duetto.notifiers.feishu import FeishuNotifier

from duetto.server import WebSocketManager

class DuettoEngine:
    def __init__(self, ws_manager: WebSocketManager = None):
        self.running = False
        self.ws_manager = ws_manager
        
        # 1. Collectors
        self.collectors: List[BaseCollector] = []
        if settings.sec.monitor_8k: # Simple check
             self.collectors.append(SECEdgarCollector())
        # self.collectors.append(TradingViewCollector())
        
        # 2. Processors
        self.pipeline = ProcessorPipeline([
            DedupProcessor(),
            FilterProcessor(),
            # AIEnricher()
        ])
        
        # 3. Notifiers
        self.notifiers: List[BaseNotifier] = []
        if settings.feishu.webhook_url:
            self.notifiers.append(FeishuNotifier())
            
    async def start(self):
        self.running = True
        logger.info("Duetto Engine Starting...")
        
        # Start all collectors
        # Note: Collectors usually run in background or we poll them. 
        # The existing pattern was asynchronous `collect()` generation.
        # We will dispatch a task for each collector.
        tasks = [asyncio.create_task(self._run_collector(c)) for c in self.collectors]
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            pass
            
    async def stop(self):
        self.running = False
        for c in self.collectors:
            await c.stop()
        logger.info("Duetto Engine Stopped")

    async def _run_collector(self, collector: BaseCollector):
        try:
            # We assume collect() is an async generator
            async for alert in collector.collect():
                if not self.running: break
                await self._process_and_notify(alert)
        except Exception as e:
            logger.error(f"Collector error {collector}: {e}")

    async def _process_and_notify(self, alert: Alert):
        # 1. Process
        processed_alert = await self.pipeline.run(alert)
        if not processed_alert:
            return # Dropped by filter or dedup
            
        # 2. Broadcast to UI
        if self.ws_manager:
            await self.ws_manager.broadcast(processed_alert)
            
        # 3. Notify External
        for notifier in self.notifiers:
            try:
                template = notifier.create_template(processed_alert)
                await notifier.send(template)
            except Exception as e:
                logger.error(f"Notifier error {notifier}: {e}")

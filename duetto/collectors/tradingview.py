"""TradingView data collector."""

import asyncio
import json
import random
import re
import string
from datetime import datetime
from typing import AsyncIterator, Optional, List

import aiohttp
from loguru import logger

from duetto.config import settings
from duetto.schemas import Alert, AlertType, AlertPriority
from duetto.utils import get_ticker_mapper
from .base import BaseCollector


class TradingViewCollector(BaseCollector):
    """Collector for real-time stock data from TradingView."""

    def __init__(self):
        self._running = False
        self._session: Optional[aiohttp.ClientSession] = None
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._ticker_mapper = None
        self._queue = asyncio.Queue()
        self._quote_session = self._generate_session()
        self._subscribed_symbols = set()

    def _generate_session(self) -> str:
        random_string = ''.join(random.choice(string.ascii_lowercase) for _ in range(12))
        return "qs_" + random_string

    def _create_message(self, func: str, param_list: List) -> str:
        message = json.dumps({"m": func, "p": param_list}, separators=(',', ':'))
        return "~m~{}~m~{}".format(len(message), message)

    async def start(self) -> None:
        """Start the collector."""
        self._running = True
        
        # Load ticker mapper
        if self._ticker_mapper is None:
            self._ticker_mapper = await get_ticker_mapper()

        logger.info("TradingView collector starting...")
        asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        """Stop the collector."""
        self._running = False
        if self._ws:
            await self._ws.close()
        if self._session:
            await self._session.close()
        logger.info("TradingView collector stopped")

    async def collect(self) -> AsyncIterator[Alert]:
        """Collect alerts from TradingView."""
        if not self._running:
            await self.start()

        while self._running:
            while not self._queue.empty():
                yield await self._queue.get()
            
            await asyncio.sleep(0.5)

    async def _run_loop(self):
        """Main WebSocket loop."""
        headers = {
            'Origin': 'https://data.tradingview.com',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Pragma': 'no-cache',
            'Cache-Control': 'no-cache'
        }

        while self._running:
            try:
                if not self._session:
                    self._session = aiohttp.ClientSession()

                async with self._session.ws_connect(
                    'wss://data.tradingview.com/socket.io/websocket',
                    headers=headers,
                    ssl=False 
                ) as ws:
                    self._ws = ws
                    logger.info("Connected to TradingView WebSocket")

                    # Handshake
                    start_session = self._quote_session

                    # Handshake mimicking official client
                    await self._send_message("set_auth_token", ["unauthorized_user_token"])
                    
                    chart_session = "cs_" + ''.join(random.choice(string.ascii_lowercase) for _ in range(12))
                    await self._send_message("chart_create_session", [chart_session, ""])
                    
                    await self._send_message("quote_create_session", [start_session])
                    await self._send_message(
                        "quote_set_fields", 
                        [start_session, "ch", "chp", "lp", "description", "currency_code", "rchp", "rtc"]
                    )

                    # Subscribe symbols
                    for symbol in settings.tv.symbols:
                        await self._send_message(
                            "quote_add_symbols", 
                            [self._quote_session, symbol, {"flags": ['force_permission']}]
                        )
                        self._subscribed_symbols.add(symbol)
                        logger.info(f"Subscribed to {symbol}")

                    async for msg in ws:
                        if not self._running:
                            break
                            
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            await self._handle_message(msg.data)
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            logger.error(f"WebSocket error: {ws.exception()}")
                            break
            
            except Exception as e:
                logger.error(f"Error in TradingView loop: {e}")
                
            if self._running:
                logger.info("Reconnecting in 5 seconds...")
                await asyncio.sleep(5)

    async def _send_message(self, func: str, args: List):
        if self._ws:
            msg = self._create_message(func, args)
            await self._ws.send_str(msg)

    async def _handle_message(self, message: str):
        # Keep-alive
        if "~m~" not in message:
             # TV sometimes sends raw numbers as pings? Or we might need to respond.
             # If message handles like heartbeat
             if re.match(r"^~h~\d+$", message):
                 await self._ws.send_str(message)
                 return

        # Parse framed messages
        # Regex to match ~m~length~m~JSON
        parts = re.split(r'~m~\d+~m~', message)
        
        for part in parts:
            if not part.strip():
                continue
                
            try:
                # Handle connection setup messages/heartbeats that are not json
                if part.startswith("~h~"):
                    await self._ws.send_str(part)
                    continue

                data = json.loads(part)
                method = data.get("m")
                params = data.get("p")

                if method == "qsd" and params:
                     # Quote Session Data
                     # params: [session_id, {symbol: {data}}]
                     if len(params) > 1 and isinstance(params[1], dict):
                         symbol_data_map = params[1] # e.g. {"v": {...}, "n": "NASDAQ:AAPL"} ???
                         # Actually structure is often: {"n": "NASDAQ:AAPL", "v": {"ch": ..., "lp": ...}}
                         # BUT qsd usually sends: [session, { "s": "ok", "n": "NASDAQ:AAPL", "v": {...} }]
                         
                         val = symbol_data_map
                         symbol = val.get("n") # Symbol name
                         values = val.get("v") # Values dict

                         if symbol and values:
                             await self._process_quote(symbol, values)

            except json.JSONDecodeError:
                pass
            except Exception as e:
                logger.error(f"Error parsing message part: {e}")

    async def _process_quote(self, symbol: str, values: dict):
        # Analyze price change
        price = values.get("lp") or values.get("price")
        change_pct = values.get("chp") or values.get("ch_p") # change percent
        
        if change_pct is not None:
             threshold = settings.tv.threshold_pct
             if abs(change_pct) >= threshold:
                 await self._create_alert(symbol, values, change_pct)

    async def _create_alert(self, symbol: str, data: dict, change_pct: float) -> None:
        """Create and enqueue an alert."""
        ticker = symbol.split(":")[-1] if ":" in symbol else symbol
        
        # Get company name
        company = ticker # Fallback
        if self._ticker_mapper:
            mapped = self._ticker_mapper.ticker_to_name(ticker)
            if mapped:
                company = mapped
        
        direction = "UP" if change_pct > 0 else "DOWN"
        priority = AlertPriority.HIGH if abs(change_pct) > 20 else AlertPriority.MEDIUM
        price = data.get("lp") or data.get("price", "N/A")
        
        alert = Alert(
            id=f"tv_{ticker}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{abs(int(change_pct*100))}",
            type=AlertType.STOCK_MOVEMENT,
            priority=priority,
            ticker=ticker,
            company=company,
            title=f"Stock Move: {ticker} {direction} {change_pct:.2f}%",
            summary=f"{company} ({ticker}) moved {change_pct:.2f}%. Price: {price}",
            url=f"https://www.tradingview.com/symbols/{symbol}/",
            source="TradingView",
            timestamp=datetime.utcnow(),
            raw_data=data
        )
        await self._queue.put(alert)

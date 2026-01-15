"""WebSocket connection manager for real-time alert delivery."""

import asyncio
import json
from typing import Optional

from fastapi import WebSocket

from duetto.models import Alert


class WebSocketManager:
    """Manage WebSocket connections for real-time alerts."""

    def __init__(self):
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            self._connections.append(websocket)
        print(f"Client connected. Total connections: {len(self._connections)}")

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        async with self._lock:
            if websocket in self._connections:
                self._connections.remove(websocket)
        print(f"Client disconnected. Total connections: {len(self._connections)}")

    async def broadcast(self, alert: Alert) -> None:
        """Broadcast an alert to all connected clients."""
        if not self._connections:
            return

        message = json.dumps(alert.model_dump(), default=str)

        async with self._lock:
            dead_connections = []

            for connection in self._connections:
                try:
                    await connection.send_text(message)
                except Exception:
                    dead_connections.append(connection)

            # Clean up dead connections
            for conn in dead_connections:
                if conn in self._connections:
                    self._connections.remove(conn)

    async def send_to_client(self, websocket: WebSocket, alert: Alert) -> bool:
        """Send an alert to a specific client."""
        try:
            message = json.dumps(alert.model_dump(), default=str)
            await websocket.send_text(message)
            return True
        except Exception:
            return False

    @property
    def connection_count(self) -> int:
        """Get current number of connections."""
        return len(self._connections)

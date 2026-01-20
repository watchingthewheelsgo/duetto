"""Server and API handling."""

from typing import List, Any
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
from loguru import logger
from duetto.schemas import Alert

class WebSocketManager:
    """Manages WebSocket connections for frontend clients."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"Client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: Any):
        """Broadcast message to all connected clients."""
        # Convert Pydantic model to dict/json if needed
        data = message.model_dump() if isinstance(message, Alert) else message
        
        # Prune closed connections
        for connection in self.active_connections[:]:
            if connection.client_state == WebSocketState.DISCONNECTED:
                self.disconnect(connection)
                continue
                
            try:
                await connection.send_json(data)
            except Exception as e:
                logger.warning(f"Failed to send to client: {e}")
                self.disconnect(connection)

app = FastAPI(title="Duetto API")
ws_manager = WebSocketManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)

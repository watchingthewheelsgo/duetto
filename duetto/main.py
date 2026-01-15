"""Duetto - Real-time market alerts server."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from duetto.services import AlertEngine, WebSocketManager
from duetto.config import settings


# Global instances
ws_manager = WebSocketManager()
alert_engine = AlertEngine(ws_manager)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Start alert engine in background
    task = asyncio.create_task(alert_engine.run())
    yield
    # Shutdown
    alert_engine._running = False
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Duetto",
    description="Free KairAlert alternative - Real-time market alerts",
    version="0.1.0",
    lifespan=lifespan,
)

# Mount static files
static_path = Path(__file__).parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


@app.get("/")
async def index():
    """Serve the main page."""
    return FileResponse(static_path / "index.html")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time alerts."""
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive, handle any client messages
            data = await websocket.receive_text()
            # Could handle client commands here
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)


@app.get("/api/alerts")
async def get_alerts(limit: int = 50):
    """Get recent alerts."""
    alerts = alert_engine.get_recent_alerts(limit)
    return [alert.model_dump() for alert in alerts]


@app.get("/api/status")
async def get_status():
    """Get system status."""
    return {
        "status": "running" if alert_engine._running else "stopped",
        "connections": ws_manager.connection_count,
        "alerts_count": len(alert_engine._recent_alerts),
    }


def main():
    """Run the server."""
    import uvicorn
    from loguru import logger

    logger.info("Starting Duetto Server...")
    logger.info(f"Server available at http://{settings.host}:{settings.port}")
    logger.info(f"WebSocket available at ws://{settings.host}:{settings.port}/ws")
    logger.info(f"Poll Interval: {settings.sec_poll_interval}s")

    uvicorn.run(
        "duetto.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    main()

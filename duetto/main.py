"""Application entry point."""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
import uvicorn
from loguru import logger

from duetto.config import settings
from duetto.server import app, ws_manager
from duetto.engine import DuettoEngine

# Global engine instance
engine = DuettoEngine(ws_manager=ws_manager)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown events."""
    # Startup
    logger.info("Starting Duetto services...")
    asyncio.create_task(engine.start())
    yield
    # Shutdown
    logger.info("Shutting down Duetto services...")
    await engine.stop()

# Assign lifespan to app
app.router.lifespan_context = lifespan

def main():
    """Run the application."""
    uvicorn.run(
        "duetto.main:app",
        host=settings.server.host,
        port=settings.server.port,
        reload=True
    )

if __name__ == "__main__":
    main()

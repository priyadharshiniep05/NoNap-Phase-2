"""FastAPI application entrypoint for NoNap real-time backend."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.app.core.config import get_settings
from server.app.db.auth_db import create_auth_tables, get_auth_session_factory
from server.app.db.ops_db import create_ops_tables, get_ops_session_factory
from server.app.db.sync import reconcile
from server.app.routers import (
    health_router,
    auth_router,
    driver_router,
    fleet_router,
    monitor_router,
    detect_router,
    alerts_router,
    ws_router,
    dev_router,
)
from server.app.capture.webcam_worker import webcam_worker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("nonap.server")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize dual SQLite databases and run reconciliation."""
    logger.info("Starting NoNap Backend Server...")

    # 1. Ensure databases and tables exist
    create_auth_tables()
    create_ops_tables()
    logger.info("Auth and Ops databases initialized.")

    # 2. Run initial cross-database reconciliation
    auth_factory = get_auth_session_factory()
    ops_factory = get_ops_session_factory()
    auth_db = auth_factory()
    ops_db = ops_factory()
    try:
        summary = reconcile(auth_db, ops_db)
        logger.info(f"Cross-DB reconciliation complete: {summary}")
    except Exception as e:
        logger.error(f"Reconciliation error on startup: {e}")
    finally:
        auth_db.close()
        ops_db.close()

    yield

    # Shutdown logic
    logger.info("Stopping NoNap Webcam Worker if running...")
    webcam_worker.stop()
    logger.info("NoNap Backend Server shutdown complete.")


settings = get_settings()

app = FastAPI(
    title="NoNap Driver Drowsiness Detection API",
    description="Real-time dual-database API supporting driver monitoring and fleet management.",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS configuration for Flutter mobile & web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all API routers
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(driver_router)
app.include_router(fleet_router)
app.include_router(monitor_router)
app.include_router(detect_router)
app.include_router(alerts_router)
app.include_router(ws_router)
app.include_router(dev_router)


@app.get("/")
def root():
    return {
        "app": "NoNap Real-Time Drowsiness Detection System",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/health",
        "status": "online",
    }

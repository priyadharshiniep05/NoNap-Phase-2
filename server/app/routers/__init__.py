"""Routers package for NoNap."""

from server.app.routers.health import router as health_router
from server.app.routers.auth import router as auth_router
from server.app.routers.driver import router as driver_router
from server.app.routers.fleet import router as fleet_router
from server.app.routers.monitor import router as monitor_router
from server.app.routers.detect import router as detect_router
from server.app.routers.alerts import router as alerts_router
from server.app.routers.ws import router as ws_router
from server.app.routers.dev import router as dev_router

__all__ = [
    "health_router",
    "auth_router",
    "driver_router",
    "fleet_router",
    "monitor_router",
    "detect_router",
    "alerts_router",
    "ws_router",
    "dev_router",
]

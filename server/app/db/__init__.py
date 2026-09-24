"""Database module for NoNap: dual-database architecture (auth_db & ops_db)."""

from server.app.db.auth_db import get_auth_session, create_auth_tables, get_auth_engine
from server.app.db.ops_db import get_ops_session, create_ops_tables, get_ops_engine
from server.app.db.models_auth import User, Fleet, FleetDriver
from server.app.db.models_ops import Threshold, AlertLog, SessionStat

__all__ = [
    "get_auth_session",
    "create_auth_tables",
    "get_auth_engine",
    "get_ops_session",
    "create_ops_tables",
    "get_ops_engine",
    "User",
    "Fleet",
    "FleetDriver",
    "Threshold",
    "AlertLog",
    "SessionStat",
]

"""Ops database (DB2) engine, session, and table creation."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from server.app.core.config import get_settings
from server.app.db.models_ops import OpsBase

_ops_engine = None
_OpsSessionLocal = None


def get_ops_engine():
    global _ops_engine
    if _ops_engine is None:
        settings = get_settings()
        url = settings.OPS_DB_URL
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        _ops_engine = create_engine(url, connect_args=connect_args, echo=False)
    return _ops_engine


def get_ops_session_factory():
    global _OpsSessionLocal
    if _OpsSessionLocal is None:
        _OpsSessionLocal = sessionmaker(bind=get_ops_engine(), autocommit=False, autoflush=False)
    return _OpsSessionLocal


def get_ops_session():
    """FastAPI dependency yielding an ops DB session."""
    factory = get_ops_session_factory()
    db = factory()
    try:
        yield db
    finally:
        db.close()


def create_ops_tables():
    """Create all ops database tables."""
    OpsBase.metadata.create_all(bind=get_ops_engine())

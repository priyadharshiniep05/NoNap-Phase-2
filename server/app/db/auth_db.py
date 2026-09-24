"""Auth database (DB1) engine, session, and table creation."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from server.app.core.config import get_settings
from server.app.db.models_auth import AuthBase

_auth_engine = None
_AuthSessionLocal = None


def get_auth_engine():
    global _auth_engine
    if _auth_engine is None:
        settings = get_settings()
        url = settings.AUTH_DB_URL
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        _auth_engine = create_engine(url, connect_args=connect_args, echo=False)
    return _auth_engine


def get_auth_session_factory():
    global _AuthSessionLocal
    if _AuthSessionLocal is None:
        _AuthSessionLocal = sessionmaker(bind=get_auth_engine(), autocommit=False, autoflush=False)
    return _AuthSessionLocal


def get_auth_session():
    """FastAPI dependency yielding an auth DB session."""
    factory = get_auth_session_factory()
    db = factory()
    try:
        yield db
    finally:
        db.close()


def create_auth_tables():
    """Create all auth database tables."""
    AuthBase.metadata.create_all(bind=get_auth_engine())

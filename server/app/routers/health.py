"""Health check router validating both auth and ops database connections."""

import time
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from server.app.db.auth_db import get_auth_session
from server.app.db.ops_db import get_ops_session
from server.app.core.config import get_settings

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check(
    auth_db: Session = Depends(get_auth_session),
    ops_db: Session = Depends(get_ops_session),
):
    """Check system health, ensuring both SQLite databases are accessible."""
    auth_status = "error"
    ops_status = "error"

    try:
        auth_db.execute(text("SELECT 1"))
        auth_status = "ok"
    except Exception as e:
        auth_status = f"error: {e}"

    try:
        ops_db.execute(text("SELECT 1"))
        ops_status = "ok"
    except Exception as e:
        ops_status = f"error: {e}"

    settings = get_settings()

    all_ok = auth_status == "ok" and ops_status == "ok"

    return {
        "status": "ok" if all_ok else "degraded",
        "service": "nonap-backend",
        "databases": {
            "auth_db": auth_status,
            "ops_db": ops_status,
        },
        "backend_model": settings.DETECTOR_BACKEND,
        "video_source": settings.VIDEO_SOURCE,
        "timestamp": time.time(),
    }

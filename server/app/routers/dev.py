"""Development simulation router (only active when DEBUG=True)."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from server.app.core.config import get_settings
from server.app.db.auth_db import get_auth_session
from server.app.db.ops_db import get_ops_session
from server.app.db.models_auth import User, FleetDriver
from server.app.realtime.connection_manager import manager
from server.app.services.alert_service import create_and_broadcast_alert
from server.app.schemas.detection import DevSimulateRequest

router = APIRouter(prefix="/dev", tags=["Development & Testing"])


@router.post("/simulate")
async def simulate_event(
    payload: DevSimulateRequest,
    auth_db: Session = Depends(get_auth_session),
    ops_db: Session = Depends(get_ops_session),
):
    """Inject synthetic drowsiness or safety event for demo and testing purposes."""
    settings = get_settings()
    if not settings.DEBUG:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dev simulation endpoint is disabled in production.",
        )

    driver = auth_db.query(User).filter(User.id == payload.driver_id).first()
    if not driver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver not found in auth_db.",
        )

    fd = auth_db.query(FleetDriver).filter(FleetDriver.driver_id == driver.id).first()
    fleet_id = fd.fleet_id if fd else None

    now = datetime.now(timezone.utc)
    timestamp_hhmm = now.strftime("%H:%M")
    iso_timestamp = now.isoformat()

    metrics = {
        "ear": payload.ear,
        "mar": payload.mar,
        "perclos": payload.perclos,
    }

    if payload.event in ("drowsy", "yawning", "accident"):
        alert = await create_and_broadcast_alert(
            ops_session=ops_db,
            auth_session=auth_db,
            driver_id=payload.driver_id,
            alert_type=payload.event,
            severity=payload.severity,
            confidence=payload.confidence,
            ear=payload.ear,
            mar=payload.mar,
            perclos=payload.perclos,
            source="simulated",
        )
        return {
            "status": "alert_broadcasted",
            "alert_id": alert.id,
            "event": payload.event,
            "driver_name": driver.full_name,
            "timestamp": iso_timestamp,
        }
    else:
        # Telemetry update
        await manager.broadcast_detection(
            driver_id=payload.driver_id,
            driver_name=driver.full_name,
            driver_fleet_id=fleet_id,
            status=payload.event,
            severity="low",
            confidence=payload.confidence,
            metrics=metrics,
            timestamp_hhmm=timestamp_hhmm,
            iso_timestamp=iso_timestamp,
            is_alert=False,
        )
        return {
            "status": "telemetry_broadcasted",
            "event": payload.event,
            "driver_name": driver.full_name,
            "timestamp": iso_timestamp,
        }

"""Driver-only personal dashboard endpoints.

STRICT ACCESS CONTROL: Accessible ONLY by users with role 'driver'.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from server.app.core.deps import require_role, Role
from server.app.db.auth_db import get_auth_session
from server.app.db.ops_db import get_ops_session
from server.app.db.models_auth import User, Fleet, FleetDriver
from server.app.db.models_ops import AlertLog, Threshold
from server.app.db.sync import ensure_user_thresholds
from server.app.realtime.connection_manager import manager
from server.app.core.timezone import ist_wall_now
from server.app.schemas.driver import (
    DriverProfileResponse,
    DriverStatsResponse,
)
from server.app.schemas.ops import (
    AlertLogResponse,
    ThresholdResponse,
    ThresholdUpdateRequest,
)

router = APIRouter(prefix="/driver", tags=["Driver Personal Dashboard"])


@router.get("/profile", response_model=DriverProfileResponse)
def get_driver_profile(
    driver: User = Depends(require_role(Role.driver)),
    auth_db: Session = Depends(get_auth_session),
):
    """Get the driver's own profile and fleet assignment."""
    fd = auth_db.query(FleetDriver).filter(FleetDriver.driver_id == driver.id).first()
    fleet_name = None
    fleet_id = None
    if fd:
        fleet_id = fd.fleet_id
        fleet = auth_db.query(Fleet).filter(Fleet.id == fd.fleet_id).first()
        if fleet:
            fleet_name = fleet.name

    return DriverProfileResponse(
        id=driver.id,
        full_name=driver.full_name,
        email=driver.email,
        role=driver.role,
        fleet_id=fleet_id,
        fleet_name=fleet_name,
        created_at=driver.created_at,
    )


@router.get("/stats", response_model=DriverStatsResponse)
def get_driver_stats(
    driver: User = Depends(require_role(Role.driver)),
    ops_db: Session = Depends(get_ops_session),
):
    """Get personal aggregate alert statistics."""
    total_alerts = ops_db.query(AlertLog).filter(AlertLog.driver_id == driver.id).count()
    drowsy_alerts = ops_db.query(AlertLog).filter(
        AlertLog.driver_id == driver.id, AlertLog.type == "drowsy"
    ).count()
    yawn_alerts = ops_db.query(AlertLog).filter(
        AlertLog.driver_id == driver.id, AlertLog.type == "yawning"
    ).count()
    accident_alerts = ops_db.query(AlertLog).filter(
        AlertLog.driver_id == driver.id, AlertLog.type == "accident"
    ).count()

    # Alerts today (past 24h)
    since = ist_wall_now() - timedelta(hours=24)  # detected_at is IST wall-clock
    alerts_today = ops_db.query(AlertLog).filter(
        AlertLog.driver_id == driver.id,
        AlertLog.detected_at >= since,
    ).count()

    last_alert = ops_db.query(AlertLog).filter(
        AlertLog.driver_id == driver.id
    ).order_by(AlertLog.detected_at.desc()).first()

    live_status = manager.get_latest_status(driver.id)
    current_status = live_status.get("status", "alert") if live_status else "alert"

    return DriverStatsResponse(
        driver_id=driver.id,
        total_alerts=total_alerts,
        drowsy_alerts=drowsy_alerts,
        yawn_alerts=yawn_alerts,
        accident_alerts=accident_alerts,
        alerts_today=alerts_today,
        last_alert_time=last_alert.detected_at if last_alert else None,
        current_status=current_status,
    )


@router.get("/alerts", response_model=List[AlertLogResponse])
def get_driver_alerts(
    limit: int = 50,
    driver: User = Depends(require_role(Role.driver)),
    ops_db: Session = Depends(get_ops_session),
):
    """Get the driver's own personal alert log history."""
    alerts = (
        ops_db.query(AlertLog)
        .filter(AlertLog.driver_id == driver.id)
        .order_by(AlertLog.detected_at.desc())
        .limit(limit)
        .all()
    )

    return [AlertLogResponse.from_row(a, driver.full_name) for a in alerts]


@router.get("/thresholds", response_model=ThresholdResponse)
def get_my_thresholds(
    driver: User = Depends(require_role(Role.driver)),
    ops_db: Session = Depends(get_ops_session),
):
    """Retrieve the driver's personalized detection thresholds."""
    t = ensure_user_thresholds(ops_db, driver.id)
    return ThresholdResponse.model_validate(t)


@router.put("/thresholds", response_model=ThresholdResponse)
def update_my_thresholds(
    payload: ThresholdUpdateRequest,
    driver: User = Depends(require_role(Role.driver)),
    ops_db: Session = Depends(get_ops_session),
):
    """Update driver's personalized detection thresholds."""
    t = ensure_user_thresholds(ops_db, driver.id)

    if payload.ear_threshold is not None:
        t.ear_threshold = payload.ear_threshold
    if payload.mar_threshold is not None:
        t.mar_threshold = payload.mar_threshold
    if payload.perclos_threshold is not None:
        t.perclos_threshold = payload.perclos_threshold
    if payload.eyes_closed_seconds is not None:
        t.eyes_closed_seconds = payload.eyes_closed_seconds
    if payload.alert_cooldown_seconds is not None:
        t.alert_cooldown_seconds = payload.alert_cooldown_seconds

    ops_db.commit()
    ops_db.refresh(t)
    return ThresholdResponse.model_validate(t)


@router.post("/calibrate/start")
def start_driver_calibration(
    duration: float = 10.0,
    driver: User = Depends(require_role(Role.driver)),
):
    """Start a 10-second personalized baseline calibration session."""
    from server.app.services.calibration_service import calibration_service
    session = calibration_service.start_calibration(driver.id, duration_seconds=duration)
    return {
        "status": "calibrating",
        "driver_id": driver.id,
        "duration_seconds": duration,
        "message": "Keep eyes open and mouth relaxed while looking at the camera.",
    }


@router.get("/calibrate/status")
def get_driver_calibration_status(
    driver: User = Depends(require_role(Role.driver)),
):
    """Get current calibration progress, status, and derived thresholds."""
    from server.app.services.calibration_service import calibration_service
    session = calibration_service.get_session(driver.id)
    if not session:
        return {
            "status": "idle",
            "is_calibrating": False,
            "progress": 0.0,
            "remaining_seconds": 0.0,
        }

    return {
        "status": "completed" if session.is_complete else ("calibrating" if session.is_active else "idle"),
        "is_calibrating": session.is_active,
        "is_complete": session.is_complete,
        "progress": round(session.progress, 2),
        "remaining_seconds": round(session.remaining_seconds, 1),
        "samples_collected": len(session.ear_samples),
        "result": session.result,
    }

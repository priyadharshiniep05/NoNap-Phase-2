"""Fleet Manager Dashboard endpoints.

STRICT ACCESS CONTROL: Accessible ONLY by users with role 'fleet_manager'.
Drivers attempting to access these routes receive 403 Forbidden.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from server.app.core.deps import require_role, Role
from server.app.db.auth_db import get_auth_session
from server.app.db.ops_db import get_ops_session
from server.app.db.models_auth import User, Fleet, FleetDriver
from server.app.db.models_ops import AlertLog, Threshold
from server.app.db.sync import ensure_fleet_thresholds
from server.app.realtime.connection_manager import manager
from server.app.schemas.fleet import (
    FleetOverviewResponse,
    FleetDriverSummary,
    FleetCreateRequest,
    FleetDriverAssignRequest,
)
from server.app.schemas.ops import (
    AlertLogResponse,
    ThresholdResponse,
    ThresholdUpdateRequest,
)

router = APIRouter(prefix="/fleet", tags=["Fleet Management Dashboard"])


def _get_manager_fleet(auth_db: Session, manager_id: str) -> Fleet:
    """Find or create a default fleet for this fleet manager."""
    fleet = auth_db.query(Fleet).filter(Fleet.manager_id == manager_id).first()
    if not fleet:
        fleet = Fleet(manager_id=manager_id, name="Primary Fleet")
        auth_db.add(fleet)
        auth_db.commit()
        auth_db.refresh(fleet)
    return fleet


@router.get("/overview", response_model=FleetOverviewResponse)
def get_fleet_overview(
    mgr: User = Depends(require_role(Role.fleet_manager)),
    auth_db: Session = Depends(get_auth_session),
    ops_db: Session = Depends(get_ops_session),
):
    """Aggregate fleet metrics, active drivers, and alert counts."""
    fleet = _get_manager_fleet(auth_db, mgr.id)

    # Get driver relationships
    fleet_drivers = auth_db.query(FleetDriver).filter(FleetDriver.fleet_id == fleet.id).all()
    driver_ids = [fd.driver_id for fd in fleet_drivers]

    users = {
        u.id: u for u in auth_db.query(User).filter(User.id.in_(driver_ids)).all()
    } if driver_ids else {}

    # Query alert metrics past 24h
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    drowsy_today = 0
    yawn_today = 0
    critical_today = 0

    if driver_ids:
        drowsy_today = ops_db.query(AlertLog).filter(
            AlertLog.driver_id.in_(driver_ids),
            AlertLog.type == "drowsy",
            AlertLog.detected_at >= since,
        ).count()
        yawn_today = ops_db.query(AlertLog).filter(
            AlertLog.driver_id.in_(driver_ids),
            AlertLog.type == "yawning",
            AlertLog.detected_at >= since,
        ).count()
        critical_today = ops_db.query(AlertLog).filter(
            AlertLog.driver_id.in_(driver_ids),
            AlertLog.severity.in_(["high", "critical"]),
            AlertLog.detected_at >= since,
        ).count()

    # Build driver summaries
    driver_summaries: List[FleetDriverSummary] = []
    active_count = 0

    for did in driver_ids:
        u = users.get(did)
        if not u:
            continue

        live = manager.get_latest_status(did)
        status_val = live.get("status", "alert") if live else "offline"
        if status_val != "offline":
            active_count += 1

        last_alert = ops_db.query(AlertLog).filter(
            AlertLog.driver_id == did
        ).order_by(AlertLog.detected_at.desc()).first()

        alerts_count = ops_db.query(AlertLog).filter(
            AlertLog.driver_id == did,
            AlertLog.detected_at >= since,
        ).count()

        perclos = live.get("metrics", {}).get("perclos", 0.0) if live else 0.0
        ear = live.get("metrics", {}).get("ear", 0.0) if live else 0.0

        driver_summaries.append(
            FleetDriverSummary(
                driver_id=u.id,
                full_name=u.full_name,
                email=u.email,
                is_active=u.is_active,
                current_status=status_val,
                last_alert_at=last_alert.detected_at if last_alert else None,
                alerts_today=alerts_count,
                perclos=perclos,
                ear=ear,
            )
        )

    return FleetOverviewResponse(
        fleet_id=fleet.id,
        fleet_name=fleet.name,
        total_drivers=len(driver_summaries),
        active_drivers=active_count,
        drowsy_count_today=drowsy_today,
        yawn_count_today=yawn_today,
        critical_alerts_today=critical_today,
        drivers=driver_summaries,
    )


@router.get("/drivers", response_model=List[FleetDriverSummary])
def get_fleet_drivers(
    mgr: User = Depends(require_role(Role.fleet_manager)),
    auth_db: Session = Depends(get_auth_session),
    ops_db: Session = Depends(get_ops_session),
):
    """List all drivers assigned to this manager's fleet."""
    overview = get_fleet_overview(mgr=mgr, auth_db=auth_db, ops_db=ops_db)
    return overview.drivers


@router.get("/drivers/{driver_id}", response_model=FleetDriverSummary)
def get_driver_detail(
    driver_id: str,
    mgr: User = Depends(require_role(Role.fleet_manager)),
    auth_db: Session = Depends(get_auth_session),
    ops_db: Session = Depends(get_ops_session),
):
    """Get single driver status within the fleet."""
    fleet = _get_manager_fleet(auth_db, mgr.id)
    fd = auth_db.query(FleetDriver).filter(
        FleetDriver.fleet_id == fleet.id, FleetDriver.driver_id == driver_id
    ).first()
    if not fd:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver not found in your fleet.",
        )

    u = auth_db.query(User).filter(User.id == driver_id).first()
    if not u:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    since = datetime.now(timezone.utc) - timedelta(hours=24)
    live = manager.get_latest_status(driver_id)
    last_alert = ops_db.query(AlertLog).filter(
        AlertLog.driver_id == driver_id
    ).order_by(AlertLog.detected_at.desc()).first()
    alerts_count = ops_db.query(AlertLog).filter(
        AlertLog.driver_id == driver_id, AlertLog.detected_at >= since
    ).count()

    return FleetDriverSummary(
        driver_id=u.id,
        full_name=u.full_name,
        email=u.email,
        is_active=u.is_active,
        current_status=live.get("status", "alert") if live else "offline",
        last_alert_at=last_alert.detected_at if last_alert else None,
        alerts_today=alerts_count,
        perclos=live.get("metrics", {}).get("perclos", 0.0) if live else 0.0,
        ear=live.get("metrics", {}).get("ear", 0.0) if live else 0.0,
    )


@router.get("/alerts", response_model=List[AlertLogResponse])
def get_fleet_alerts(
    limit: int = 100,
    mgr: User = Depends(require_role(Role.fleet_manager)),
    auth_db: Session = Depends(get_auth_session),
    ops_db: Session = Depends(get_ops_session),
):
    """Retrieve recent alerts for all drivers across the fleet."""
    fleet = _get_manager_fleet(auth_db, mgr.id)
    fleet_drivers = auth_db.query(FleetDriver).filter(FleetDriver.fleet_id == fleet.id).all()
    driver_ids = [fd.driver_id for fd in fleet_drivers]

    if not driver_ids:
        return []

    users = {u.id: u.full_name for u in auth_db.query(User).filter(User.id.in_(driver_ids)).all()}

    alerts = (
        ops_db.query(AlertLog)
        .filter(AlertLog.driver_id.in_(driver_ids))
        .order_by(AlertLog.detected_at.desc())
        .limit(limit)
        .all()
    )

    return [
        AlertLogResponse(
            id=a.id,
            driver_id=a.driver_id,
            driver_name=users.get(a.driver_id, "Driver"),
            fleet_id=a.fleet_id,
            type=a.type,
            severity=a.severity,
            confidence=a.confidence,
            ear=a.ear,
            mar=a.mar,
            perclos=a.perclos,
            source=a.source,
            detected_at=a.detected_at,
            acknowledged=a.acknowledged,
            acknowledged_by=a.acknowledged_by,
        )
        for a in alerts
    ]


@router.get("/thresholds", response_model=ThresholdResponse)
def get_fleet_thresholds(
    mgr: User = Depends(require_role(Role.fleet_manager)),
    auth_db: Session = Depends(get_auth_session),
    ops_db: Session = Depends(get_ops_session),
):
    """Get fleet-scope detection thresholds."""
    fleet = _get_manager_fleet(auth_db, mgr.id)
    t = ensure_fleet_thresholds(ops_db, fleet.id)
    return ThresholdResponse.model_validate(t)


@router.put("/thresholds", response_model=ThresholdResponse)
def update_fleet_thresholds(
    payload: ThresholdUpdateRequest,
    mgr: User = Depends(require_role(Role.fleet_manager)),
    auth_db: Session = Depends(get_auth_session),
    ops_db: Session = Depends(get_ops_session),
):
    """Update fleet-scope detection thresholds."""
    fleet = _get_manager_fleet(auth_db, mgr.id)
    t = ensure_fleet_thresholds(ops_db, fleet.id)

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


@router.post("/assign", status_code=status.HTTP_200_OK)
def assign_driver(
    payload: FleetDriverAssignRequest,
    mgr: User = Depends(require_role(Role.fleet_manager)),
    auth_db: Session = Depends(get_auth_session),
):
    """Assign an existing driver to this fleet."""
    fleet = _get_manager_fleet(auth_db, mgr.id)
    user = auth_db.query(User).filter(User.id == payload.driver_id, User.role == "driver").first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver not found.")

    existing = auth_db.query(FleetDriver).filter(
        FleetDriver.fleet_id == fleet.id, FleetDriver.driver_id == user.id
    ).first()
    if not existing:
        fd = FleetDriver(fleet_id=fleet.id, driver_id=user.id)
        auth_db.add(fd)
        auth_db.commit()

    return {"status": "ok", "message": f"Driver {user.full_name} assigned to {fleet.name}."}

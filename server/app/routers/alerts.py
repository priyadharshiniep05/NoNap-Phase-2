"""Alert lifecycle and accident SOS endpoints."""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from server.app.core.deps import get_current_user
from server.app.db.auth_db import get_auth_session
from server.app.db.ops_db import get_ops_session
from server.app.db.models_auth import User
from server.app.db.models_ops import AlertLog
from server.app.services.alert_service import create_and_broadcast_alert
from server.app.schemas.ops import AlertLogResponse, AlertAcknowledgeRequest

router = APIRouter(prefix="/alerts", tags=["Alerts & Accidents"])


class AccidentAlertRequest(BaseModel):
    driver_id: Optional[str] = None
    confidence: float = 1.0
    details: Optional[str] = "Manual SOS button triggered"


@router.post("/accident", response_model=AlertLogResponse)
async def report_accident_sos(
    payload: AccidentAlertRequest,
    current_user: User = Depends(get_current_user),
    auth_db: Session = Depends(get_auth_session),
    ops_db: Session = Depends(get_ops_session),
):
    """Trigger critical accident/SOS alert."""
    target_driver_id = payload.driver_id or current_user.id

    alert = await create_and_broadcast_alert(
        ops_session=ops_db,
        auth_session=auth_db,
        driver_id=target_driver_id,
        alert_type="accident",
        severity="critical",
        confidence=payload.confidence,
        ear=0.0,
        mar=0.0,
        perclos=1.0,
        source="webcam",
    )

    return AlertLogResponse(
        id=alert.id,
        driver_id=alert.driver_id,
        driver_name=current_user.full_name,
        fleet_id=alert.fleet_id,
        type=alert.type,
        severity=alert.severity,
        confidence=alert.confidence,
        ear=alert.ear,
        mar=alert.mar,
        perclos=alert.perclos,
        source=alert.source,
        detected_at=alert.detected_at,
        acknowledged=alert.acknowledged,
        acknowledged_by=alert.acknowledged_by,
    )


@router.post("/{alert_id}/acknowledge", response_model=AlertLogResponse)
def acknowledge_alert(
    alert_id: str,
    payload: AlertAcknowledgeRequest,
    current_user: User = Depends(get_current_user),
    ops_db: Session = Depends(get_ops_session),
    auth_db: Session = Depends(get_auth_session),
):
    """Acknowledge or clear an alert."""
    alert = ops_db.query(AlertLog).filter(AlertLog.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found.")

    ack_name = payload.acknowledged_by or current_user.full_name
    alert.acknowledged = True
    alert.acknowledged_by = ack_name
    ops_db.commit()
    ops_db.refresh(alert)

    driver = auth_db.query(User).filter(User.id == alert.driver_id).first()
    driver_name = driver.full_name if driver else "Driver"

    return AlertLogResponse(
        id=alert.id,
        driver_id=alert.driver_id,
        driver_name=driver_name,
        fleet_id=alert.fleet_id,
        type=alert.type,
        severity=alert.severity,
        confidence=alert.confidence,
        ear=alert.ear,
        mar=alert.mar,
        perclos=alert.perclos,
        source=alert.source,
        detected_at=alert.detected_at,
        acknowledged=alert.acknowledged,
        acknowledged_by=alert.acknowledged_by,
    )

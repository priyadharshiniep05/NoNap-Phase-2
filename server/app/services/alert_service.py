"""Alert recording, notification, and lifecycle management service."""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from server.app.db.models_ops import AlertLog
from server.app.db.models_auth import User, FleetDriver
from server.app.realtime.connection_manager import manager
from server.app.services.notify_service import send_push_notification
from server.app.services.escalation_service import escalate_accident

logger = logging.getLogger("nonap.alerts")


async def create_and_broadcast_alert(
    ops_session: Session,
    auth_session: Session,
    driver_id: str,
    alert_type: str,  # drowsy, yawning, accident, no_face
    severity: str,  # low, medium, high, critical
    confidence: float,
    ear: float,
    mar: float,
    perclos: float,
    source: str = "webcam",
) -> AlertLog:
    """Persist alert to ops_db and broadcast to WebSocket subscribers."""
    # Find driver name from auth_db
    driver = auth_session.query(User).filter(User.id == driver_id).first()
    driver_name = driver.full_name if driver else "Driver"

    # Find driver fleet_id from auth_db
    fd = auth_session.query(FleetDriver).filter(FleetDriver.driver_id == driver_id).first()
    fleet_id = fd.fleet_id if fd else None

    now = datetime.now(timezone.utc)
    timestamp_hhmm = now.strftime("%H:%M")
    iso_timestamp = now.isoformat()

    # Save to ops_db
    alert = AlertLog(
        driver_id=driver_id,
        fleet_id=fleet_id,
        type=alert_type,
        severity=severity,
        confidence=confidence,
        ear=ear,
        mar=mar,
        perclos=perclos,
        source=source,
        detected_at=now,
        acknowledged=False,
    )
    ops_session.add(alert)
    ops_session.commit()
    ops_session.refresh(alert)

    metrics = {
        "ear": ear,
        "mar": mar,
        "perclos": perclos,
    }

    # Broadcast via WebSocket
    await manager.broadcast_detection(
        driver_id=driver_id,
        driver_name=driver_name,
        driver_fleet_id=fleet_id,
        status=alert_type,
        severity=severity,
        confidence=confidence,
        metrics=metrics,
        timestamp_hhmm=timestamp_hhmm,
        iso_timestamp=iso_timestamp,
        is_alert=True,
    )

    # Push notification stub
    if alert_type == "drowsy":
        title = "Drowsiness Warning"
        body = f"You were drowsy at {timestamp_hhmm}. Pull over safely."
    elif alert_type == "yawning":
        title = "Fatigue Notice"
        body = f"Frequent yawning detected at {timestamp_hhmm}."
    elif alert_type == "accident":
        title = "CRITICAL ACCIDENT ALERT"
        body = f"Accident impact recorded at {timestamp_hhmm}."
    else:
        title = "Alert"
        body = f"Alert at {timestamp_hhmm}"

    await send_push_notification(driver_id=driver_id, title=title, body=body, data={"alert_id": alert.id})

    # Escalation if accident
    if alert_type == "accident" or severity == "critical":
        await escalate_accident(
            driver_id=driver_id,
            fleet_id=fleet_id,
            alert_details={
                "alert_id": alert.id,
                "timestamp": iso_timestamp,
                "ear": ear,
                "mar": mar,
            },
        )

    logger.info(f"Alert created & broadcast: id={alert.id}, type={alert_type}, driver={driver_name}")
    return alert

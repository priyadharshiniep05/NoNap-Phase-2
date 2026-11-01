"""Alert recording, notification, and lifecycle management service."""

import logging
import os
import subprocess
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from server.app.core.timezone import now_ist, format_ist_time, to_ist_iso
from server.app.db.models_ops import AlertLog
from server.app.db.models_auth import User, FleetDriver
from server.app.realtime.connection_manager import manager
from server.app.services.notify_service import send_push_notification
from server.app.services.escalation_service import escalate_accident

logger = logging.getLogger("nonap.alerts")


def play_laptop_alarm() -> None:
    """Play an audible alarm tone on the laptop hardware."""
    # Standard macOS alert sounds
    sound_candidates = [
        "/System/Library/Sounds/Sosumi.aiff",
        "/System/Library/Sounds/Ping.aiff",
        "/System/Library/Sounds/Glass.aiff",
    ]
    for sound in sound_candidates:
        if os.path.exists(sound):
            try:
                subprocess.Popen(
                    ["afplay", sound],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return
            except Exception:
                pass
    # Terminal bell fallback
    print("\a", flush=True)


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
    reason: Optional[str] = None,  # eyes_closed, yawn, perclos
    source: str = "webcam",
) -> AlertLog:
    """Persist alert to ops_db and broadcast to WebSocket subscribers."""
    # Find driver name from auth_db
    driver = auth_session.query(User).filter(User.id == driver_id).first()
    driver_name = driver.full_name if driver else "Driver"

    # Find driver fleet_id from auth_db
    fd = auth_session.query(FleetDriver).filter(FleetDriver.driver_id == driver_id).first()
    fleet_id = fd.fleet_id if fd else None

    # Current timestamp in Asia/Kolkata (IST)
    current_ist = now_ist()
    time_ist_str = format_ist_time(current_ist)
    iso_timestamp = to_ist_iso(current_ist)

    # Trigger audible alarm on laptop when drowsy or accident
    if alert_type in ("drowsy", "accident") or severity in ("high", "critical"):
        play_laptop_alarm()

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
        detected_at=current_ist,
        acknowledged=False,
    )
    ops_session.add(alert)
    ops_session.commit()
    ops_session.refresh(alert)

    metrics = {
        "ear": ear,
        "mar": mar,
        "perclos": perclos,
        "reason": reason or alert_type,
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
        timestamp_hhmm=time_ist_str,
        iso_timestamp=iso_timestamp,
        is_alert=True,
    )

    # Push notification copy with IST timestamp
    if alert_type == "drowsy":
        title = "Drowsiness Warning"
        body = f"You were drowsy at {time_ist_str}."
    elif alert_type == "yawning":
        title = "Fatigue Notice"
        body = f"Frequent yawning detected at {time_ist_str}."
    elif alert_type == "accident":
        title = "CRITICAL ACCIDENT ALERT"
        body = f"Accident impact recorded at {time_ist_str}."
    else:
        title = "Alert"
        body = f"Alert recorded at {time_ist_str}."

    await send_push_notification(driver_id=driver_id, title=title, body=body, data={"alert_id": alert.id})

    # Escalation if accident
    if alert_type == "accident" or severity == "critical":
        await escalate_accident(
            driver_id=driver_id,
            fleet_id=fleet_id,
            alert_details={
                "alert_id": alert.id,
                "timestamp": iso_timestamp,
                "time_ist": time_ist_str,
                "ear": ear,
                "mar": mar,
            },
        )

    logger.info(f"Alert created & broadcast: id={alert.id}, type={alert_type}, reason={reason}, driver={driver_name} at {time_ist_str}")
    return alert

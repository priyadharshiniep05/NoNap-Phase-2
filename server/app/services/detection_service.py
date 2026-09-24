"""Detection pipeline service connecting model inference with database and WebSocket."""

import base64
import logging
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any

import cv2
import numpy as np
from sqlalchemy.orm import Session

# Import model inference engine
try:
    from model.nonap_model.engine import predict as model_predict
    MODEL_AVAILABLE = True
except ImportError:
    try:
        from nonap_model.engine import predict as model_predict
        MODEL_AVAILABLE = True
    except ImportError:
        MODEL_AVAILABLE = False
        model_predict = None

from server.app.db.models_auth import User, FleetDriver
from server.app.db.models_ops import Threshold
from server.app.realtime.connection_manager import manager
from server.app.services.alert_service import create_and_broadcast_alert

logger = logging.getLogger("nonap.detection")


def _get_driver_thresholds(ops_session: Session, driver_id: str, fleet_id: Optional[str]) -> Optional[dict]:
    """Load effective thresholds: driver-specific > fleet-specific > global."""
    # 1. Driver specific
    t = ops_session.query(Threshold).filter(
        Threshold.scope == "user", Threshold.user_id == driver_id
    ).first()
    if t:
        return {
            "ear": t.ear_threshold,
            "mar": t.mar_threshold,
            "perclos": t.perclos_threshold,
            "eyes_closed_seconds": t.eyes_closed_seconds,
            "alert_cooldown_seconds": t.alert_cooldown_seconds,
        }

    # 2. Fleet specific
    if fleet_id:
        t = ops_session.query(Threshold).filter(
            Threshold.scope == "fleet", Threshold.fleet_id == fleet_id
        ).first()
        if t:
            return {
                "ear": t.ear_threshold,
                "mar": t.mar_threshold,
                "perclos": t.perclos_threshold,
                "eyes_closed_seconds": t.eyes_closed_seconds,
                "alert_cooldown_seconds": t.alert_cooldown_seconds,
            }

    # 3. Global
    t = ops_session.query(Threshold).filter(Threshold.scope == "global").first()
    if t:
        return {
            "ear": t.ear_threshold,
            "mar": t.mar_threshold,
            "perclos": t.perclos_threshold,
            "eyes_closed_seconds": t.eyes_closed_seconds,
            "alert_cooldown_seconds": t.alert_cooldown_seconds,
        }
    return None


async def process_frame(
    frame: np.ndarray,
    driver_id: str,
    auth_session: Session,
    ops_session: Session,
    source: str = "webcam",
    broadcast_telemetry: bool = True,
) -> Dict[str, Any]:
    """Run model inference on a single frame, log alerts, and broadcast results."""
    # Get driver info
    driver = auth_session.query(User).filter(User.id == driver_id).first()
    driver_name = driver.full_name if driver else "Driver"
    fd = auth_session.query(FleetDriver).filter(FleetDriver.driver_id == driver_id).first()
    fleet_id = fd.fleet_id if fd else None

    # Get customized thresholds
    thresholds = _get_driver_thresholds(ops_session, driver_id, fleet_id)

    # Run inference
    if MODEL_AVAILABLE and model_predict is not None:
        try:
            pred = model_predict(
                frame=frame,
                driver_id=driver_id,
                custom_thresholds=thresholds,
            )
            result = pred.to_dict()
        except Exception as e:
            logger.error(f"Inference error: {e}")
            result = {
                "driver_id": driver_id,
                "status": "alert",
                "severity": "low",
                "confidence": 0.5,
                "ear": 0.28,
                "mar": 0.15,
                "perclos": 0.05,
                "eyes_closed_seconds": 0.0,
                "alert_triggered": False,
                "alert_type": None,
                "backend": "baseline",
                "timestamp": time.time(),
            }
    else:
        # Fallback dummy prediction if model not loaded
        result = {
            "driver_id": driver_id,
            "status": "alert",
            "severity": "low",
            "confidence": 0.8,
            "ear": 0.28,
            "mar": 0.15,
            "perclos": 0.05,
            "eyes_closed_seconds": 0.0,
            "alert_triggered": False,
            "alert_type": None,
            "backend": "baseline",
            "timestamp": time.time(),
        }

    now = datetime.now(timezone.utc)
    timestamp_hhmm = now.strftime("%H:%M")
    iso_timestamp = now.isoformat()

    metrics = {
        "ear": round(result.get("ear", 0.0), 3),
        "mar": round(result.get("mar", 0.0), 3),
        "perclos": round(result.get("perclos", 0.0), 3),
        "eyes_closed_seconds": round(result.get("eyes_closed_seconds", 0.0), 2),
    }

    # If an alert was triggered by temporal analysis
    if result.get("alert_triggered"):
        alert_type = result.get("alert_type") or result.get("status")
        severity = result.get("severity", "medium")
        confidence = result.get("confidence", 0.9)

        await create_and_broadcast_alert(
            ops_session=ops_session,
            auth_session=auth_session,
            driver_id=driver_id,
            alert_type=alert_type,
            severity=severity,
            confidence=confidence,
            ear=result.get("ear", 0.0),
            mar=result.get("mar", 0.0),
            perclos=result.get("perclos", 0.0),
            source=source,
        )
        result["alert_message"] = (
            f"You were drowsy at {timestamp_hhmm}"
            if alert_type == "drowsy"
            else f"Alert at {timestamp_hhmm}"
        )
    elif broadcast_telemetry:
        # Normal telemetry broadcast
        await manager.broadcast_detection(
            driver_id=driver_id,
            driver_name=driver_name,
            driver_fleet_id=fleet_id,
            status=result.get("status", "alert"),
            severity=result.get("severity", "low"),
            confidence=result.get("confidence", 0.9),
            metrics=metrics,
            timestamp_hhmm=timestamp_hhmm,
            iso_timestamp=iso_timestamp,
            is_alert=False,
        )

    return result


def decode_base64_frame(b64_str: str) -> Optional[np.ndarray]:
    """Decode a base64-encoded JPEG/PNG image to OpenCV BGR numpy array."""
    try:
        if "," in b64_str:
            b64_str = b64_str.split(",", 1)[1]
        img_bytes = base64.b64decode(b64_str)
        nparr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return frame
    except Exception as e:
        logger.error(f"Error decoding base64 frame: {e}")
        return None

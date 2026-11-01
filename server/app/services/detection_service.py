"""Detection pipeline service connecting model inference with database and WebSocket."""

import asyncio
import base64
import logging
import threading
import time
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

from server.app.core.config import get_settings
from server.app.core.timezone import now_ist, format_ist_time, to_ist_iso
from server.app.db.models_ops import Threshold
from server.app.realtime.connection_manager import manager
from server.app.services.alert_levels import Observation
from server.app.services.alerting_service import alerting_service, LEVEL_SEVERITY
from server.app.services.calibration_service import calibration_service
from server.app.services.driver_context import driver_context
from server.app.services.latency_logger import latency_logger, now_ms

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


_inference_lock = threading.Lock()
_last_telemetry_ts: Dict[str, float] = {}


def _infer(frame: np.ndarray, driver_id: str, thresholds: Optional[dict]) -> Dict[str, Any]:
    """Blocking model call. MediaPipe FaceMesh is not re-entrant, so calls are serialised."""
    with _inference_lock:
        pred = model_predict(frame=frame, driver_id=driver_id, custom_thresholds=thresholds)
    pred.pop("to_dict", None)
    return pred


async def process_frame(
    frame: np.ndarray,
    driver_id: str,
    auth_session: Session,
    ops_session: Session,
    source: str = "webcam",
    broadcast_telemetry: bool = True,
    device_id: Optional[str] = None,
    frame_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the detection pipeline on one frame, drive alert levels, and broadcast.

    Shared by every frame source (Pi frames endpoint, webcam worker, legacy
    /detect/frame). Returns the model output plus the alert state the client
    should react to: state (awake|drowsy|no_face|error), severity 0-3, alert_id.
    """
    driver, fleet_id = driver_context(auth_session, driver_id)
    driver_name = driver.full_name if driver else "Driver"
    thresholds = _get_driver_thresholds(ops_session, driver_id, fleet_id)
    eff_ear_thresh = thresholds.get("ear", 0.21) if thresholds else 0.21
    eff_mar_thresh = thresholds.get("mar", 0.60) if thresholds else 0.60

    if not MODEL_AVAILABLE or model_predict is None:
        return _error_result(driver_id, "Detection model is not installed on the server.")
    try:
        result = await asyncio.to_thread(_infer, frame, driver_id, thresholds)
    except Exception as e:
        # Never substitute made-up metrics: report the failure and skip alerting.
        logger.error(f"Inference error: {e}")
        return _error_result(driver_id, f"Inference failed: {e}")
    latency_logger.mark(frame_id, inference_done_ms=now_ms())

    # Handle online baseline calibration if active
    if calibration_service.is_calibrating(driver_id):
        ear_val = float(result.get("ear", 0.0))
        mar_val = float(result.get("mar", 0.0))
        calib_result = calibration_service.process_frame_sample(
            driver_id=driver_id,
            ear=ear_val,
            mar=mar_val,
            ops_session=ops_session,
        )
        if calib_result:
            await manager.broadcast_calibration_event(
                driver_id=driver_id,
                event_type="calibration_complete",
                data=calib_result,
            )
        else:
            session = calibration_service.get_session(driver_id)
            if session:
                await manager.broadcast_calibration_event(
                    driver_id=driver_id,
                    event_type="calibration_progress",
                    data={
                        "progress": round(session.progress, 2),
                        "remaining_seconds": round(session.remaining_seconds, 1),
                        "samples": len(session.ear_samples),
                        "message": "Calibrating baseline... Keep eyes open and mouth relaxed.",
                    },
                )

    # Time-window alert levels on the server clock, using unsmoothed EAR/MAR.
    has_face = bool(result.get("face_detected", result.get("status") != "no_face"))
    decision = await alerting_service.handle_observation(
        ops_session=ops_session,
        driver_id=driver_id,
        driver_name=driver_name,
        fleet_id=fleet_id,
        obs=Observation(
            ts=alerting_service.clock(),
            has_face=has_face,
            ear=float(result.get("raw_ear", result.get("ear", 0.0))),
            mar=float(result.get("raw_mar", result.get("mar", 0.0))),
            ear_threshold=eff_ear_thresh,
            mar_threshold=eff_mar_thresh,
        ),
        source=source,
        device_id=device_id,
        frame_id=frame_id,
    )
    current = alerting_service.current(driver_id)
    state = decision.state
    if current["severity"] > 0 and state == "awake":
        state = "drowsy"  # an unacknowledged alert is still ringing

    if state == "no_face":
        status = "no_face"
    elif state == "drowsy":
        status = "yawning" if decision.reason == "yawn" else "drowsy"
    else:
        status = "alert"

    current_ist = now_ist()
    metrics = {
        "ear": round(result.get("ear", 0.0), 3),
        "mar": round(result.get("mar", 0.0), 3),
        "raw_ear": round(float(result.get("raw_ear", 0.0)), 3),
        "raw_mar": round(float(result.get("raw_mar", 0.0)), 3),
        "perclos": round(result.get("perclos", 0.0), 3),
        "eyes_closed_seconds": decision.eyes_low_s,
        "ear_threshold": round(eff_ear_thresh, 3),
        "mar_threshold": round(eff_mar_thresh, 3),
        "reason": decision.reason or "normal",
        "backend": result.get("backend", "baseline"),
        "latency_ms": result.get("latency_ms"),
    }

    if broadcast_telemetry and _telemetry_due(driver_id):
        delivered = await manager.broadcast_detection(
            driver_id=driver_id,
            driver_name=driver_name,
            driver_fleet_id=fleet_id,
            status=status,
            severity=LEVEL_SEVERITY.get(current["severity"], "low"),
            confidence=float(result.get("confidence", 0.0)),
            metrics=metrics,
            timestamp_hhmm=format_ist_time(current_ist),
            iso_timestamp=to_ist_iso(current_ist),
            is_alert=False,
            extra={
                "state": state,
                "level": current["severity"],
                "alert_id": current["alert_id"],
                "frame_id": frame_id,
                "device_id": device_id,
                "source": source,
                "server_ts_ms": round(now_ms(), 1),
            },
        )
        if delivered:
            latency_logger.mark(frame_id, ws_sent_ms=now_ms())

    result.update({
        "status": status,
        "state": state,
        "severity_level": current["severity"],
        "alert_id": current["alert_id"],
        "alert_status": current["alert_status"],
        "reason": decision.reason,
        "eyes_closed_seconds": decision.eyes_low_s,
        "alert_triggered": decision.event is not None,
        "ear_threshold": eff_ear_thresh,
        "mar_threshold": eff_mar_thresh,
    })
    if decision.event is not None:
        result["alert_message"] = f"You were drowsy at {format_ist_time(current_ist)}"
    return result


def _telemetry_due(driver_id: str) -> bool:
    hz = max(0.1, get_settings().TELEMETRY_HZ)
    now = time.monotonic()
    if now - _last_telemetry_ts.get(driver_id, 0.0) >= 1.0 / hz - 0.02:
        _last_telemetry_ts[driver_id] = now
        return True
    return False


def _error_result(driver_id: str, message: str) -> Dict[str, Any]:
    current = alerting_service.current(driver_id)
    return {
        "driver_id": driver_id,
        "status": "error",
        "state": "error",
        "error": message,
        "severity_level": current["severity"],
        "alert_id": current["alert_id"],
        "alert_status": current["alert_status"],
        "alert_triggered": False,
        "timestamp": time.time(),
        "backend": "unavailable",
    }


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

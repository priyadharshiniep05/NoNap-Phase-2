"""/api/v1: Raspberry Pi ingest, device heartbeats, alert ack, and driving sessions.

Two kinds of callers:
- Devices (Pi, tools/simulate_pi.py) send the X-Device-Key shared secret.
- People (the app) send their JWT; role and ownership are checked on every route.
"""

import asyncio
from collections import defaultdict
from typing import Dict, Optional

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from server.app.core.config import get_settings
from server.app.core.deps import Role, get_current_user_ws, require_role
from server.app.core.timezone import as_ist, ist_wall_now
from server.app.db.auth_db import get_auth_session
from server.app.db.models_auth import User
from server.app.db.models_ops import AlertLog, Device, SessionStat
from server.app.db.ops_db import get_ops_session
from server.app.services.alerting_service import alerting_service, serialize_alert
from server.app.services.detection_service import process_frame
from server.app.services.device_service import device_service
from server.app.services.driver_context import manager_fleet_id, resolve_driver, driver_context
from server.app.services.latency_logger import latency_logger, now_ms

router = APIRouter(prefix="/api/v1", tags=["API v1 (Pi + alerting)"])
_bearer = HTTPBearer(auto_error=False)


# ---- auth helpers ---------------------------------------------------------

def _device_key_ok(key: Optional[str]) -> bool:
    expected = get_settings().DEVICE_API_KEY
    return bool(expected) and key == expected


def require_device(x_device_key: Optional[str] = Header(None)) -> None:
    if not _device_key_ok(x_device_key):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing or wrong X-Device-Key.")


class Principal:
    def __init__(self, device: bool = False, user: Optional[User] = None):
        self.device = device
        self.user = user


def device_or_user(
    x_device_key: Optional[str] = Header(None),
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    auth_db: Session = Depends(get_auth_session),
) -> Principal:
    if _device_key_ok(x_device_key):
        return Principal(device=True)
    if creds is not None:
        user = get_current_user_ws(creds.credentials, auth_db)
        if user is not None:
            return Principal(user=user)
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Device key or user token required.")


def _can_see_driver(p: Principal, driver_id: Optional[str], auth_db: Session) -> bool:
    if p.device:
        return True
    if p.user is None or driver_id is None:
        return False
    if p.user.role == "driver":
        return p.user.id == driver_id
    fleet_id = manager_fleet_id(auth_db, p.user.id)
    _, driver_fleet = driver_context(auth_db, driver_id)
    return fleet_id is not None and fleet_id == driver_fleet


# ---- frames ---------------------------------------------------------------

# Latest-frame-only gating per device: a request that waited behind a newer
# frame is answered immediately without inference.
_frame_seq: Dict[str, int] = defaultdict(int)
_frame_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


@router.post("/frames", dependencies=[Depends(require_device)])
async def ingest_frame(
    frame: UploadFile = File(..., description="JPEG frame"),
    device_id: str = Form(...),
    driver_id: str = Form(..., description="Driver UUID or email"),
    captured_at: Optional[float] = Form(None, description="Capture time, epoch ms (device clock)"),
    last_rtt_ms: Optional[float] = Form(None, description="Device-measured round trip of the previous frame"),
    source: str = Form("pi"),
    auth_db: Session = Depends(get_auth_session),
    ops_db: Session = Depends(get_ops_session),
):
    """Run the detection pipeline on a frame from a Pi and return what it should do now."""
    receive_ms = now_ms()
    settings = get_settings()
    if settings.VIDEO_SOURCE != "pi":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Server is running with VIDEO_SOURCE={settings.VIDEO_SOURCE}. Restart it with VIDEO_SOURCE=pi to accept Pi frames.",
        )
    driver = resolve_driver(auth_db, driver_id)
    if driver is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No active driver '{driver_id}'.")

    _frame_seq[device_id] += 1
    my_seq = _frame_seq[device_id]
    frame_id = f"{device_id}-{int(captured_at if captured_at else receive_ms)}"
    data = await frame.read()

    async with _frame_locks[device_id]:
        await device_service.frame_seen(ops_db, auth_db, device_id, driver.id)
        if my_seq != _frame_seq[device_id]:
            current = alerting_service.current(driver.id)
            return {"dropped": True, "frame_id": frame_id, "state": None, **_severity_view(current)}

        img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Could not decode JPEG frame.")
        from server.app.capture.webcam_worker import webcam_worker
        webcam_worker.set_preview_jpeg(data)  # in-memory preview for the app; never written to disk

        latency_logger.start(
            frame_id,
            source="simulated" if source == "simulated" else "pi",
            device_id=device_id,
            driver_id=driver.id,
            pi_capture_ms=captured_at,
            server_receive_ms=receive_ms,
            pi_rtt_ms=last_rtt_ms,
        )
        res = await process_frame(
            frame=img,
            driver_id=driver.id,
            auth_session=auth_db,
            ops_session=ops_db,
            source="simulated" if source == "simulated" else "pi",
            device_id=device_id,
            frame_id=frame_id,
        )

    return {
        "dropped": False,
        "frame_id": frame_id,
        "state": res.get("state"),
        "severity": res.get("severity_level", 0),
        "alert_id": res.get("alert_id"),
        "alert_status": res.get("alert_status"),
        "ear": res.get("ear"),
        "mar": res.get("mar"),
        "eyes_closed_seconds": res.get("eyes_closed_seconds"),
        "error": res.get("error"),
        "server_ms": round(now_ms() - receive_ms, 1),
    }


def _severity_view(current: dict) -> dict:
    return {
        "severity": current["severity"],
        "alert_id": current["alert_id"],
        "alert_status": current["alert_status"],
    }


# ---- devices --------------------------------------------------------------

class HeartbeatRequest(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=64)
    driver_id: Optional[str] = None
    fps: Optional[float] = None
    cpu_temp_c: Optional[float] = None
    uptime_s: Optional[float] = None
    ip: Optional[str] = None
    camera_backend: Optional[str] = None
    vehicle: Optional[str] = None
    rtt_ms: Optional[float] = None


@router.post("/devices/heartbeat", dependencies=[Depends(require_device)])
async def device_heartbeat(
    payload: HeartbeatRequest,
    auth_db: Session = Depends(get_auth_session),
    ops_db: Session = Depends(get_ops_session),
):
    driver = resolve_driver(auth_db, payload.driver_id) if payload.driver_id else None
    d = await device_service.heartbeat(
        ops_db, auth_db, payload.device_id, driver.id if driver else None, payload.model_dump()
    )
    return {
        "ok": True,
        "device": device_service.status_dict(d),
        "driver_name": driver.full_name if driver else None,
        "video_source": get_settings().VIDEO_SOURCE,
        "server_time_ms": round(now_ms()),
    }


@router.get("/devices/{device_id}")
def get_device(
    device_id: str,
    p: Principal = Depends(device_or_user),
    auth_db: Session = Depends(get_auth_session),
    ops_db: Session = Depends(get_ops_session),
):
    d = ops_db.query(Device).filter(Device.id == device_id).first()
    if d is None or not _can_see_driver(p, d.driver_id, auth_db):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Device not found.")
    return device_service.status_dict(d)


# ---- alerts ---------------------------------------------------------------

@router.get("/alerts/{alert_id}")
def get_alert(
    alert_id: str,
    p: Principal = Depends(device_or_user),
    auth_db: Session = Depends(get_auth_session),
    ops_db: Session = Depends(get_ops_session),
):
    a = ops_db.query(AlertLog).filter(AlertLog.id == alert_id).first()
    if a is None or not _can_see_driver(p, a.driver_id, auth_db):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found.")
    driver, _ = driver_context(auth_db, a.driver_id)
    return serialize_alert(a, driver.full_name if driver else "Driver")


@router.post("/alerts/{alert_id}/ack")
async def acknowledge_alert(
    alert_id: str,
    driver: User = Depends(require_role(Role.driver)),
    ops_db: Session = Depends(get_ops_session),
):
    """The driver's "I'm awake". Only the driver the alert belongs to may acknowledge it."""
    a = ops_db.query(AlertLog).filter(AlertLog.id == alert_id).first()
    if a is None or a.driver_id != driver.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found.")
    a = await alerting_service.acknowledge(ops_db, a, driver.full_name)
    return serialize_alert(a, driver.full_name)


# ---- driver session + device ---------------------------------------------

def _session_view(s: Optional[SessionStat], driver_id: str, ops_db: Session) -> dict:
    if s is None:
        return {"active": False}
    q = ops_db.query(AlertLog).filter(AlertLog.driver_id == driver_id, AlertLog.detected_at >= s.started_at)
    if s.ended_at is not None:
        q = q.filter(AlertLog.detected_at <= s.ended_at)
    alerts = q.count()
    avg_ack = q.filter(AlertLog.response_time_ms.isnot(None)).with_entities(func.avg(AlertLog.response_time_ms)).scalar()
    end = s.ended_at or ist_wall_now()
    return {
        "active": s.ended_at is None,
        "id": s.id,
        "started_at": as_ist(s.started_at).isoformat(),
        "ended_at": as_ist(s.ended_at).isoformat() if s.ended_at else None,
        "driving_seconds": max(0, int((end - s.started_at).total_seconds())),
        "alerts": alerts,
        "avg_ack_ms": round(avg_ack, 1) if avg_ack is not None else None,
    }


def _open_session(ops_db: Session, driver_id: str) -> Optional[SessionStat]:
    return (
        ops_db.query(SessionStat)
        .filter(SessionStat.driver_id == driver_id, SessionStat.ended_at.is_(None))
        .order_by(SessionStat.started_at.desc())
        .first()
    )


@router.get("/driver/session")
def get_session(driver: User = Depends(require_role(Role.driver)), ops_db: Session = Depends(get_ops_session)):
    return _session_view(_open_session(ops_db, driver.id), driver.id, ops_db)


@router.post("/driver/session/start")
def start_session(driver: User = Depends(require_role(Role.driver)), ops_db: Session = Depends(get_ops_session)):
    s = _open_session(ops_db, driver.id)
    if s is None:
        s = SessionStat(driver_id=driver.id, started_at=ist_wall_now())
        ops_db.add(s)
        ops_db.commit()
        ops_db.refresh(s)
    if get_settings().VIDEO_SOURCE == "webcam":
        from server.app.capture.webcam_worker import webcam_worker
        webcam_worker.start(driver_id=driver.id)
    return _session_view(s, driver.id, ops_db)


@router.post("/driver/session/end")
def end_session(driver: User = Depends(require_role(Role.driver)), ops_db: Session = Depends(get_ops_session)):
    s = _open_session(ops_db, driver.id)
    if s is not None:
        s.ended_at = ist_wall_now()
        s.alert_count = (
            ops_db.query(AlertLog)
            .filter(AlertLog.driver_id == driver.id, AlertLog.detected_at >= s.started_at)
            .count()
        )
        ops_db.commit()
        ops_db.refresh(s)
    if get_settings().VIDEO_SOURCE == "webcam":
        from server.app.capture.webcam_worker import webcam_worker
        if webcam_worker.driver_id == driver.id:
            webcam_worker.stop()
    return _session_view(s, driver.id, ops_db)


@router.get("/driver/device")
def my_device(driver: User = Depends(require_role(Role.driver)), ops_db: Session = Depends(get_ops_session)):
    """The driver's camera: their Pi, or the MacBook webcam in webcam mode."""
    settings = get_settings()
    d = device_service.device_for_driver(ops_db, driver.id)
    return {
        "video_source": settings.VIDEO_SOURCE,
        "device": device_service.status_dict(d) if d else None,
    }


@router.get("/system")
def system_info():
    """Public, non-sensitive settings the app needs (countdown length, source)."""
    s = get_settings()
    return {
        "video_source": s.VIDEO_SOURCE,
        "ack_timeout_seconds": s.ACK_TIMEOUT_SECONDS,
        "l1_eyes_low_seconds": s.L1_EYES_LOW_SECONDS,
        "l2_eyes_low_seconds": s.L2_EYES_LOW_SECONDS,
        "device_offline_seconds": s.DEVICE_OFFLINE_SECONDS,
        "telemetry_hz": s.TELEMETRY_HZ,
    }

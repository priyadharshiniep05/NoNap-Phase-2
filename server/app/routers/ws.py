"""WebSocket streaming router for Flutter mobile clients and web dashboards.

/ws/driver/{driver_id}  a driver's own alerts, live EAR/MAR (~2 Hz), device status
/ws/fleet/{manager_id}  alerts and statuses for every driver in the manager's fleet
/ws                     legacy endpoint (same scoping, role taken from the token)

Every endpoint authenticates with the access token (?token=... or a first
{"type": "auth", "token": ...} message). The path id must match the token's
user and the role must match the path.
"""

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from server.app.core.deps import get_current_user_ws
from server.app.db.auth_db import get_auth_session_factory
from server.app.db.models_auth import FleetDriver, User
from server.app.db.models_ops import AlertLog, Device
from server.app.db.ops_db import get_ops_session_factory
from server.app.realtime.connection_manager import manager
from server.app.services.alerting_service import alerting_service, serialize_alert
from server.app.services.device_service import device_service
from server.app.services.driver_context import ws_fleet_id
from server.app.services.latency_logger import latency_logger

logger = logging.getLogger("nonap.ws")
router = APIRouter(tags=["WebSocket"])


async def _authenticate(websocket: WebSocket, token: Optional[str], auth_db) -> Optional[User]:
    user = get_current_user_ws(token, auth_db) if token else None
    if user:
        return user
    await websocket.accept()
    try:
        raw_auth = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
        data = json.loads(raw_auth)
        if data.get("type") == "auth" and "token" in data:
            user = get_current_user_ws(data["token"], auth_db)
    except Exception:
        await websocket.close(code=4001, reason="Authentication timeout or invalid message")
        return None
    if not user:
        await websocket.close(code=4003, reason="Unauthorized")
    return user


def _snapshot(user: User, fleet_id: Optional[str], auth_db) -> dict:
    """Current open alerts and device states, so a reconnecting app catches up."""
    if user.role == "driver":
        driver_ids = [user.id]
    elif fleet_id:
        driver_ids = [fd.driver_id for fd in auth_db.query(FleetDriver).filter(FleetDriver.fleet_id == fleet_id)]
    else:
        driver_ids = []

    names = {u.id: u.full_name for u in auth_db.query(User).filter(User.id.in_(driver_ids))} if driver_ids else {}
    ops = get_ops_session_factory()()
    try:
        alerts = []
        for did in driver_ids:
            oa = alerting_service.open_alert(did)
            if oa is None:
                continue
            a = ops.query(AlertLog).filter(AlertLog.id == oa.id).first()
            if a is not None and not a.acknowledged:
                alerts.append(serialize_alert(a, names.get(did, "Driver")))
        devices = [
            device_service.status_dict(d)
            for d in ops.query(Device).filter(Device.driver_id.in_(driver_ids)).all()
        ] if driver_ids else []
    finally:
        ops.close()
    return {"type": "snapshot", "open_alerts": alerts, "devices": devices}


async def _serve(websocket: WebSocket, token: Optional[str], path_user_id: Optional[str], required_role: Optional[str]):
    auth_db = get_auth_session_factory()()
    try:
        user = await _authenticate(websocket, token, auth_db)
        if not user:
            return
        if (required_role and user.role != required_role) or (path_user_id and user.id != path_user_id):
            if websocket.client_state.name == "CONNECTING":
                await websocket.accept()
            await websocket.close(code=4003, reason="Forbidden for this role or user")
            return

        fleet_id = ws_fleet_id(auth_db, user)
        await manager.connect(
            websocket=websocket,
            user_id=user.id,
            full_name=user.full_name,
            role=user.role,
            fleet_id=fleet_id,
        )
        if required_role:  # role-specific endpoints only; legacy /ws keeps its old message order
            await websocket.send_json(_snapshot(user, fleet_id, auth_db))

        while True:
            text = await websocket.receive_text()
            try:
                msg = json.loads(text)
            except json.JSONDecodeError:
                continue
            msg_type = msg.get("type")
            if msg_type == "ping":
                await websocket.send_json({"type": "pong", "message": "heartbeat"})
            elif msg_type == "receipt" and msg.get("frame_id") and msg.get("received_ms"):
                # The app echoes frame ids so the paper's latency CSV has app-side receive time.
                try:
                    latency_logger.app_received(str(msg["frame_id"]), float(msg["received_ms"]))
                except (TypeError, ValueError):
                    pass
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket unhandled error: {e}")
    finally:
        await manager.disconnect(websocket)
        auth_db.close()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: Optional[str] = Query(None)):
    """Legacy endpoint: role and scope come from the token."""
    await _serve(websocket, token, None, None)


@router.websocket("/ws/driver/{driver_id}")
async def driver_ws(websocket: WebSocket, driver_id: str, token: Optional[str] = Query(None)):
    await _serve(websocket, token, driver_id, "driver")


@router.websocket("/ws/fleet/{manager_id}")
async def fleet_ws(websocket: WebSocket, manager_id: str, token: Optional[str] = Query(None)):
    await _serve(websocket, token, manager_id, "fleet_manager")

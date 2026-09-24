"""WebSocket streaming router for Flutter mobile clients and web dashboards."""

import asyncio
import json
import logging
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from sqlalchemy.orm import Session

from server.app.core.deps import get_current_user_ws
from server.app.db.auth_db import get_auth_session_factory
from server.app.db.models_auth import FleetDriver
from server.app.realtime.connection_manager import manager

logger = logging.getLogger("nonap.ws")
router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
):
    """Real-time bidirectional WebSocket stream for driver & fleet manager telemetry."""
    auth_factory = get_auth_session_factory()
    auth_db = auth_factory()

    user = None
    try:
        # 1. Attempt auth from query param
        if token:
            user = get_current_user_ws(token, auth_db)

        # If not in query param, wait for first auth message
        if not user:
            await websocket.accept()
            try:
                raw_auth = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
                data = json.loads(raw_auth)
                if data.get("type") == "auth" and "token" in data:
                    user = get_current_user_ws(data["token"], auth_db)
            except Exception:
                await websocket.close(code=4001, reason="Authentication timeout or invalid message")
                return

        if not user:
            await websocket.close(code=4003, reason="Unauthorized")
            return

        # Find fleet_id
        fd = auth_db.query(FleetDriver).filter(FleetDriver.driver_id == user.id).first()
        fleet_id = fd.fleet_id if fd else None

        # Connect to manager
        await manager.connect(
            websocket=websocket,
            user_id=user.id,
            full_name=user.full_name,
            role=user.role,
            fleet_id=fleet_id,
        )

        # Message loop
        while True:
            text = await websocket.receive_text()
            try:
                msg = json.loads(text)
                msg_type = msg.get("type")
                if msg_type == "ping":
                    await websocket.send_json({"type": "pong", "message": "heartbeat"})
            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket unhandled error: {e}")
        await manager.disconnect(websocket)
    finally:
        auth_db.close()

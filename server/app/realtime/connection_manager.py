"""WebSocket Connection Manager with role-filtered broadcast fan-out."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Any
from fastapi import WebSocket

logger = logging.getLogger("nonap.realtime")


class Connection:
    def __init__(
        self,
        websocket: WebSocket,
        user_id: str,
        full_name: str,
        role: str,
        fleet_id: Optional[str] = None,
    ):
        self.websocket = websocket
        self.user_id = user_id
        self.full_name = full_name
        self.role = role
        self.fleet_id = fleet_id


class ConnectionManager:
    """Manages WebSocket connections and enforces strict role-based telemetry delivery."""

    def __init__(self):
        # List of active connections
        self.active_connections: List[Connection] = []
        # In-memory latest status for each driver: driver_id -> status dict
        self._latest_driver_status: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def connect(
        self,
        websocket: WebSocket,
        user_id: str,
        full_name: str,
        role: str,
        fleet_id: Optional[str] = None,
    ) -> Connection:
        await websocket.accept()
        conn = Connection(
            websocket=websocket,
            user_id=user_id,
            full_name=full_name,
            role=role,
            fleet_id=fleet_id,
        )
        async with self._lock:
            self.active_connections.append(conn)
        logger.info(f"WebSocket connected: user_id={user_id}, role={role}, total={len(self.active_connections)}")

        # Send connection ack
        await websocket.send_json({
            "type": "connection_ack",
            "driver_id": user_id,
            "driver_name": full_name,
            "status": "connected",
            "severity": "low",
            "confidence": 1.0,
            "metrics": {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": f"Connected as {role} ({full_name})",
        })
        return conn

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            self.active_connections = [
                c for c in self.active_connections if c.websocket != websocket
            ]
        logger.info(f"WebSocket disconnected, remaining={len(self.active_connections)}")

    def get_latest_status(self, driver_id: str) -> Optional[Dict[str, Any]]:
        return self._latest_driver_status.get(driver_id)

    def set_latest_status(self, driver_id: str, status_data: Dict[str, Any]):
        self._latest_driver_status[driver_id] = status_data

    async def broadcast_detection(
        self,
        driver_id: str,
        driver_name: str,
        driver_fleet_id: Optional[str],
        status: str,  # alert, drowsy, yawning, accident, no_face
        severity: str,  # low, medium, high, critical
        confidence: float,
        metrics: Dict[str, Any],
        timestamp_hhmm: str,
        iso_timestamp: str,
        is_alert: bool = False,
        extra: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Broadcast detection result with role-appropriate messaging and scoping.

        Returns the number of sockets the message was delivered to.
        """
        # Update latest state cache
        self.set_latest_status(driver_id, {
            "status": status,
            "severity": severity,
            "confidence": confidence,
            "metrics": metrics,
            "timestamp": iso_timestamp,
            "driver_name": driver_name,
            "fleet_id": driver_fleet_id,
            **(extra or {}),
        })

        # Format message based on status
        if status == "alert":
            driver_msg = "You are alert and focused."
            manager_msg = f"{driver_name} is alert."
        elif status == "drowsy":
            driver_msg = f"You were drowsy at {timestamp_hhmm}."
            manager_msg = f"{driver_name} was drowsy at {timestamp_hhmm}."
        elif status == "yawning":
            driver_msg = f"Yawning detected at {timestamp_hhmm}. Consider a short break."
            manager_msg = f"{driver_name} was yawning at {timestamp_hhmm}."
        elif status == "accident":
            driver_msg = f"CRITICAL: Accident alert recorded at {timestamp_hhmm}!"
            manager_msg = f"CRITICAL: Accident reported for {driver_name} at {timestamp_hhmm}!"
        elif status == "no_face":
            driver_msg = "No driver face detected in camera view."
            manager_msg = f"No face detected for {driver_name}."
        else:
            driver_msg = f"Status: {status} at {timestamp_hhmm}."
            manager_msg = f"{driver_name} status: {status} at {timestamp_hhmm}."

        msg_type = "alert" if is_alert else "telemetry"

        dead_connections: List[Connection] = []
        delivered = 0

        async with self._lock:
            connections = list(self.active_connections)

        for conn in connections:
            try:
                # Driver: only sees their own data
                if conn.role == "driver":
                    if conn.user_id == driver_id:
                        payload = {
                            "type": msg_type,
                            "driver_id": driver_id,
                            "driver_name": driver_name,
                            "status": status,
                            "severity": severity,
                            "confidence": round(confidence, 3),
                            "metrics": metrics,
                            "timestamp": iso_timestamp,
                            "timestamp_ist": timestamp_hhmm,
                            "message": driver_msg,
                            **(extra or {}),
                        }
                        await conn.websocket.send_json(payload)
                        delivered += 1
                # Fleet manager: sees data for drivers in their fleet
                elif conn.role == "fleet_manager":
                    if conn.fleet_id is not None and conn.fleet_id == driver_fleet_id:
                        payload = {
                            "type": msg_type,
                            "driver_id": driver_id,
                            "driver_name": driver_name,
                            "status": status,
                            "severity": severity,
                            "confidence": round(confidence, 3),
                            "metrics": metrics,
                            "timestamp": iso_timestamp,
                            "timestamp_ist": timestamp_hhmm,
                            "message": manager_msg,
                            **(extra or {}),
                        }
                        await conn.websocket.send_json(payload)
                        delivered += 1
            except Exception as e:
                logger.warning(f"Error sending message to conn {conn.user_id}: {e}")
                dead_connections.append(conn)

        await self._drop(dead_connections)
        return delivered

    async def _drop(self, dead: List[Connection]) -> None:
        if dead:
            async with self._lock:
                self.active_connections = [c for c in self.active_connections if c not in dead]

    async def send_scoped(
        self,
        driver_id: str,
        driver_fleet_id: Optional[str],
        driver_payload: Optional[Dict[str, Any]],
        fleet_payload: Optional[Dict[str, Any]],
    ) -> int:
        """Send one event about a driver: the driver gets driver_payload, the
        manager of that driver's fleet gets fleet_payload. Nobody else."""
        async with self._lock:
            connections = list(self.active_connections)

        dead: List[Connection] = []
        delivered = 0
        for conn in connections:
            if conn.role == "driver" and conn.user_id == driver_id:
                payload = driver_payload
            elif (
                conn.role == "fleet_manager"
                and conn.fleet_id is not None
                and conn.fleet_id == driver_fleet_id
            ):
                payload = fleet_payload
            else:
                continue
            if payload is None:
                continue
            try:
                await conn.websocket.send_json(payload)
                delivered += 1
            except Exception as e:
                logger.warning(f"Error sending event to {conn.user_id}: {e}")
                dead.append(conn)
        await self._drop(dead)
        return delivered

    async def send_to_user(self, user_id: str, payload: Dict[str, Any]) -> None:
        async with self._lock:
            connections = [c for c in self.active_connections if c.user_id == user_id]
        for conn in connections:
            try:
                await conn.websocket.send_json(payload)
            except Exception:
                await self._drop([conn])


    async def broadcast_calibration_event(
        self,
        driver_id: str,
        event_type: str,  # calibration_progress, calibration_complete
        data: Dict[str, Any],
    ):
        """Send calibration status or result to the driver's active WebSocket."""
        async with self._lock:
            connections = list(self.active_connections)

        payload = {
            "type": event_type,
            "driver_id": driver_id,
            **data,
        }
        for conn in connections:
            if conn.role == "driver" and conn.user_id == driver_id:
                try:
                    await conn.websocket.send_json(payload)
                except Exception as e:
                    logger.warning(f"Error sending calibration event to {conn.user_id}: {e}")

# Singleton instance
manager = ConnectionManager()

"""Capture-device registry: heartbeats, liveness, and online/offline pushes.

Liveness is kept in memory (a server restart marks every device offline until
its next heartbeat). Heartbeats and frames both count as "seen". The DB2
`devices` row keeps the last reported telemetry for display.
"""

import logging
import time
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from server.app.core.config import get_settings
from server.app.core.timezone import as_ist, ist_wall_now
from server.app.db.models_ops import Device
from server.app.realtime.connection_manager import manager
from server.app.services.driver_context import driver_context

logger = logging.getLogger("nonap.devices")


class DeviceService:
    def __init__(self) -> None:
        self._last_seen: Dict[str, float] = {}
        self._announced_online: Dict[str, bool] = {}
        self._driver_of: Dict[str, str] = {}
        self.clock = time.time

    def reset(self) -> None:
        self._last_seen.clear()
        self._announced_online.clear()
        self._driver_of.clear()

    def is_online(self, device_id: str, now: Optional[float] = None) -> bool:
        seen = self._last_seen.get(device_id)
        if seen is None:
            return False
        now = now if now is not None else self.clock()
        return now - seen < get_settings().DEVICE_OFFLINE_SECONDS

    def seconds_since_seen(self, device_id: str) -> Optional[float]:
        seen = self._last_seen.get(device_id)
        return None if seen is None else round(self.clock() - seen, 1)

    def status_dict(self, d: Device) -> Dict[str, Any]:
        last = as_ist(d.last_seen_at)
        return {
            "device_id": d.id,
            "driver_id": d.driver_id,
            "vehicle": d.vehicle,
            "online": self.is_online(d.id),
            "ip": d.ip,
            "camera_backend": d.camera_backend,
            "fps": d.fps,
            "cpu_temp_c": d.cpu_temp_c,
            "uptime_s": d.uptime_s,
            "rtt_ms": d.rtt_ms,
            "last_seen_at": last.isoformat() if last else None,
            "seconds_since_seen": self.seconds_since_seen(d.id),
        }

    def _upsert(self, ops_session: Session, device_id: str, driver_id: Optional[str]) -> Device:
        d = ops_session.query(Device).filter(Device.id == device_id).first()
        if d is None:
            d = Device(id=device_id, driver_id=driver_id, created_at=ist_wall_now())
            ops_session.add(d)
        elif driver_id and d.driver_id != driver_id:
            d.driver_id = driver_id
        return d

    async def heartbeat(
        self,
        ops_session: Session,
        auth_session: Session,
        device_id: str,
        driver_id: Optional[str],
        fields: Dict[str, Any],
    ) -> Device:
        d = self._upsert(ops_session, device_id, driver_id)
        for key in ("vehicle", "ip", "camera_backend", "fps", "cpu_temp_c", "uptime_s", "rtt_ms"):
            if fields.get(key) is not None:
                setattr(d, key, fields[key])
        d.last_seen_at = ist_wall_now()
        ops_session.commit()
        ops_session.refresh(d)
        await self._mark_seen(auth_session, d)
        return d

    async def frame_seen(self, ops_session: Session, auth_session: Session, device_id: str, driver_id: str) -> None:
        """Frames also prove the device is alive. Once it is announced online,
        only the in-memory clock moves; heartbeats keep the DB row current."""
        if self._announced_online.get(device_id):
            self._last_seen[device_id] = self.clock()
            return
        d = self._upsert(ops_session, device_id, driver_id)
        d.last_seen_at = ist_wall_now()
        ops_session.commit()
        await self._mark_seen(auth_session, d)

    async def _mark_seen(self, auth_session: Session, d: Device) -> None:
        self._last_seen[d.id] = self.clock()
        if d.driver_id:
            self._driver_of[d.id] = d.driver_id
        if not self._announced_online.get(d.id):
            self._announced_online[d.id] = True
            logger.info(f"Device {d.id} online (driver={d.driver_id}, ip={d.ip})")
        # Every heartbeat refreshes fps / temperature on the app chips
        await self._push(auth_session, d)

    async def check_offline(self, ops_session_factory, auth_session_factory) -> int:
        """Announce devices whose last contact is older than DEVICE_OFFLINE_SECONDS."""
        now = self.clock()
        gone = [
            dev_id for dev_id, online in self._announced_online.items()
            if online and not self.is_online(dev_id, now)
        ]
        if not gone:
            return 0
        ops, auth = ops_session_factory(), auth_session_factory()
        try:
            for dev_id in gone:
                self._announced_online[dev_id] = False
                d = ops.query(Device).filter(Device.id == dev_id).first()
                if d is not None:
                    logger.warning(f"Device {dev_id} offline (no contact for {now - self._last_seen[dev_id]:.0f}s)")
                    await self._push(auth, d)
        finally:
            ops.close()
            auth.close()
        return len(gone)

    async def _push(self, auth_session: Session, d: Device) -> None:
        if not d.driver_id:
            return
        _, fleet_id = driver_context(auth_session, d.driver_id)
        payload = {"type": "device_status", "driver_id": d.driver_id, "device": self.status_dict(d)}
        await manager.send_scoped(d.driver_id, fleet_id, payload, payload)

    def device_for_driver(self, ops_session: Session, driver_id: str) -> Optional[Device]:
        """The driver's most recently seen device."""
        return (
            ops_session.query(Device)
            .filter(Device.driver_id == driver_id)
            .order_by(Device.last_seen_at.desc())
            .first()
        )


device_service = DeviceService()

"""Level-based alert lifecycle: raise, upgrade, escalate to level 3, acknowledge.

alert_levels.AlertLevelPolicy decides levels 1-2 from frames. This service
persists the alert in DB2, pushes it over WebSockets, runs the level-3 timer
(an unacknowledged level-2 alert after ACK_TIMEOUT_SECONDS), and records the
driver's acknowledgement time.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from sqlalchemy.orm import Session

from server.app.core.config import get_settings
from server.app.core.timezone import as_ist, ist_wall_now
from server.app.db.models_ops import AlertLog
from server.app.realtime.connection_manager import manager
from server.app.services.alert_levels import AlertLevelPolicy, Decision, LevelConfig, Observation
from server.app.services.latency_logger import latency_logger, now_ms

logger = logging.getLogger("nonap.alerting")

LEVEL_SEVERITY = {1: "medium", 2: "high", 3: "critical"}
OPEN_STATUSES = ("active", "unacknowledged")


@dataclass
class OpenAlert:
    id: str
    driver_id: str
    driver_name: str
    fleet_id: Optional[str]
    level: int
    status: str
    raised_ts: float
    l2_ts: Optional[float] = None


def first_name(full_name: str) -> str:
    return (full_name or "Driver").replace("[Simulated]", "").strip().split(" ")[0] or "Driver"


def serialize_alert(a: AlertLog, driver_name: str) -> Dict[str, Any]:
    detected = as_ist(a.detected_at)
    return {
        "id": a.id,
        "driver_id": a.driver_id,
        "driver_name": driver_name,
        "fleet_id": a.fleet_id,
        "type": a.type,
        "severity": a.severity,
        "level": a.level,
        "status": a.status,
        "reason": a.reason,
        "ear": a.ear,
        "mar": a.mar,
        "source": a.source,
        "device_id": a.device_id,
        "detected_at": detected.isoformat() if detected else None,
        "time_ist": detected.strftime("%H:%M") if detected else None,
        "acknowledged": bool(a.acknowledged),
        "acknowledged_at": as_ist(a.acknowledged_at).isoformat() if a.acknowledged_at else None,
        "response_time_ms": a.response_time_ms,
        "escalated_at": as_ist(a.escalated_at).isoformat() if a.escalated_at else None,
    }


def _messages(event: str, a: AlertLog, driver_name: str) -> Dict[str, str]:
    t = as_ist(a.detected_at).strftime("%H:%M") if a.detected_at else ""
    first = first_name(driver_name)
    level = a.level or 0
    if event == "acknowledged":
        secs = f"{(a.response_time_ms or 0) / 1000:.1f}"
        return {
            "driver": f"Acknowledged in {secs} s. Stay safe and consider a break.",
            "fleet": f"{driver_name} acknowledged the level {level} alert in {secs} s.",
            "spoken": "",
        }
    if event == "resolved":
        return {"driver": "Alert cleared.", "fleet": f"{driver_name}'s level 1 alert cleared.", "spoken": ""}
    if level >= 3:
        return {
            "driver": "Your fleet manager has been notified.",
            "fleet": f"{driver_name} has not responded to a drowsiness alert since {t} IST.",
            "spoken": f"{first}, wake up. Your fleet manager has been notified. Please pull over now.",
        }
    if level == 2:
        return {
            "driver": f"You seem drowsy ({t} IST). Please pull over and take a break.",
            "fleet": f"{driver_name} is drowsy (level 2) at {t} IST.",
            "spoken": f"{first}, you seem drowsy. Please pull over and take a break.",
        }
    why = "Yawning detected" if a.reason == "yawn" else "Eyes closing"
    return {
        "driver": f"{why} at {t} IST. Stay focused.",
        "fleet": f"{driver_name}: {why.lower()} (level 1) at {t} IST.",
        "spoken": "",
    }


class AlertingService:
    def __init__(self) -> None:
        self._policies: Dict[str, AlertLevelPolicy] = {}
        self._open: Dict[str, OpenAlert] = {}
        self.clock: Callable[[], float] = time.time

    # ---- state -----------------------------------------------------------

    def reset(self) -> None:
        self._policies.clear()
        self._open.clear()

    def policy(self, driver_id: str) -> AlertLevelPolicy:
        p = self._policies.get(driver_id)
        if p is None:
            p = AlertLevelPolicy(cfg=LevelConfig.from_settings(get_settings()))
            self._policies[driver_id] = p
        return p

    def open_alert(self, driver_id: str) -> Optional[OpenAlert]:
        return self._open.get(driver_id)

    def current(self, driver_id: str) -> Dict[str, Any]:
        """Severity and alert the Pi/app should be reacting to right now."""
        oa = self._open.get(driver_id)
        if oa and oa.status in OPEN_STATUSES:
            return {"severity": oa.level, "alert_id": oa.id, "alert_status": oa.status}
        return {"severity": 0, "alert_id": None, "alert_status": None}

    # ---- frames ----------------------------------------------------------

    async def handle_observation(
        self,
        ops_session: Session,
        driver_id: str,
        driver_name: str,
        fleet_id: Optional[str],
        obs: Observation,
        source: str,
        device_id: Optional[str] = None,
        frame_id: Optional[str] = None,
    ) -> Decision:
        decision = self.policy(driver_id).observe(obs)
        oa = self._open.get(driver_id)

        if decision.event is not None:
            if oa and oa.status in OPEN_STATUSES and oa.level >= 2:
                pass  # an unacknowledged L2/L3 is still ringing; this episode belongs to it
            elif decision.event == "new" or oa is None or oa.status not in OPEN_STATUSES:
                await self._raise(ops_session, driver_id, driver_name, fleet_id, decision, obs, source, device_id, frame_id)
            else:
                await self._upgrade(ops_session, oa, decision, frame_id)
        elif oa and oa.level == 1 and oa.status == "active" and not self.policy(driver_id).episode_active:
            await self._resolve_l1(ops_session, oa, frame_id)

        return decision

    async def _raise(self, ops_session, driver_id, driver_name, fleet_id, decision: Decision,
                     obs: Observation, source, device_id, frame_id) -> None:
        now = self.clock()
        level = decision.level
        a = AlertLog(
            driver_id=driver_id,
            fleet_id=fleet_id,
            type="yawning" if decision.reason == "yawn" else "drowsy",
            severity=LEVEL_SEVERITY[level],
            confidence=1.0,
            ear=round(obs.ear, 3),
            mar=round(obs.mar, 3),
            perclos=0.0,
            source=source if source in ("webcam", "pi", "simulated") else "webcam",
            detected_at=ist_wall_now(),
            acknowledged=False,
            level=level,
            status="active",
            reason=decision.reason,
            device_id=device_id,
            frame_id=frame_id,
        )
        ops_session.add(a)
        ops_session.commit()
        ops_session.refresh(a)
        self._open[driver_id] = OpenAlert(
            id=a.id, driver_id=driver_id, driver_name=driver_name, fleet_id=fleet_id,
            level=level, status="active", raised_ts=now, l2_ts=now if level >= 2 else None,
        )
        logger.info(f"Alert L{level} raised for {driver_name} ({decision.reason}) id={a.id}")
        self._laptop_alarm(level)
        await self._broadcast("raised", a, driver_name, fleet_id, frame_id)

    async def _upgrade(self, ops_session, oa: OpenAlert, decision: Decision, frame_id) -> None:
        a = ops_session.query(AlertLog).filter(AlertLog.id == oa.id).first()
        if a is None:
            self._open.pop(oa.driver_id, None)
            return
        a.level = decision.level
        a.severity = LEVEL_SEVERITY[decision.level]
        a.reason = decision.reason
        if decision.reason in ("eyes_closed", "repeated_l1"):
            a.type = "drowsy"
        ops_session.commit()
        oa.level = decision.level
        if decision.level >= 2 and oa.l2_ts is None:
            oa.l2_ts = self.clock()
        logger.info(f"Alert {oa.id} upgraded to L{decision.level}")
        self._laptop_alarm(decision.level)
        await self._broadcast("upgraded", a, oa.driver_name, oa.fleet_id, frame_id)

    async def _resolve_l1(self, ops_session, oa: OpenAlert, frame_id) -> None:
        a = ops_session.query(AlertLog).filter(AlertLog.id == oa.id).first()
        self._open.pop(oa.driver_id, None)
        if a is None:
            return
        a.status = "resolved"
        ops_session.commit()
        await self._broadcast("resolved", a, oa.driver_name, oa.fleet_id, frame_id)

    # ---- level 3 watchdog ------------------------------------------------

    async def check_escalations(self, ops_session_factory, now: Optional[float] = None) -> int:
        """Escalate every level-2 alert left unacknowledged for ACK_TIMEOUT_SECONDS."""
        now = now if now is not None else self.clock()
        timeout = get_settings().ACK_TIMEOUT_SECONDS
        due = [
            oa for oa in self._open.values()
            if oa.level == 2 and oa.status == "active" and oa.l2_ts is not None and now - oa.l2_ts >= timeout
        ]
        if not due:
            return 0
        db = ops_session_factory()
        try:
            for oa in due:
                a = db.query(AlertLog).filter(AlertLog.id == oa.id).first()
                if a is None or a.acknowledged:
                    self._open.pop(oa.driver_id, None)
                    continue
                a.level = 3
                a.severity = LEVEL_SEVERITY[3]
                a.status = "unacknowledged"
                a.escalated_at = ist_wall_now()
                db.commit()
                oa.level, oa.status = 3, "unacknowledged"
                logger.warning(f"Alert {oa.id} escalated to L3: {oa.driver_name} did not acknowledge in {timeout:.0f}s")
                await self._broadcast("escalated", a, oa.driver_name, oa.fleet_id, None)
        finally:
            db.close()
        return len(due)

    # ---- acknowledgement -------------------------------------------------

    async def acknowledge(
        self,
        ops_session: Session,
        a: AlertLog,
        driver_name: str,
        acknowledged_by: Optional[str] = None,
    ) -> AlertLog:
        """Driver tapped "I'm awake" (or their fleet manager cleared it). Idempotent.

        response_time_ms is only recorded for the driver's own acknowledgement.
        """
        if a.acknowledged:
            return a
        now = self.clock()
        oa = self._open.get(a.driver_id)
        if acknowledged_by is None:
            if oa and oa.id == a.id:
                # Measured from when the alert first demanded acknowledgement
                # (reached level 2), or from raise time if acknowledged at level 1.
                started = oa.l2_ts or oa.raised_ts
                a.response_time_ms = round((now - started) * 1000.0, 1)
            else:
                detected = as_ist(a.detected_at)
                if detected is not None:
                    a.response_time_ms = round((now - detected.timestamp()) * 1000.0, 1)
        a.acknowledged = True
        a.acknowledged_by = acknowledged_by or driver_name
        a.acknowledged_at = ist_wall_now()
        a.status = "acknowledged"
        ops_session.commit()
        ops_session.refresh(a)

        if oa and oa.id == a.id:
            self._open.pop(a.driver_id, None)
            self.policy(a.driver_id).acknowledge(now)
        logger.info(f"Alert {a.id} acknowledged by {a.acknowledged_by} ({a.response_time_ms} ms)")
        await self._broadcast("acknowledged", a, driver_name, a.fleet_id, None)
        return a

    # ---- helpers ---------------------------------------------------------

    async def _broadcast(self, event: str, a: AlertLog, driver_name: str, fleet_id: Optional[str],
                         frame_id: Optional[str]) -> None:
        msgs = _messages(event, a, driver_name)
        alert = serialize_alert(a, driver_name)
        base = {
            "type": "alert_event",
            "event": event,
            "driver_id": a.driver_id,
            "driver_name": driver_name,
            "level": a.level,
            "alert": alert,
            "frame_id": frame_id,
            "server_ts_ms": round(now_ms(), 1),
            "timestamp": alert["detected_at"],
            "timestamp_ist": alert["time_ist"],
        }
        driver_payload = {**base, "message": msgs["driver"], "spoken": msgs["spoken"]}
        fleet_payload = {**base, "message": msgs["fleet"]}
        await manager.send_scoped(a.driver_id, fleet_id, driver_payload, fleet_payload)
        latency_logger.mark(frame_id, ws_sent_ms=now_ms(), alert_id=a.id, level=a.level)

    def _laptop_alarm(self, level: int) -> None:
        if level >= 2 and get_settings().LAPTOP_ALARM_ENABLED:
            from server.app.services.alert_service import play_laptop_alarm
            play_laptop_alarm()


alerting_service = AlertingService()

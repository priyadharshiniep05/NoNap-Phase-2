"""Ops database SQLAlchemy models (DB2: thresholds, alerts, stats)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Float, Boolean, Integer, DateTime, Enum as SAEnum
from sqlalchemy.orm import declarative_base

OpsBase = declarative_base()


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Threshold(OpsBase):
    __tablename__ = "thresholds"

    id = Column(String, primary_key=True, default=_uuid)
    scope = Column(SAEnum("global", "fleet", "user", name="threshold_scope"), nullable=False)
    fleet_id = Column(String, nullable=True)
    user_id = Column(String, nullable=True)
    ear_threshold = Column(Float, default=0.21)
    mar_threshold = Column(Float, default=0.60)
    perclos_threshold = Column(Float, default=0.40)
    eyes_closed_seconds = Column(Float, default=1.5)
    alert_cooldown_seconds = Column(Float, default=30.0)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class AlertLog(OpsBase):
    __tablename__ = "alert_logs"

    id = Column(String, primary_key=True, default=_uuid)
    driver_id = Column(String, nullable=False, index=True)
    fleet_id = Column(String, nullable=True)
    type = Column(SAEnum("drowsy", "yawning", "accident", "no_face", name="alert_type"), nullable=False)
    severity = Column(SAEnum("low", "medium", "high", "critical", name="alert_severity"), nullable=False)
    confidence = Column(Float, default=0.0)
    ear = Column(Float, default=0.0)
    mar = Column(Float, default=0.0)
    perclos = Column(Float, default=0.0)
    source = Column(SAEnum("webcam", "pi", "simulated", name="alert_source"), default="webcam")
    detected_at = Column(DateTime, default=_utcnow)
    acknowledged = Column(Boolean, default=False)
    acknowledged_by = Column(String, nullable=True)

    # Level-based alerting (migration 0001_alert_levels)
    level = Column(Integer, nullable=True)  # 1-3; NULL for legacy / SOS rows
    status = Column(String, nullable=True)  # active | acknowledged | unacknowledged | resolved
    reason = Column(String, nullable=True)  # eyes_closed | yawn | repeated_l1
    acknowledged_at = Column(DateTime, nullable=True)
    response_time_ms = Column(Float, nullable=True)
    escalated_at = Column(DateTime, nullable=True)
    device_id = Column(String, nullable=True)
    frame_id = Column(String, nullable=True)


class SessionStat(OpsBase):
    __tablename__ = "session_stats"

    id = Column(String, primary_key=True, default=_uuid)
    driver_id = Column(String, nullable=False, index=True)
    started_at = Column(DateTime, default=_utcnow)
    ended_at = Column(DateTime, nullable=True)
    frames_processed = Column(Integer, default=0)
    alert_count = Column(Integer, default=0)


class Device(OpsBase):
    """A capture device (Raspberry Pi) bound to a driver. Liveness comes from heartbeats and frames."""

    __tablename__ = "devices"

    id = Column(String, primary_key=True)  # device_id from pi_client/config.ini
    driver_id = Column(String, nullable=True, index=True)
    vehicle = Column(String, nullable=True)
    ip = Column(String, nullable=True)
    camera_backend = Column(String, nullable=True)
    fps = Column(Float, nullable=True)
    cpu_temp_c = Column(Float, nullable=True)
    uptime_s = Column(Float, nullable=True)
    rtt_ms = Column(Float, nullable=True)
    last_seen_at = Column(DateTime, nullable=True)  # UTC
    created_at = Column(DateTime, default=_utcnow)

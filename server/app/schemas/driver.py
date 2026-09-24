"""Pydantic schemas for driver dashboard."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from server.app.schemas.ops import AlertLogResponse, ThresholdResponse


class DriverProfileResponse(BaseModel):
    id: str
    full_name: str
    email: str
    role: str
    fleet_id: Optional[str] = None
    fleet_name: Optional[str] = None
    created_at: Optional[datetime] = None


class DriverStatsResponse(BaseModel):
    driver_id: str
    total_alerts: int
    drowsy_alerts: int
    yawn_alerts: int
    accident_alerts: int
    alerts_today: int
    last_alert_time: Optional[datetime] = None
    current_status: str = "alert"  # alert, drowsy, yawning, no_face

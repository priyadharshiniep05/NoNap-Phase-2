"""Pydantic schemas for fleet management dashboard."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class FleetDriverSummary(BaseModel):
    driver_id: str
    full_name: str
    email: str
    is_active: bool
    current_status: str = "alert"  # alert, drowsy, yawning, offline, no_face
    last_alert_at: Optional[datetime] = None
    alerts_today: int = 0
    perclos: float = 0.0
    ear: float = 0.0


class FleetOverviewResponse(BaseModel):
    fleet_id: str
    fleet_name: str
    total_drivers: int
    active_drivers: int
    drowsy_count_today: int
    yawn_count_today: int
    critical_alerts_today: int
    drivers: List[FleetDriverSummary] = []


class FleetCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)


class FleetDriverAssignRequest(BaseModel):
    driver_id: str

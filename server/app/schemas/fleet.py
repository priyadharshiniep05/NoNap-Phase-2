"""Pydantic schemas for fleet management dashboard."""

from datetime import datetime
from typing import Any, Dict, Optional, List
from pydantic import BaseModel, Field, field_serializer

from server.app.core.timezone import as_ist


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
    online: bool = False
    device_id: Optional[str] = None
    device_online: bool = False
    vehicle: Optional[str] = None
    fps: Optional[float] = None
    cpu_temp_c: Optional[float] = None
    active_alert: Optional[Dict[str, Any]] = None
    avg_response_ms: Optional[float] = None

    @field_serializer("last_alert_at")
    def _ser_ist(self, dt: Optional[datetime]):
        return as_ist(dt).isoformat() if dt else None


class FleetOverviewResponse(BaseModel):
    fleet_id: str
    fleet_name: str
    total_drivers: int
    active_drivers: int
    drowsy_count_today: int
    yawn_count_today: int
    critical_alerts_today: int
    drivers_online: int = 0
    active_alerts: int = 0
    alerts_today: int = 0
    avg_response_ms_today: Optional[float] = None
    drivers: List[FleetDriverSummary] = []


class FleetCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)


class FleetDriverAssignRequest(BaseModel):
    driver_id: str

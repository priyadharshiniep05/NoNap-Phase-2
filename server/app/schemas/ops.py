"""Pydantic schemas for operational database models (thresholds, alerts, session stats)."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ThresholdResponse(BaseModel):
    id: str
    scope: str
    fleet_id: Optional[str] = None
    user_id: Optional[str] = None
    ear_threshold: float
    mar_threshold: float
    perclos_threshold: float
    eyes_closed_seconds: float
    alert_cooldown_seconds: float
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ThresholdUpdateRequest(BaseModel):
    ear_threshold: Optional[float] = Field(None, ge=0.05, le=0.5)
    mar_threshold: Optional[float] = Field(None, ge=0.2, le=1.5)
    perclos_threshold: Optional[float] = Field(None, ge=0.1, le=1.0)
    eyes_closed_seconds: Optional[float] = Field(None, ge=0.5, le=10.0)
    alert_cooldown_seconds: Optional[float] = Field(None, ge=5.0, le=300.0)


class AlertLogResponse(BaseModel):
    id: str
    driver_id: str
    driver_name: Optional[str] = None
    fleet_id: Optional[str] = None
    type: str
    severity: str
    confidence: float
    ear: float
    mar: float
    perclos: float
    source: str
    detected_at: datetime
    acknowledged: bool
    acknowledged_by: Optional[str] = None

    model_config = {"from_attributes": True}


class AlertAcknowledgeRequest(BaseModel):
    acknowledged_by: Optional[str] = None


class SessionStatResponse(BaseModel):
    id: str
    driver_id: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    frames_processed: int
    alert_count: int

    model_config = {"from_attributes": True}

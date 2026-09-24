"""Pydantic schemas for detection and real-time streaming."""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class DetectFrameRequest(BaseModel):
    driver_id: str
    frame_b64: Optional[str] = None
    timestamp: Optional[float] = None
    source: str = "pi"  # webcam, pi, simulated


class DetectionResultResponse(BaseModel):
    driver_id: str
    status: str  # alert, drowsy, yawning, no_face
    severity: str  # low, medium, high, critical
    confidence: float
    ear: float
    mar: float
    perclos: float
    eyes_closed_seconds: float
    alert_triggered: bool
    alert_type: Optional[str] = None
    alert_message: Optional[str] = None
    timestamp: float
    backend: str = "baseline"


class DevSimulateRequest(BaseModel):
    driver_id: str
    event: str = Field(..., pattern="^(alert|drowsy|yawning|accident|no_face)$")
    severity: str = Field("high", pattern="^(low|medium|high|critical)$")
    confidence: float = 0.95
    ear: float = 0.12
    mar: float = 0.75
    perclos: float = 0.55

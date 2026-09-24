"""WebSocket message schemas."""

from typing import Dict, Any, Optional
from pydantic import BaseModel


class WSMessage(BaseModel):
    type: str  # telemetry, alert, connection_ack, ping, pong, status_update
    driver_id: str
    driver_name: str
    status: str  # alert, drowsy, yawning, accident, no_face
    severity: str  # low, medium, high, critical
    confidence: float
    metrics: Dict[str, Any]
    timestamp: str  # ISO-8601 or HH:mm:ss
    message: str

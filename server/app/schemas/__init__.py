"""Schemas package for NoNap."""

from server.app.schemas.auth import (
    UserSignupRequest,
    UserLoginRequest,
    TokenResponse,
    TokenRefreshRequest,
    UserResponse,
)
from server.app.schemas.ops import (
    ThresholdResponse,
    ThresholdUpdateRequest,
    AlertLogResponse,
    AlertAcknowledgeRequest,
    SessionStatResponse,
)
from server.app.schemas.driver import (
    DriverProfileResponse,
    DriverStatsResponse,
)
from server.app.schemas.fleet import (
    FleetOverviewResponse,
    FleetDriverSummary,
    FleetCreateRequest,
    FleetDriverAssignRequest,
)
from server.app.schemas.detection import (
    DetectFrameRequest,
    DetectionResultResponse,
    DevSimulateRequest,
)
from server.app.schemas.ws import WSMessage

__all__ = [
    "UserSignupRequest",
    "UserLoginRequest",
    "TokenResponse",
    "TokenRefreshRequest",
    "UserResponse",
    "ThresholdResponse",
    "ThresholdUpdateRequest",
    "AlertLogResponse",
    "AlertAcknowledgeRequest",
    "SessionStatResponse",
    "DriverProfileResponse",
    "DriverStatsResponse",
    "FleetOverviewResponse",
    "FleetDriverSummary",
    "FleetCreateRequest",
    "FleetDriverAssignRequest",
    "DetectFrameRequest",
    "DetectionResultResponse",
    "DevSimulateRequest",
    "WSMessage",
]

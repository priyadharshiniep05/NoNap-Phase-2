"""Server application configuration loaded from environment variables."""

import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from .env file and environment variables."""

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True

    # Database URLs
    AUTH_DB_URL: str = "sqlite:///server/data/auth.db"
    OPS_DB_URL: str = "sqlite:///server/data/ops.db"

    # JWT
    JWT_SECRET_KEY: str = "nonap_phase2_dev_secret_key_change_in_production_m4_mac"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Detection
    DETECTOR_BACKEND: str = "auto"
    WEBCAM_INDEX: int = 0
    WEBCAM_FPS: int = 10

    # Frame source feeding the detection pipeline: "pi" (frames POSTed to
    # /api/v1/frames by the Raspberry Pi) or "webcam" (MacBook webcam worker).
    VIDEO_SOURCE: str = "pi"

    # Shared secret the Pi (and tools/simulate_pi.py) send as X-Device-Key.
    DEVICE_API_KEY: str = "nonap-dev-device-key"
    # A device is offline when no heartbeat or frame arrived for this long.
    DEVICE_OFFLINE_SECONDS: float = 12.0

    # Alert level timing (seconds). Time windows, not frame counts.
    L1_EYES_LOW_SECONDS: float = 1.0
    L2_EYES_LOW_SECONDS: float = 2.0
    YAWN_MIN_SECONDS: float = 1.0
    L1_REPEAT_COUNT: int = 3
    L1_REPEAT_WINDOW_SECONDS: float = 60.0
    ACK_TIMEOUT_SECONDS: float = 10.0
    EPISODE_END_SECONDS: float = 1.5
    ALERT_COOLDOWN_SECONDS: float = 5.0
    MAX_FRAME_GAP_SECONDS: float = 1.5
    # Live EAR/MAR telemetry rate on the WebSocket.
    TELEMETRY_HZ: float = 2.0

    # Play a macOS system sound on the MacBook for level >= 2 alerts.
    LAPTOP_ALARM_ENABLED: bool = False

    # Latency instrumentation CSVs (logs/latency_<date>.csv)
    LATENCY_LOG_DIR: str = "logs"

    # Integrations
    CONTROL_CENTER_WEBHOOK_URL: str = "http://localhost:8000/mock/webhook"
    FCM_ENABLED: bool = False

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return cached Settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

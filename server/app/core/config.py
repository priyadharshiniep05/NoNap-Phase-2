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

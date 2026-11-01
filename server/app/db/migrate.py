"""Run DB2 Alembic migrations programmatically on server startup."""

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config

from server.app.db.ops_db import get_ops_engine

logger = logging.getLogger("nonap.migrate")

_SERVER_DIR = Path(__file__).resolve().parents[2]


def upgrade_ops_db() -> None:
    """Bring ops_db to the latest Alembic revision using the app's own engine."""
    cfg = Config(str(_SERVER_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(_SERVER_DIR / "migrations"))
    with get_ops_engine().begin() as connection:
        cfg.attributes["connection"] = connection
        command.upgrade(cfg, "head")
    logger.info("ops_db migrations at head.")

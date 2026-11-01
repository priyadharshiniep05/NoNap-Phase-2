"""Alembic environment for DB2 (ops_db).

Uses a connection passed in via config.attributes["connection"] when the server
runs migrations on startup; otherwise connects to OPS_DB_URL from settings.
"""

from alembic import context
from sqlalchemy import create_engine

from server.app.core.config import get_settings
from server.app.db.models_ops import OpsBase

config = context.config
target_metadata = OpsBase.metadata


def _run(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


connection = config.attributes.get("connection")
if connection is not None:
    _run(connection)
else:
    engine = create_engine(get_settings().OPS_DB_URL)
    with engine.connect() as conn:
        _run(conn)

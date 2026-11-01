"""Alert levels, acknowledgement timing, and device registry (DB2).

Idempotent: databases created by create_all() after this change already have
these columns/tables, older ops.db files get them added here.

Revision ID: 0001_alert_levels
Revises:
Create Date: 2026-10-21
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_alert_levels"
down_revision = None
branch_labels = None
depends_on = None

ALERT_COLUMNS = [
    sa.Column("level", sa.Integer(), nullable=True),
    sa.Column("status", sa.String(), nullable=True),
    sa.Column("reason", sa.String(), nullable=True),
    sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
    sa.Column("response_time_ms", sa.Float(), nullable=True),
    sa.Column("escalated_at", sa.DateTime(), nullable=True),
    sa.Column("device_id", sa.String(), nullable=True),
    sa.Column("frame_id", sa.String(), nullable=True),
]


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = inspector.get_table_names()

    if "alert_logs" in tables:
        existing = {c["name"] for c in inspector.get_columns("alert_logs")}
        missing = [c for c in ALERT_COLUMNS if c.name not in existing]
        if missing:
            with op.batch_alter_table("alert_logs") as batch:
                for col in missing:
                    batch.add_column(col)

    if "devices" not in tables:
        op.create_table(
            "devices",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("driver_id", sa.String(), nullable=True, index=True),
            sa.Column("vehicle", sa.String(), nullable=True),
            sa.Column("ip", sa.String(), nullable=True),
            sa.Column("camera_backend", sa.String(), nullable=True),
            sa.Column("fps", sa.Float(), nullable=True),
            sa.Column("cpu_temp_c", sa.Float(), nullable=True),
            sa.Column("uptime_s", sa.Float(), nullable=True),
            sa.Column("rtt_ms", sa.Float(), nullable=True),
            sa.Column("last_seen_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    op.drop_table("devices")
    with op.batch_alter_table("alert_logs") as batch:
        for col in ALERT_COLUMNS:
            batch.drop_column(col.name)

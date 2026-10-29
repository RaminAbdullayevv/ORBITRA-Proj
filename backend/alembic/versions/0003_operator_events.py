"""Persist local operator actions.

Revision ID: 0003_operator_events
Revises: 0002_telemetry
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_operator_events"
down_revision = "0002_telemetry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "operator_events",
        sa.Column("event_number", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.String(36), nullable=False, unique=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("simulation_runs.run_id"), nullable=True),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("received_at", sa.String(40), nullable=False),
        sa.Column("simulation_elapsed_seconds", sa.Integer(), nullable=False),
        sa.Column("before_status", sa.String(16), nullable=False),
        sa.Column("after_status", sa.String(16), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("reason", sa.String(240), nullable=False),
        sa.Column("source", sa.String(40), nullable=False),
    )
    op.create_index("ix_operator_events_run_number", "operator_events", ["run_id", "event_number"])


def downgrade() -> None:
    op.drop_index("ix_operator_events_run_number", table_name="operator_events")
    op.drop_table("operator_events")

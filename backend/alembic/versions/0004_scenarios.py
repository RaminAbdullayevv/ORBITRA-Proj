"""Persist Stage 5 scenarios, rule alerts, and rejected test packets.

Revision ID: 0004_scenarios
Revises: 0003_operator_events
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_scenarios"
down_revision = "0003_operator_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("simulation_runs") as batch:
        batch.add_column(sa.Column("scenario", sa.String(32), nullable=False, server_default="NORMAL_MISSION"))
    op.create_table(
        "rule_alerts",
        sa.Column("alert_id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("simulation_runs.run_id"), nullable=False),
        sa.Column("rule_code", sa.String(40), nullable=False),
        sa.Column("opened_at", sa.String(40), nullable=False),
        sa.Column("closed_at", sa.String(40), nullable=True),
        sa.Column("reason", sa.String(240), nullable=False),
        sa.Column("metric_key", sa.String(40), nullable=False),
        sa.Column("metric_value", sa.Float(), nullable=False),
        sa.Column("resolved_value", sa.Float(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
    )
    op.create_index("ix_rule_alerts_run_opened", "rule_alerts", ["run_id", "opened_at"])
    op.create_table(
        "rejected_telemetry",
        sa.Column("rejection_id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("simulation_runs.run_id"), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("rejected_at", sa.String(40), nullable=False),
        sa.Column("schema_version", sa.String(40), nullable=False),
        sa.Column("reason", sa.String(240), nullable=False),
        sa.UniqueConstraint("run_id", "sequence_number", name="uq_rejected_run_sequence"),
    )
    op.create_index("ix_rejected_run_time", "rejected_telemetry", ["run_id", "rejected_at"])


def downgrade() -> None:
    op.drop_index("ix_rejected_run_time", table_name="rejected_telemetry")
    op.drop_table("rejected_telemetry")
    op.drop_index("ix_rule_alerts_run_opened", table_name="rule_alerts")
    op.drop_table("rule_alerts")
    with op.batch_alter_table("simulation_runs") as batch:
        batch.drop_column("scenario")

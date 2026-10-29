"""Persist local simulation runs and telemetry samples.

Revision ID: 0002_telemetry
Revises: 0001_initial
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_telemetry"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "simulation_runs",
        sa.Column("run_id", sa.String(36), primary_key=True),
        sa.Column("started_at", sa.String(40), nullable=False),
        sa.Column("last_status", sa.String(16), nullable=False),
        sa.Column("ended_at", sa.String(40), nullable=True),
    )
    op.create_table(
        "telemetry_samples",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("simulation_runs.run_id"), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("simulation_elapsed_seconds", sa.Integer(), nullable=False),
        sa.Column("sample_time", sa.String(40), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("battery_level_percent", sa.Float(), nullable=False),
        sa.Column("voltage_v", sa.Float(), nullable=False),
        sa.Column("current_a", sa.Float(), nullable=False),
        sa.Column("temperature_1_c", sa.Float(), nullable=False),
        sa.Column("temperature_2_c", sa.Float(), nullable=False),
        sa.Column("temperature_3_c", sa.Float(), nullable=False),
        sa.Column("cpu_load_percent", sa.Float(), nullable=False),
        sa.Column("memory_usage_percent", sa.Float(), nullable=False),
        sa.Column("signal_strength_percent", sa.Float(), nullable=False),
        sa.Column("communication_latency_ms", sa.Float(), nullable=False),
        sa.Column("packet_loss_percent", sa.Float(), nullable=False),
        sa.UniqueConstraint("run_id", "sequence_number", name="uq_telemetry_run_sequence"),
    )


def downgrade() -> None:
    op.drop_table("telemetry_samples")
    op.drop_table("simulation_runs")

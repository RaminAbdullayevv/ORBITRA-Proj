"""Persist trusted model metadata and deduplicated AI anomaly events.

Revision ID: 0005_ai_analysis
Revises: 0004_scenarios
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_ai_analysis"
down_revision = "0004_scenarios"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_model_versions",
        sa.Column("version", sa.String(64), primary_key=True),
        sa.Column("trained_at", sa.String(40), nullable=False),
        sa.Column("training_summary", sa.Text(), nullable=False),
        sa.Column("artifact_sha256", sa.String(64), nullable=False),
        sa.Column("score_threshold", sa.Float(), nullable=False),
    )
    op.create_table(
        "ai_events",
        sa.Column("event_id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("simulation_runs.run_id"), nullable=False),
        sa.Column("model_version", sa.String(64), sa.ForeignKey("ai_model_versions.version"), nullable=False),
        sa.Column("started_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.Column("ended_at", sa.String(40), nullable=True),
        sa.Column("start_sequence_number", sa.Integer(), nullable=False),
        sa.Column("latest_sequence_number", sa.Integer(), nullable=False),
        sa.Column("window_start_sequence_number", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("affected_sensors", sa.Text(), nullable=False),
        sa.Column("baseline_comparison", sa.Text(), nullable=False),
        sa.Column("explanation", sa.String(600), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
    )
    op.create_index("ix_ai_events_run_start", "ai_events", ["run_id", "start_sequence_number"])


def downgrade() -> None:
    op.drop_index("ix_ai_events_run_start", table_name="ai_events")
    op.drop_table("ai_events")
    op.drop_table("ai_model_versions")

"""Persist per-run AI evaluation proof and report generation metadata.

Revision ID: 0007_reports
Revises: 0006_security
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_reports"
down_revision = "0006_security"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "run_analysis",
        sa.Column("run_id", sa.String(36), sa.ForeignKey("simulation_runs.run_id"), primary_key=True),
        sa.Column("model_version", sa.String(64), nullable=False),
        sa.Column("last_evaluated_at", sa.String(40), nullable=False),
        sa.Column("latest_sequence_number", sa.Integer(), nullable=False),
    )
    op.create_table(
        "report_generations",
        sa.Column("run_id", sa.String(36), sa.ForeignKey("simulation_runs.run_id"), primary_key=True),
        sa.Column("generated_at", sa.String(40), nullable=False),
        sa.Column("rules_version", sa.String(40), nullable=False),
        sa.Column("model_version", sa.String(64), nullable=True),
    )
    # Existing confirmed AI events prove at least one evaluated window.
    op.execute(sa.text("""
        INSERT INTO run_analysis (run_id, model_version, last_evaluated_at, latest_sequence_number)
        SELECT e.run_id, e.model_version, e.updated_at, e.latest_sequence_number
        FROM ai_events e
        WHERE e.event_id = (
            SELECT e2.event_id FROM ai_events e2 WHERE e2.run_id = e.run_id
            ORDER BY e2.updated_at DESC, e2.event_id DESC LIMIT 1
        )
    """))


def downgrade() -> None:
    op.drop_table("report_generations")
    op.drop_table("run_analysis")

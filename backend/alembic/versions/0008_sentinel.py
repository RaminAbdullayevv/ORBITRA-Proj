"""Persist packet trust decisions and extend the existing rejection quarantine.

Revision ID: 0008_sentinel
Revises: 0007_reports
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_sentinel"
down_revision = "0007_reports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("rejected_telemetry") as batch:
        batch.add_column(sa.Column("packet_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("raw_payload_json", sa.Text(), nullable=True))
        batch.add_column(sa.Column("signature_status", sa.String(16), nullable=True))
        batch.add_column(sa.Column("packet_timestamp", sa.String(40), nullable=True))
        batch.add_column(sa.Column("incident_id", sa.String(36), nullable=True))
    op.create_table(
        "telemetry_trust_assessments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("mission_id", sa.String(36), sa.ForeignKey("simulation_runs.run_id"), nullable=False),
        sa.Column("packet_id", sa.String(36), nullable=False),
        sa.Column("device_id", sa.String(64), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("received_at", sa.String(40), nullable=False),
        sa.Column("schema_valid", sa.Boolean(), nullable=False),
        sa.Column("source_valid", sa.Boolean(), nullable=True),
        sa.Column("signature_valid", sa.Boolean(), nullable=True),
        sa.Column("replay_detected", sa.Boolean(), nullable=True),
        sa.Column("freshness_valid", sa.Boolean(), nullable=True),
        sa.Column("cross_sensor_status", sa.String(24), nullable=False),
        sa.Column("digital_twin_status", sa.String(24), nullable=False),
        sa.Column("final_verdict", sa.String(40), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("explanation", sa.String(600), nullable=False),
        sa.Column("evidence_json", sa.Text(), nullable=False),
        sa.Column("ruleset_version", sa.String(40), nullable=False),
        sa.Column("model_version", sa.String(64), nullable=True),
        sa.Column("processing_time_ms", sa.Float(), nullable=False),
        sa.Column("accepted", sa.Boolean(), nullable=False),
        sa.Column("incident_id", sa.String(36), nullable=True),
    )
    op.create_index("ix_trust_mission_id", "telemetry_trust_assessments", ["mission_id", "id"])


def downgrade() -> None:
    op.drop_index("ix_trust_mission_id", table_name="telemetry_trust_assessments")
    op.drop_table("telemetry_trust_assessments")
    with op.batch_alter_table("rejected_telemetry") as batch:
        for name in ("incident_id", "packet_timestamp", "signature_status", "raw_payload_json", "packet_id"):
            batch.drop_column(name)

"""Preserve the former Device application's run, dispatch and audit history in Main.

Revision ID: 0009_unified_device_history
Revises: 0008_sentinel
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_unified_device_history"
down_revision = "0008_sentinel"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("device_run_history",
        sa.Column("run_id", sa.String(36), primary_key=True),
        sa.Column("scenario", sa.String(32), nullable=False),
        sa.Column("started_at", sa.String(40), nullable=False),
        sa.Column("last_status", sa.String(16), nullable=False),
        sa.Column("ended_at", sa.String(40), nullable=True))
    op.create_table("device_dispatch_history",
        sa.Column("legacy_id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.String(36), nullable=True),
        sa.Column("sequence_number", sa.Integer(), nullable=True),
        sa.Column("packet_id", sa.String(36), nullable=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("sent_at", sa.String(40), nullable=False),
        sa.Column("result", sa.String(24), nullable=False),
        sa.Column("reason_code", sa.String(40), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True))
    op.create_index("ix_device_dispatch_run", "device_dispatch_history", ["run_id", "sent_at"])
    op.create_table("device_audit_history",
        sa.Column("legacy_id", sa.Integer(), primary_key=True),
        sa.Column("occurred_at", sa.String(40), nullable=False),
        sa.Column("username", sa.String(64), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("outcome", sa.String(24), nullable=False),
        sa.Column("reason_code", sa.String(40), nullable=False),
        sa.Column("run_id", sa.String(36), nullable=True),
        sa.Column("sequence_number", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_table("device_audit_history")
    op.drop_index("ix_device_dispatch_run", table_name="device_dispatch_history")
    op.drop_table("device_dispatch_history")
    op.drop_table("device_run_history")

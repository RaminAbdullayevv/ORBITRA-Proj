"""Add local accounts, sessions, signed packet provenance, incidents and audit.

Revision ID: 0006_security
Revises: 0005_ai_analysis
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_security"
down_revision = "0005_ai_analysis"
branch_labels = None
depends_on = None


def _table(name: str, *columns) -> None:
    if not sa.inspect(op.get_bind()).has_table(name):
        op.create_table(name, *columns)


def _index(name: str, table: str, columns: list[str], unique: bool = False) -> None:
    existing = {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table)}
    if name not in existing:
        op.create_index(name, table, columns, unique=unique)


def upgrade() -> None:
    _table(
        "users", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
    )
    _table(
        "user_sessions", sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("expires_at", sa.String(40), nullable=False),
        sa.Column("revoked_at", sa.String(40), nullable=True),
    )
    _index("ix_user_sessions_user", "user_sessions", ["user_id"])
    _table(
        "audit_events", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("occurred_at", sa.String(40), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("username", sa.String(64), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("outcome", sa.String(24), nullable=False),
        sa.Column("reason_code", sa.String(40), nullable=False),
        sa.Column("run_id", sa.String(36), nullable=True),
        sa.Column("incident_id", sa.String(36), nullable=True),
        sa.Column("sequence_number", sa.Integer(), nullable=True),
    )
    _index("ix_audit_events_time", "audit_events", ["occurred_at"])
    _table(
        "security_incidents", sa.Column("incident_id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("reason_code", sa.String(40), nullable=False),
        sa.Column("summary", sa.String(240), nullable=False),
        sa.Column("run_id", sa.String(36), nullable=True),
        sa.Column("source_id", sa.String(64), nullable=True),
        sa.Column("sequence_number", sa.Integer(), nullable=True),
        sa.Column("closed_at", sa.String(40), nullable=True),
        sa.Column("closed_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("close_reason", sa.String(500), nullable=True),
    )
    _index("ix_security_incidents_time", "security_incidents", ["created_at"])
    _table(
        "incident_notes", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("incident_id", sa.String(36), sa.ForeignKey("security_incidents.incident_id"), nullable=False),
        sa.Column("author_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("body", sa.String(1000), nullable=False),
    )
    _index("ix_incident_notes_incident", "incident_notes", ["incident_id", "created_at"])
    # SQLite can add columns and unique indexes without rebuilding the old data tables.
    # A failed development attempt may have left an empty Alembic temporary table.
    bind = op.get_bind()
    if sa.inspect(bind).has_table("_alembic_tmp_telemetry_samples"):
        count = bind.execute(sa.text("SELECT COUNT(*) FROM _alembic_tmp_telemetry_samples")).scalar_one()
        if count:
            raise RuntimeError("Nonempty Alembic temporary telemetry table needs manual review")
        op.drop_table("_alembic_tmp_telemetry_samples")
    if "source_id" not in {column["name"] for column in sa.inspect(bind).get_columns("telemetry_samples")}:
        op.add_column("telemetry_samples", sa.Column("source_id", sa.String(64), nullable=False,
                                                      server_default="orbitra-local-simulator"))
    _index("uq_telemetry_run_source_sequence", "telemetry_samples",
           ["run_id", "source_id", "sequence_number"], unique=True)
    rejected_columns = {column["name"] for column in sa.inspect(bind).get_columns("rejected_telemetry")}
    if "source_id" not in rejected_columns:
        op.add_column("rejected_telemetry", sa.Column("source_id", sa.String(64), nullable=False,
                                                      server_default="orbitra-local-simulator"))
    if "reason_code" not in rejected_columns:
        op.add_column("rejected_telemetry", sa.Column("reason_code", sa.String(32), nullable=False,
                                                        server_default="SCHEMA_REJECTED"))
    if "user_id" not in {column["name"] for column in sa.inspect(bind).get_columns("operator_events")}:
        op.add_column("operator_events", sa.Column("user_id", sa.Integer(), nullable=True))
    op.execute(sa.text("""
        INSERT INTO security_incidents
        (incident_id, created_at, kind, status, reason_code, summary, run_id, source_id, sequence_number)
        SELECT rejection_id, rejected_at, 'TELEMETRY_REJECTION', 'OPEN',
               'SCHEMA_REJECTED', reason, run_id, 'orbitra-local-simulator', sequence_number
        FROM rejected_telemetry AS r
        WHERE NOT EXISTS (SELECT 1 FROM security_incidents AS i WHERE i.incident_id = r.rejection_id)
    """))


def downgrade() -> None:
    op.drop_column("operator_events", "user_id")
    op.drop_column("rejected_telemetry", "reason_code")
    op.drop_column("rejected_telemetry", "source_id")
    op.drop_index("uq_telemetry_run_source_sequence", table_name="telemetry_samples")
    op.drop_column("telemetry_samples", "source_id")
    op.drop_index("ix_incident_notes_incident", table_name="incident_notes")
    op.drop_table("incident_notes")
    op.drop_index("ix_security_incidents_time", table_name="security_incidents")
    op.drop_table("security_incidents")
    op.drop_index("ix_audit_events_time", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_user_sessions_user", table_name="user_sessions")
    op.drop_table("user_sessions")
    op.drop_table("users")

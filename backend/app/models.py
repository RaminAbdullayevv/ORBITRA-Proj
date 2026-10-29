from sqlalchemy import Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    started_at: Mapped[str] = mapped_column(String(40), nullable=False)
    last_status: Mapped[str] = mapped_column(String(16), nullable=False)
    scenario: Mapped[str] = mapped_column(String(32), nullable=False, default="NORMAL_MISSION")
    ended_at: Mapped[str | None] = mapped_column(String(40), nullable=True)


class TelemetrySample(Base):
    __tablename__ = "telemetry_samples"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence_number", name="uq_telemetry_run_sequence"),
        UniqueConstraint("run_id", "source_id", "sequence_number", name="uq_telemetry_run_source_sequence"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("simulation_runs.run_id"), nullable=False)
    source_id: Mapped[str] = mapped_column(String(64), nullable=False, default="orbitra-local-simulator")
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    simulation_elapsed_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    sample_time: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    battery_level_percent: Mapped[float] = mapped_column(Float, nullable=False)
    voltage_v: Mapped[float] = mapped_column(Float, nullable=False)
    current_a: Mapped[float] = mapped_column(Float, nullable=False)
    temperature_1_c: Mapped[float] = mapped_column(Float, nullable=False)
    temperature_2_c: Mapped[float] = mapped_column(Float, nullable=False)
    temperature_3_c: Mapped[float] = mapped_column(Float, nullable=False)
    cpu_load_percent: Mapped[float] = mapped_column(Float, nullable=False)
    memory_usage_percent: Mapped[float] = mapped_column(Float, nullable=False)
    signal_strength_percent: Mapped[float] = mapped_column(Float, nullable=False)
    communication_latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    packet_loss_percent: Mapped[float] = mapped_column(Float, nullable=False)


class OperatorEvent(Base):
    __tablename__ = "operator_events"

    event_number: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("simulation_runs.run_id"), nullable=True)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    received_at: Mapped[str] = mapped_column(String(40), nullable=False)
    simulation_elapsed_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    before_status: Mapped[str] = mapped_column(String(16), nullable=False)
    after_status: Mapped[str] = mapped_column(String(16), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str] = mapped_column(String(240), nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False, default="local_demo_operator")
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)


class RuleAlert(Base):
    __tablename__ = "rule_alerts"

    alert_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("simulation_runs.run_id"), nullable=False)
    rule_code: Mapped[str] = mapped_column(String(40), nullable=False)
    opened_at: Mapped[str] = mapped_column(String(40), nullable=False)
    closed_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reason: Mapped[str] = mapped_column(String(240), nullable=False)
    metric_key: Mapped[str] = mapped_column(String(40), nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    resolved_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)


class RejectedTelemetry(Base):
    __tablename__ = "rejected_telemetry"

    rejection_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("simulation_runs.run_id"), nullable=False)
    source_id: Mapped[str] = mapped_column(String(64), nullable=False, default="orbitra-local-simulator")
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    rejected_at: Mapped[str] = mapped_column(String(40), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(40), nullable=False)
    reason: Mapped[str] = mapped_column(String(240), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(32), nullable=False, default="SCHEMA_REJECTED")
    packet_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    raw_payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    signature_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    packet_timestamp: Mapped[str | None] = mapped_column(String(40), nullable=True)
    incident_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class TrustAssessment(Base):
    __tablename__ = "telemetry_trust_assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mission_id: Mapped[str] = mapped_column(String(36), ForeignKey("simulation_runs.run_id"), nullable=False)
    packet_id: Mapped[str] = mapped_column(String(36), nullable=False)
    device_id: Mapped[str] = mapped_column(String(64), nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    received_at: Mapped[str] = mapped_column(String(40), nullable=False)
    schema_valid: Mapped[bool] = mapped_column(nullable=False)
    source_valid: Mapped[bool | None] = mapped_column(nullable=True)
    signature_valid: Mapped[bool | None] = mapped_column(nullable=True)
    replay_detected: Mapped[bool | None] = mapped_column(nullable=True)
    freshness_valid: Mapped[bool | None] = mapped_column(nullable=True)
    cross_sensor_status: Mapped[str] = mapped_column(String(24), nullable=False)
    digital_twin_status: Mapped[str] = mapped_column(String(24), nullable=False)
    final_verdict: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    explanation: Mapped[str] = mapped_column(String(600), nullable=False)
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False)
    ruleset_version: Mapped[str] = mapped_column(String(40), nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    processing_time_ms: Mapped[float] = mapped_column(Float, nullable=False)
    accepted: Mapped[bool] = mapped_column(nullable=False)
    incident_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)
    active: Mapped[bool] = mapped_column(nullable=False, default=True)


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)
    expires_at: Mapped[str] = mapped_column(String(40), nullable=False)
    revoked_at: Mapped[str | None] = mapped_column(String(40), nullable=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    occurred_at: Mapped[str] = mapped_column(String(40), nullable=False)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[str] = mapped_column(String(24), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(40), nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    incident_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    sequence_number: Mapped[int | None] = mapped_column(Integer, nullable=True)


class SecurityIncident(Base):
    __tablename__ = "security_incidents"

    incident_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(40), nullable=False)
    summary: Mapped[str] = mapped_column(String(240), nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sequence_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    closed_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    closed_by_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    close_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)


class IncidentNote(Base):
    __tablename__ = "incident_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[str] = mapped_column(String(36), ForeignKey("security_incidents.incident_id"), nullable=False)
    author_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)
    body: Mapped[str] = mapped_column(String(1000), nullable=False)


class AIModelVersion(Base):
    __tablename__ = "ai_model_versions"

    version: Mapped[str] = mapped_column(String(64), primary_key=True)
    trained_at: Mapped[str] = mapped_column(String(40), nullable=False)
    training_summary: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    score_threshold: Mapped[float] = mapped_column(Float, nullable=False)


class AIEvent(Base):
    __tablename__ = "ai_events"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("simulation_runs.run_id"), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), ForeignKey("ai_model_versions.version"), nullable=False)
    started_at: Mapped[str] = mapped_column(String(40), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(40), nullable=False)
    ended_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    start_sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    latest_sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    window_start_sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    affected_sensors: Mapped[str] = mapped_column(Text, nullable=False)
    baseline_comparison: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(String(600), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)


class RunAnalysis(Base):
    __tablename__ = "run_analysis"

    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("simulation_runs.run_id"), primary_key=True)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    last_evaluated_at: Mapped[str] = mapped_column(String(40), nullable=False)
    latest_sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)


class ReportGeneration(Base):
    __tablename__ = "report_generations"

    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("simulation_runs.run_id"), primary_key=True)
    generated_at: Mapped[str] = mapped_column(String(40), nullable=False)
    rules_version: Mapped[str] = mapped_column(String(40), nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)


class DeviceRunHistory(Base):
    __tablename__ = "device_run_history"
    run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    scenario: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[str] = mapped_column(String(40), nullable=False)
    last_status: Mapped[str] = mapped_column(String(16), nullable=False)
    ended_at: Mapped[str | None] = mapped_column(String(40), nullable=True)


class DeviceDispatchHistory(Base):
    __tablename__ = "device_dispatch_history"
    legacy_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    sequence_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    packet_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    sent_at: Mapped[str] = mapped_column(String(40), nullable=False)
    result: Mapped[str] = mapped_column(String(24), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)


class DeviceAuditHistory(Base):
    __tablename__ = "device_audit_history"
    legacy_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    occurred_at: Mapped[str] = mapped_column(String(40), nullable=False)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[str] = mapped_column(String(24), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(40), nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    sequence_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

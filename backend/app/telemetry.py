"""Persistence and live delivery for the one local simulator."""

import asyncio
import json
import logging
import math
import time
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import WebSocket
from pydantic import BaseModel, Field
from sqlalchemy import Engine, func, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.ai_analysis import AIAnalyzer, AIEventPayload, AIStatusPayload
from app.auth import Principal, security
from app.config import settings
from app.cyber_demo import test_evidence
from app.database import engine
from app.integrity import SOURCE_ID, SignedTelemetryPacket, verify_control, verify_packet
from app.models import OperatorEvent, RejectedTelemetry, RuleAlert, SecurityIncident, SimulationRun, TelemetrySample, TrustAssessment
from app.sentinel import MAX_FUTURE_SECONDS, MAX_PAST_SECONDS, RULESET_VERSION, attribute
from app.simulator import (
    DeviceStatus, InvalidTransition, ScenarioName, SensorReadings, SimulatorSnapshot,
    VirtualSpacecraftSimulator, simulator,
)


logger = logging.getLogger(__name__)


class TelemetrySamplePayload(BaseModel):
    run_id: str
    sequence_number: int
    simulation_elapsed_seconds: int
    sample_time: datetime
    status: DeviceStatus
    sensors: SensorReadings


class RunSummary(BaseModel):
    run_id: str
    scenario: ScenarioName
    started_at: datetime
    last_status: str
    ended_at: datetime | None


class RuleAlertPayload(BaseModel):
    alert_id: str
    run_id: str
    opened_at: datetime
    closed_at: datetime | None
    reason: str
    metric_key: str
    metric_value: float
    resolved_value: float | None
    status: str


class RejectedTelemetryPayload(BaseModel):
    rejection_id: str
    run_id: str
    sequence_number: int
    rejected_at: datetime
    schema_version: str
    reason: str
    reason_code: str
    source_id: str
    packet_id: str | None = None
    signature_status: str | None = None
    packet_timestamp: datetime | None = None
    incident_id: str | None = None


class TelemetryState(BaseModel):
    device: SimulatorSnapshot | None
    run: RunSummary | None
    latest_sample: TelemetrySamplePayload | None
    active_alerts: list[RuleAlertPayload] = Field(default_factory=list)
    rule_alerts: list[RuleAlertPayload] = Field(default_factory=list)
    rejections: list[RejectedTelemetryPayload] = Field(default_factory=list)
    ai_status: AIStatusPayload
    ai_events: list[AIEventPayload] = Field(default_factory=list)
    trust: dict = Field(default_factory=dict)
    device_last_seen_at: datetime | None = None


class TelemetryHistory(BaseModel):
    run_id: str
    samples: list[TelemetrySamplePayload]
    has_more: bool


class OperatorEventPayload(BaseModel):
    event_number: int
    event_id: str
    run_id: str | None
    action: str
    received_at: datetime
    simulation_elapsed_seconds: int
    before_status: str
    after_status: str
    outcome: str
    reason: str
    source: str
    user_id: int | None = None


class OperatorEventHistory(BaseModel):
    run_id: str
    events: list[OperatorEventPayload]
    has_more: bool


def _as_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _sample_payload(row: TelemetrySample) -> TelemetrySamplePayload:
    return TelemetrySamplePayload(
        run_id=row.run_id,
        sequence_number=row.sequence_number,
        simulation_elapsed_seconds=row.simulation_elapsed_seconds,
        sample_time=_as_utc(row.sample_time),
        status=DeviceStatus(row.status),
        sensors=SensorReadings(**{key: getattr(row, key) for key in SensorReadings.model_fields}),
    )


def _run_payload(row: SimulationRun) -> RunSummary:
    return RunSummary(
        run_id=row.run_id,
        scenario=ScenarioName(row.scenario),
        started_at=_as_utc(row.started_at),
        last_status=row.last_status,
        ended_at=_as_utc(row.ended_at) if row.ended_at else None,
    )


def _event_payload(row: OperatorEvent) -> OperatorEventPayload:
    return OperatorEventPayload(
        event_number=row.event_number, event_id=row.event_id, run_id=row.run_id,
        action=row.action, received_at=_as_utc(row.received_at),
        simulation_elapsed_seconds=row.simulation_elapsed_seconds,
        before_status=row.before_status, after_status=row.after_status,
        outcome=row.outcome, reason=row.reason, source=row.source, user_id=row.user_id,
    )


def _alert_payload(row: RuleAlert) -> RuleAlertPayload:
    return RuleAlertPayload(
        alert_id=row.alert_id, run_id=row.run_id, opened_at=_as_utc(row.opened_at),
        closed_at=_as_utc(row.closed_at) if row.closed_at else None,
        reason=row.reason, metric_key=row.metric_key, metric_value=row.metric_value,
        resolved_value=row.resolved_value, status=row.status,
    )


def _rejection_payload(row: RejectedTelemetry) -> RejectedTelemetryPayload:
    return RejectedTelemetryPayload(
        rejection_id=row.rejection_id, run_id=row.run_id,
        sequence_number=row.sequence_number, rejected_at=_as_utc(row.rejected_at),
        schema_version=row.schema_version, reason=row.reason,
        reason_code=row.reason_code, source_id=row.source_id, packet_id=row.packet_id,
        signature_status=row.signature_status, incident_id=row.incident_id,
        packet_timestamp=_as_utc(row.packet_timestamp) if row.packet_timestamp else None,
    )


def _trust_payload(row: TrustAssessment) -> dict:
    return {
        "id": row.id, "packet_id": row.packet_id, "mission_id": row.mission_id,
        "device_id": row.device_id, "sequence_number": row.sequence_number,
        "received_at": row.received_at, "schema_valid": row.schema_valid,
        "source_valid": row.source_valid, "signature_valid": row.signature_valid,
        "replay_detected": row.replay_detected, "freshness_valid": row.freshness_valid,
        "cross_sensor_status": row.cross_sensor_status, "digital_twin_status": row.digital_twin_status,
        "final_verdict": row.final_verdict, "severity": row.severity,
        "explanation": row.explanation, "evidence": json.loads(row.evidence_json),
        "ruleset_version": row.ruleset_version, "model_version": row.model_version,
        "processing_time_ms": row.processing_time_ms, "accepted": row.accepted,
        "incident_id": row.incident_id,
    }


def _safe_json(value: object) -> object:
    """Preserve malformed local test values as strings in standard JSON quarantine."""
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {key: _safe_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe_json(item) for item in value]
    return value


class TelemetryStore:
    def __init__(self, database_engine: Engine, integrity_key: bytes | None = None):
        self.engine = database_engine
        self.integrity_key = integrity_key
        self.last_assessment: dict | None = None

    def mark_interrupted_runs(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with Session(self.engine) as db:
            db.execute(
                update(SimulationRun)
                .where(SimulationRun.last_status.in_(["RUNNING", "PAUSED"]))
                .values(last_status="INTERRUPTED", ended_at=now)
            )
            db.commit()

    def record_operation(
        self, action: str, before: SimulatorSnapshot, after: SimulatorSnapshot,
        outcome: str, reason: str, actor: Principal | None = None, source_override: str | None = None,
    ) -> OperatorEventPayload:
        now = datetime.now(timezone.utc).isoformat()
        run_id = after.run_id if action == "start" and outcome == "SUCCESS" else before.run_id
        with Session(self.engine) as db:
            if outcome == "SUCCESS" and action == "start":
                assert after.run_id is not None
                db.add(SimulationRun(
                    run_id=after.run_id, started_at=after.updated_at.isoformat(),
                    last_status=after.status.value, scenario=after.scenario.value,
                ))
            elif outcome == "SUCCESS" and run_id and not (action == "reset" and before.status == DeviceStatus.ENDED):
                values: dict[str, str] = {"last_status": "RESET" if action == "reset" else after.status.value}
                if action in ("reset", "end"):
                    values["ended_at"] = now
                db.execute(update(SimulationRun).where(SimulationRun.run_id == run_id).values(**values))
            row = OperatorEvent(
                event_id=str(uuid4()), run_id=run_id, action=action,
                received_at=now, simulation_elapsed_seconds=after.simulation_elapsed_seconds,
                before_status=before.status.value, after_status=after.status.value,
                outcome=outcome, reason=reason,
                source=source_override or ("authenticated_operator" if actor else "local_demo_operator"),
                user_id=actor.user_id if actor else None,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return _event_payload(row)

    def read_events(self, run_id: str, after_id: int, limit: int) -> OperatorEventHistory | None:
        with Session(self.engine) as db:
            if db.get(SimulationRun, run_id) is None:
                return None
            rows = list(db.scalars(
                select(OperatorEvent)
                .where(OperatorEvent.run_id == run_id, OperatorEvent.event_number > after_id)
                .order_by(OperatorEvent.event_number.asc()).limit(limit + 1)
            ))
            return OperatorEventHistory(
                run_id=run_id, events=[_event_payload(row) for row in rows[:limit]],
                has_more=len(rows) > limit,
            )

    def insert_sample(self, snapshot: SimulatorSnapshot, source_id: str) -> TelemetrySamplePayload | None:
        if snapshot.schema_version != "1.0":
            raise ValueError(f"Unsupported schema_version: {snapshot.schema_version}")
        assert snapshot.run_id is not None
        values = {
            "run_id": snapshot.run_id,
            "source_id": source_id,
            "sequence_number": snapshot.simulation_elapsed_seconds,
            "simulation_elapsed_seconds": snapshot.simulation_elapsed_seconds,
            "sample_time": snapshot.updated_at.isoformat(),
            "status": snapshot.status.value,
            **snapshot.sensors.model_dump(),
        }
        with Session(self.engine) as db:
            result = db.execute(
                sqlite_insert(TelemetrySample)
                .values(**values)
                .on_conflict_do_nothing()
            )
            db.commit()
        if result.rowcount != 1:
            return None
        return TelemetrySamplePayload(
            run_id=snapshot.run_id,
            sequence_number=snapshot.simulation_elapsed_seconds,
            simulation_elapsed_seconds=snapshot.simulation_elapsed_seconds,
            sample_time=snapshot.updated_at,
            status=snapshot.status,
            sensors=snapshot.sensors,
        )

    def _reject_packet(self, packet: SignedTelemetryPacket, code: str, reason: str, start: float,
                       checks: dict, model_version: str | None, run_id_override: str | None = None,
                       raw_payload_override: object | None = None) -> RejectedTelemetryPayload:
        snapshot = packet.snapshot
        effective_run_id = run_id_override or snapshot.run_id
        assert effective_run_id is not None
        now = datetime.now(timezone.utc).isoformat()
        verdict = {
            "SCHEMA_REJECTED": "INSUFFICIENT EVIDENCE",
            "SOURCE_REJECTED": "UNKNOWN SOURCE",
            "INTEGRITY_REJECTED": "INTEGRITY INCIDENT",
            "REPLAY_REJECTED": "REPLAY INCIDENT",
            "STALE_REJECTED": "STALE DATA",
            "RUN_REJECTED": "INSUFFICIENT EVIDENCE",
            "STATE_REJECTED": "INSUFFICIENT EVIDENCE",
        }[code]
        with Session(self.engine) as db:
            existing = db.scalar(select(RejectedTelemetry).where(
                RejectedTelemetry.run_id == effective_run_id,
                RejectedTelemetry.sequence_number == snapshot.simulation_elapsed_seconds,
                RejectedTelemetry.reason_code == code,
            ))
            if existing is not None:
                return _rejection_payload(existing)
            rejection = RejectedTelemetry(
                rejection_id=str(uuid4()), run_id=effective_run_id, source_id=packet.source_id,
                sequence_number=snapshot.simulation_elapsed_seconds, rejected_at=now,
                schema_version=snapshot.schema_version, reason=reason, reason_code=code,
                packet_id=packet.packet_id,
                raw_payload_json=json.dumps(_safe_json(raw_payload_override if raw_payload_override is not None else snapshot.model_dump(mode="json")), ensure_ascii=False, allow_nan=False),
                signature_status="INVALID" if code == "INTEGRITY_REJECTED" else "VALID" if checks.get("signature_valid") else "NOT_EVALUATED",
                packet_timestamp=snapshot.updated_at.isoformat(),
            )
            incident = SecurityIncident(
                incident_id=str(uuid4()), created_at=now, kind="TELEMETRY_REJECTION", status="OPEN",
                reason_code=code, summary=reason, run_id=effective_run_id, source_id=packet.source_id,
                sequence_number=snapshot.simulation_elapsed_seconds,
            )
            db.add(rejection)
            db.add(incident)
            rejection.incident_id = incident.incident_id
            trust = TrustAssessment(
                mission_id=effective_run_id, packet_id=packet.packet_id, device_id=packet.source_id,
                sequence_number=snapshot.simulation_elapsed_seconds, received_at=now,
                schema_valid=checks.get("schema_valid", False), source_valid=checks.get("source_valid"),
                signature_valid=checks.get("signature_valid"), replay_detected=checks.get("replay_detected"),
                freshness_valid=checks.get("freshness_valid"), cross_sensor_status="NOT_EVALUATED",
                digital_twin_status="NOT_EVALUATED", final_verdict=verdict, severity="CRITICAL",
                explanation=reason, evidence_json=json.dumps({"rejection_code": code, **checks.get("evidence", {})}),
                ruleset_version=RULESET_VERSION, model_version=model_version,
                processing_time_ms=round((time.perf_counter() - start) * 1000, 3),
                accepted=False, incident_id=incident.incident_id,
            )
            db.add(trust)
            security.audit("TELEMETRY_REJECTION", "REJECTED", code, run_id=effective_run_id,
                           incident_id=incident.incident_id, sequence_number=snapshot.simulation_elapsed_seconds, db=db)
            db.commit()
            self.last_assessment = _trust_payload(trust)
            return _rejection_payload(rejection)

    def process_sample(self, packet: SignedTelemetryPacket, model_version: str | None = None) -> tuple[TelemetrySamplePayload | None, list[RuleAlertPayload], RejectedTelemetryPayload | None]:
        """Security gate precedes persistence, attribution, rules, AI and live delivery."""
        start = time.perf_counter()
        snapshot = packet.snapshot
        assert snapshot.run_id is not None
        checks: dict = {"evidence": {"sequence_number": snapshot.simulation_elapsed_seconds,
                                    **test_evidence(packet.test_kind)}}
        checks["schema_valid"] = (snapshot.schema_version == "1.0" and snapshot.simulation_elapsed_seconds >= 1
            and snapshot.updated_at.tzinfo is not None
            and all(math.isfinite(value) for value in snapshot.sensors.model_dump().values()))
        if not checks["schema_valid"]:
            reason = (f"Dəstəklənməyən schema_version: {snapshot.schema_version}; gözlənilən: 1.0."
                      if snapshot.schema_version != "1.0" else "Paketdə sıra, UTC vaxtı və ya sonlu sensor dəyəri yanlışdır.")
            return None, [], self._reject_packet(packet, "SCHEMA_REJECTED", reason, start, checks, model_version)
        if self.integrity_key is None:
            raise RuntimeError("TELEMETRY_HMAC_KEY is not configured")
        checks["source_valid"] = packet.source_id == SOURCE_ID
        if not checks["source_valid"]:
            return None, [], self._reject_packet(packet, "SOURCE_REJECTED", "Paketin mənbəsi tanınmır.", start, checks, model_version)
        checks["signature_valid"] = verify_packet(packet, self.integrity_key)
        if not checks["signature_valid"]:
            return None, [], self._reject_packet(packet, "INTEGRITY_REJECTED", "Paketin HMAC-SHA256 imzası uyğun gəlmir.", start, checks, model_version)
        with Session(self.engine) as db:
            previous = db.scalar(select(TelemetrySample).where(TelemetrySample.run_id == snapshot.run_id)
                                 .order_by(TelemetrySample.sequence_number.desc()).limit(1))
            if previous is not None:
                db.expunge(previous)
        checks["replay_detected"] = previous is not None and snapshot.simulation_elapsed_seconds <= previous.sequence_number
        if checks["replay_detected"]:
            checks["evidence"]["last_accepted_sequence"] = previous.sequence_number
            return None, [], self._reject_packet(packet, "REPLAY_REJECTED", "Bu run üçün sıra nömrəsi artıq qəbul edilib və ya geriyə gedir.", start, checks, model_version)
        age = (datetime.now(timezone.utc) - snapshot.updated_at).total_seconds()
        checks["evidence"]["packet_age_seconds"] = round(age, 3)
        checks["freshness_valid"] = -MAX_FUTURE_SECONDS <= age <= MAX_PAST_SECONDS
        if not checks["freshness_valid"]:
            return None, [], self._reject_packet(packet, "STALE_REJECTED", "Paket vaxtı qəbul pəncərəsindən kənardadır.", start, checks, model_version)
        sample = self.insert_sample(snapshot, packet.source_id)
        if sample is None:
            checks["replay_detected"] = True
            return None, [], self._reject_packet(packet, "REPLAY_REJECTED", "Bu run, mənbə və sıra nömrəsi artıq qəbul edilib.", start, checks, model_version)
        attribution = attribute(snapshot, previous)
        with Session(self.engine) as db:
            trust = TrustAssessment(
                mission_id=sample.run_id, packet_id=packet.packet_id, device_id=packet.source_id,
                sequence_number=sample.sequence_number, received_at=datetime.now(timezone.utc).isoformat(),
                schema_valid=True, source_valid=True, signature_valid=True, replay_detected=False,
                freshness_valid=True, cross_sensor_status=attribution.cross_sensor_status,
                digital_twin_status=attribution.digital_twin_status,
                final_verdict=attribution.verdict, severity=attribution.severity,
                explanation=attribution.explanation,
                evidence_json=json.dumps({**attribution.evidence, **checks["evidence"]}),
                ruleset_version=RULESET_VERSION, model_version=model_version,
                processing_time_ms=round((time.perf_counter() - start) * 1000, 3),
                accepted=True, incident_id=None,
            )
            db.add(trust)
            db.commit()
            self.last_assessment = _trust_payload(trust)
        rules = [
            ("TEMP_1_HIGH", "temperature_1_c", sample.sensors.temperature_1_c, 24.5, 23.3,
             "Temperatur 1 qayda həddi (24.5 °C) keçdi."),
            ("PACKET_LOSS_HIGH", "packet_loss_percent", sample.sensors.packet_loss_percent, 0.5, 0.3,
             "Paket itkisi qayda həddi (0.5%) keçdi."),
        ]
        changed: list[RuleAlert] = []
        with Session(self.engine) as db:
            for rule_code, metric_key, value, open_limit, close_limit, reason in rules:
                active = db.scalars(select(RuleAlert).where(
                    RuleAlert.run_id == sample.run_id, RuleAlert.rule_code == rule_code,
                    RuleAlert.status == "ACTIVE",
                )).first()
                if rule_code == "TEMP_1_HIGH" and attribution.verdict == "PROBABLE SENSOR FAULT":
                    if active is not None:
                        active.closed_at = sample.sample_time.isoformat()
                        active.resolved_value = value
                        active.status = "RESOLVED"
                        changed.append(active)
                    continue
                if active is None and value >= open_limit:
                    row = RuleAlert(
                        alert_id=str(uuid4()), run_id=sample.run_id, rule_code=rule_code,
                        opened_at=sample.sample_time.isoformat(), closed_at=None, reason=reason,
                        metric_key=metric_key, metric_value=value, resolved_value=None, status="ACTIVE",
                    )
                    db.add(row)
                    changed.append(row)
                elif active is not None and value <= close_limit:
                    active.closed_at = sample.sample_time.isoformat()
                    active.resolved_value = value
                    active.status = "RESOLVED"
                    changed.append(active)
            if changed:
                db.commit()
                return sample, [_alert_payload(row) for row in changed], None
        return sample, [], None

    def read_trust_overview(self, run_id: str | None) -> dict:
        empty = {"accepted": 0, "quarantined": 0, "system_anomaly": 0, "sensor_fault": 0,
                 "integrity_incident": 0, "replay_incident": 0, "stale_data": 0}
        if not run_id:
            return {"status": "NO DATA", "latest": None, "latest_accepted": None,
                    "stats": empty, "quarantine": [], "last_successful_at": None,
                    "active_integrity_count": 0, "active_integrity_assessment_id": None,
                    "untrusted_blocks": []}
        with Session(self.engine) as db:
            latest = db.scalar(select(TrustAssessment).where(TrustAssessment.mission_id == run_id)
                               .order_by(TrustAssessment.id.desc()).limit(1))
            accepted = db.scalar(select(TrustAssessment).where(TrustAssessment.mission_id == run_id,
                TrustAssessment.accepted.is_(True)).order_by(TrustAssessment.id.desc()).limit(1))
            counts = dict(db.execute(select(TrustAssessment.final_verdict, func.count()).where(
                TrustAssessment.mission_id == run_id).group_by(TrustAssessment.final_verdict)).all())
            stats = {**empty,
                "accepted": db.scalar(select(func.count()).select_from(TelemetrySample).where(TelemetrySample.run_id == run_id)) or 0,
                "quarantined": db.scalar(select(func.count()).select_from(RejectedTelemetry).where(RejectedTelemetry.run_id == run_id)) or 0,
                "system_anomaly": counts.get("PROBABLE SYSTEM ANOMALY", 0),
                "sensor_fault": counts.get("PROBABLE SENSOR FAULT", 0),
                "integrity_incident": counts.get("INTEGRITY INCIDENT", 0),
                "replay_incident": counts.get("REPLAY INCIDENT", 0),
                "stale_data": counts.get("STALE DATA", 0),
            }
            quarantine = list(db.scalars(select(RejectedTelemetry).where(RejectedTelemetry.run_id == run_id)
                                         .order_by(RejectedTelemetry.rejected_at.desc()).limit(20)))
            open_rejections = list(db.scalars(select(SecurityIncident).where(
                SecurityIncident.run_id == run_id, SecurityIncident.kind == "TELEMETRY_REJECTION",
                SecurityIncident.status == "OPEN")))
            open_integrity = [item for item in open_rejections if item.reason_code == "INTEGRITY_REJECTED"]
            open_assessments = list(db.scalars(select(TrustAssessment).where(
                TrustAssessment.incident_id.in_([item.incident_id for item in open_rejections]))
                .order_by(TrustAssessment.id.desc()))) if open_rejections else []
            active_assessment = next((item for item in open_assessments
                if item.incident_id in {incident.incident_id for incident in open_integrity}), None)
            untrusted_blocks = []
            for item in open_assessments:
                evidence = json.loads(item.evidence_json)
                block = evidence.get("affected_block")
                if block and block not in untrusted_blocks:
                    untrusted_blocks.append(block)
            run = db.get(SimulationRun, run_id)
            age = (datetime.now(timezone.utc) - _as_utc(accepted.received_at)).total_seconds() if accepted else None
            live = accepted and run and (run.last_status == "PAUSED" or
                (run.last_status == "RUNNING" and age is not None and age <= 5))
            status = "DEGRADED" if live and (open_rejections or (latest and not latest.accepted)) else \
                "ONLINE" if live else "DEGRADED" if latest and run and run.last_status in ("RUNNING", "PAUSED") else "NO DATA"
            return {"status": status, "latest": _trust_payload(latest) if latest else None,
                    "latest_accepted": _trust_payload(accepted) if accepted else None,
                    "stats": stats, "quarantine": [_rejection_payload(row).model_dump(mode="json") for row in quarantine],
                    "last_successful_at": accepted.received_at if accepted else None,
                    "active_integrity_count": len(open_integrity),
                    "active_integrity_assessment_id": active_assessment.id if active_assessment else None,
                    "untrusted_blocks": untrusted_blocks}

    def read_trust_decisions(self, run_id: str, before_id: int | None, limit: int) -> dict | None:
        with Session(self.engine) as db:
            if db.get(SimulationRun, run_id) is None:
                return None
            query = select(TrustAssessment).where(TrustAssessment.mission_id == run_id)
            if before_id is not None:
                query = query.where(TrustAssessment.id < before_id)
            rows = list(db.scalars(query.order_by(TrustAssessment.id.desc()).limit(limit + 1)))
            return {"decisions": [_trust_payload(row) for row in rows[:limit]], "has_more": len(rows) > limit}

    def read_trust_decision(self, run_id: str, assessment_id: int) -> dict | None:
        with Session(self.engine) as db:
            row = db.get(TrustAssessment, assessment_id)
            return _trust_payload(row) if row and row.mission_id == run_id else None

    def read_scenario_events(self, run_id: str) -> tuple[list[RuleAlertPayload], list[RejectedTelemetryPayload]]:
        with Session(self.engine) as db:
            alerts = list(db.scalars(select(RuleAlert).where(RuleAlert.run_id == run_id).order_by(RuleAlert.opened_at)))
            rejections = list(db.scalars(select(RejectedTelemetry).where(RejectedTelemetry.run_id == run_id).order_by(RejectedTelemetry.sequence_number)))
            return [_alert_payload(row) for row in alerts], [_rejection_payload(row) for row in rejections]

    def read_state(self, run_id: str) -> tuple[RunSummary | None, TelemetrySamplePayload | None]:
        with Session(self.engine) as db:
            run = db.get(SimulationRun, run_id)
            if run is None:
                return None, None
            latest = db.scalars(
                select(TelemetrySample)
                .where(TelemetrySample.run_id == run_id)
                .order_by(TelemetrySample.sequence_number.desc())
                .limit(1)
            ).first()
            return _run_payload(run), _sample_payload(latest) if latest else None

    def read_history(self, run_id: str, after_sequence: int | None, limit: int) -> TelemetryHistory | None:
        with Session(self.engine) as db:
            if db.get(SimulationRun, run_id) is None:
                return None
            query = select(TelemetrySample).where(TelemetrySample.run_id == run_id)
            if after_sequence is None:
                rows = list(db.scalars(query.order_by(TelemetrySample.sequence_number.desc()).limit(limit)))
                rows.reverse()
                return TelemetryHistory(run_id=run_id, samples=[_sample_payload(row) for row in rows], has_more=False)
            rows = list(db.scalars(
                query.where(TelemetrySample.sequence_number > after_sequence)
                .order_by(TelemetrySample.sequence_number.asc())
                .limit(limit + 1)
            ))
            return TelemetryHistory(
                run_id=run_id,
                samples=[_sample_payload(row) for row in rows[:limit]],
                has_more=len(rows) > limit,
            )


class TelemetryCoordinator:
    def __init__(self, device: VirtualSpacecraftSimulator, store: TelemetryStore, *, external: bool = False):
        self.device = device
        self.external = external
        self._external_snapshot = device.snapshot()
        self._last_device_seen_at: datetime | None = None
        self.store = store
        self.ai = AIAnalyzer(store.engine)
        self._lock = asyncio.Lock()
        self._clients: set[WebSocket] = set()
        self._client_tokens: dict[WebSocket, str] = {}
        self._pending: list[SignedTelemetryPacket] = []
        self._task: asyncio.Task[None] | None = None

    def _flush_locked(self) -> list[dict]:
        events: list[dict] = []
        while self._pending:
            model_version = self.ai.metadata["version"] if self.ai.metadata else None
            saved, alerts, rejected = self.store.process_sample(self._pending[0], model_version)
            self._pending.pop(0)
            if saved is not None:
                events.append({"type": "telemetry_sample", **saved.model_dump(mode="json")})
                try:
                    ai_status, ai_event = self.ai.assess(saved.run_id, saved.sequence_number, saved.sample_time)
                    events.append({"type": "ai_assessment", "run_id": saved.run_id, "ai_status": ai_status.model_dump(mode="json")})
                    if ai_event is not None:
                        events.append({"type": "ai_event", **ai_event.model_dump(mode="json")})
                except Exception as exc:
                    self.ai.fail(exc)
                    events.append({"type": "ai_assessment", "run_id": saved.run_id,
                                   "ai_status": self.ai.status(saved.run_id).model_dump(mode="json")})
            for alert in alerts:
                events.append({"type": "rule_alert", **alert.model_dump(mode="json")})
            if rejected is not None:
                events.append({"type": "telemetry_rejected", **rejected.model_dump(mode="json")})
            if self.store.last_assessment is not None:
                events.append({"type": "trust_assessment", "run_id": self.store.last_assessment["mission_id"],
                               "trust": self.store.read_trust_overview(self.store.last_assessment["mission_id"])})
        return events

    def _sync_locked(self) -> tuple[SimulatorSnapshot, list[dict]]:
        if self.external:
            return self._external_snapshot, []
        snapshot = self.device.snapshot()
        self._last_device_seen_at = datetime.now(timezone.utc)
        if self.store.integrity_key is None:
            raise RuntimeError("TELEMETRY_HMAC_KEY is not configured; run python -m scripts.setup_security")
        self._pending.extend(self.device.drain_signed_samples(self.store.integrity_key))
        return snapshot, self._flush_locked()

    async def _broadcast(self, events: list[dict]) -> None:
        if not events:
            return
        for client in tuple(self._clients):
            try:
                token = self._client_tokens.get(client)
                if token is not None and security.authenticate(token) is None:
                    await client.close(code=1008)
                    self.disconnect(client)
                    continue
                for event in events:
                    await client.send_json(event)
            except Exception:
                self.disconnect(client)

    async def tick(self) -> SimulatorSnapshot:
        async with self._lock:
            snapshot, events = self._sync_locked()
        await self._broadcast(events)
        return snapshot

    async def current(self) -> SimulatorSnapshot:
        return await self.tick()

    async def state(self, run_id: str | None = None) -> TelemetryState:
        async with self._lock:
            current, events = self._sync_locked()
            selected = run_id or current.run_id
            run, latest = self.store.read_state(selected) if selected else (None, None)
            alerts, rejections = self.store.read_scenario_events(selected) if selected else ([], [])
            ai_status = self.ai.status(selected)
            ai_events = self.ai.read_events(selected)
            trust = self.store.read_trust_overview(selected)
            device = current if run_id is None or run_id == current.run_id else None
        await self._broadcast(events)
        return TelemetryState(device=device, run=run, latest_sample=latest,
            active_alerts=[alert for alert in alerts if alert.status == "ACTIVE"],
            rule_alerts=alerts, rejections=rejections, ai_status=ai_status, ai_events=ai_events,
            trust=trust, device_last_seen_at=self._last_device_seen_at)

    async def history(self, run_id: str, after_sequence: int | None, limit: int) -> TelemetryHistory | None:
        return self.store.read_history(run_id, after_sequence, limit)

    async def event_history(self, run_id: str, after_id: int, limit: int) -> OperatorEventHistory | None:
        return self.store.read_events(run_id, after_id, limit)

    async def ai_event_history(self, run_id: str) -> list[AIEventPayload] | None:
        run, _ = self.store.read_state(run_id)
        return self.ai.read_events(run_id) if run else None

    async def trust_overview(self, run_id: str | None = None) -> dict:
        async with self._lock:
            current, events = self._sync_locked()
            selected = run_id or current.run_id
            overview = self.store.read_trust_overview(selected)
        await self._broadcast(events)
        return overview

    async def trust_decisions(self, run_id: str, before_id: int | None, limit: int) -> dict | None:
        return self.store.read_trust_decisions(run_id, before_id, limit)

    async def trust_decision(self, run_id: str, assessment_id: int) -> dict | None:
        return self.store.read_trust_decision(run_id, assessment_id)

    async def command(self, action: str, scenario: ScenarioName = ScenarioName.NORMAL_MISSION,
                      actor: Principal | None = None) -> SimulatorSnapshot:
        if self.external:
            raise InvalidTransition(action, self._external_snapshot.status, "İdarəetmə ORBITRA Device tətbiqindədir.")
        failure: InvalidTransition | None = None
        async with self._lock:
            before, events = self._sync_locked()
            try:
                result = self.device.start(scenario) if action == "start" else getattr(self.device, action)()
            except InvalidTransition as exc:
                failure = exc
                rejected = self.store.record_operation(action, before, before, "REJECTED", exc.reason, actor)
                events.append({"type": "operator_event", **rejected.model_dump(mode="json")})
                result = before
            else:
                try:
                    reason = {
                        "start": "Yeni lokal simulyasiya sessiyası başladı.",
                        "pause": "Simulyasiya istifadəçi tərəfindən dayandırıldı.",
                        "resume": "Eyni sessiya davam etdirildi.",
                        "reset": "Virtual cihaz IDLE vəziyyətinə qaytarıldı.",
                        "end": "Missiya bitirildi; sessiya davam etdirilə bilməz.",
                        "reduce_processing_load": "Virtual hesablama yükü növbəti addımlar üçün azaldıldı.",
                    }[action]
                    recorded = self.store.record_operation(action, before, result, "SUCCESS", reason, actor)
                except Exception:
                    if action == "start":
                        self.device.reset()
                    raise
                assert self.store.integrity_key is not None
                self._pending.extend(self.device.drain_signed_samples(self.store.integrity_key))
                events.extend(self._flush_locked())
                if action in ("end", "reset") and before.run_id:
                    closed = self.ai.finish_run(before.run_id, datetime.now(timezone.utc))
                    if closed is not None:
                        events.append({"type": "ai_event", **closed.model_dump(mode="json")})
                run, latest = self.store.read_state(result.run_id) if result.run_id else (None, None)
                alerts, rejections = self.store.read_scenario_events(result.run_id) if result.run_id else ([], [])
                ai_status = self.ai.status(result.run_id)
                ai_events = self.ai.read_events(result.run_id)
                trust = self.store.read_trust_overview(result.run_id)
                events.append({
                    "type": "simulation_status", "device": result.model_dump(mode="json"),
                    "run": run.model_dump(mode="json") if run else None,
                    "latest_sample": latest.model_dump(mode="json") if latest else None,
                    "rule_alerts": [alert.model_dump(mode="json") for alert in alerts],
                    "rejections": [rejection.model_dump(mode="json") for rejection in rejections],
                    "ai_status": ai_status.model_dump(mode="json"),
                    "ai_events": [event.model_dump(mode="json") for event in ai_events],
                    "trust": trust,
                })
                events.append({"type": "operator_event", **recorded.model_dump(mode="json")})
        await self._broadcast(events)
        if failure is not None:
            raise failure
        return result

    def _status_event_locked(self, snapshot: SimulatorSnapshot) -> dict:
        selected = snapshot.run_id
        run, latest = self.store.read_state(selected) if selected else (None, None)
        alerts, rejections = self.store.read_scenario_events(selected) if selected else ([], [])
        return {
            "type": "simulation_status", "device": snapshot.model_dump(mode="json"),
            "run": run.model_dump(mode="json") if run else None,
            "latest_sample": latest.model_dump(mode="json") if latest else None,
            "rule_alerts": [item.model_dump(mode="json") for item in alerts],
            "rejections": [item.model_dump(mode="json") for item in rejections],
            "ai_status": self.ai.status(selected).model_dump(mode="json"),
            "ai_events": [item.model_dump(mode="json") for item in self.ai.read_events(selected)],
            "trust": self.store.read_trust_overview(selected),
            "device_last_seen_at": self._last_device_seen_at.isoformat() if self._last_device_seen_at else None,
        }

    async def receive_control(self, action: str, snapshot: SimulatorSnapshot, signature: str) -> dict:
        """Apply an HMAC-authenticated Device lifecycle event to the Main database."""
        if not self.external or self.store.integrity_key is None:
            raise RuntimeError("External Device ingress is unavailable")
        if not verify_control(action, snapshot, signature, self.store.integrity_key):
            raise ValueError("INVALID_CONTROL_SIGNATURE")
        if snapshot.schema_version != "1.0" or snapshot.updated_at.tzinfo is None:
            raise ValueError("INVALID_CONTROL_FORMAT")
        events: list[dict] = []
        async with self._lock:
            before = self._external_snapshot
            if action == "heartbeat":
                if snapshot.run_id != before.run_id or snapshot.status != before.status:
                    raise ValueError("RUN_MISMATCH")
                self._last_device_seen_at = datetime.now(timezone.utc)
                return {"accepted": True, "action": action}
            if action == "start":
                if before.status not in (DeviceStatus.IDLE, DeviceStatus.ENDED) or snapshot.status != DeviceStatus.RUNNING or not snapshot.run_id or not snapshot.scenario or snapshot.simulation_elapsed_seconds != 0:
                    raise ValueError("INVALID_START_TRANSITION")
                try:
                    UUID(snapshot.run_id)
                except ValueError as exc:
                    raise ValueError("INVALID_RUN_ID") from exc
                if self.store.read_state(snapshot.run_id)[0] is not None:
                    raise ValueError("DUPLICATE_RUN_ID")
            elif action == "reset":
                if snapshot.status != DeviceStatus.IDLE or snapshot.run_id is not None or snapshot.scenario is not None:
                    raise ValueError("INVALID_RESET_TRANSITION")
            else:
                transitions = {
                    "pause": (DeviceStatus.RUNNING, DeviceStatus.PAUSED),
                    "resume": (DeviceStatus.PAUSED, DeviceStatus.RUNNING),
                    "end": (DeviceStatus.RUNNING, DeviceStatus.ENDED),
                    "reduce_processing_load": (DeviceStatus.RUNNING, DeviceStatus.RUNNING),
                }
                if action not in transitions:
                    raise ValueError("UNKNOWN_CONTROL_ACTION")
                expected_before, expected_after = transitions[action]
                if (before.status != expected_before or snapshot.status != expected_after or
                        not before.run_id or snapshot.run_id != before.run_id or snapshot.scenario != before.scenario or
                        snapshot.simulation_elapsed_seconds < before.simulation_elapsed_seconds):
                    # End is also allowed directly from a paused run.
                    if not (action == "end" and before.status == DeviceStatus.PAUSED and
                            snapshot.status == DeviceStatus.ENDED and snapshot.run_id == before.run_id and
                            snapshot.scenario == before.scenario):
                        raise ValueError("INVALID_CONTROL_TRANSITION")
            reasons = {
                "start": "Device tətbiqində yeni sessiya başladı.",
                "pause": "Device simulyasiyası dayandırıldı.",
                "resume": "Device sessiyası davam etdirildi.",
                "reset": "Device ilkin vəziyyətinə qaytarıldı.",
                "end": "Device sessiyası bitirildi.",
                "reduce_processing_load": "Device virtual yükü azaltdı.",
            }
            event = self.store.record_operation(action, before, snapshot, "SUCCESS", reasons[action],
                                                source_override="device_backend")
            self._external_snapshot = snapshot
            self._last_device_seen_at = datetime.now(timezone.utc)
            if action in ("end", "reset") and before.run_id:
                closed = self.ai.finish_run(before.run_id, datetime.now(timezone.utc))
                if closed is not None:
                    events.append({"type": "ai_event", **closed.model_dump(mode="json")})
            events.append(self._status_event_locked(snapshot))
            events.append({"type": "operator_event", **event.model_dump(mode="json")})
        await self._broadcast(events)
        return {"accepted": True, "action": action, "run_id": snapshot.run_id}

    async def receive_packet(self, packet: SignedTelemetryPacket) -> dict:
        """Gate, persist and broadcast exactly one Device packet in Main."""
        if not self.external or self.store.integrity_key is None:
            raise RuntimeError("External Device ingress is unavailable")
        async with self._lock:
            current = self._external_snapshot
            self._last_device_seen_at = datetime.now(timezone.utc)
            rejection = None
            code = None
            if not current.run_id or packet.snapshot.run_id != current.run_id or packet.snapshot.scenario != current.scenario:
                code = "RUN_REJECTED"
                reason = f"Run və ya ssenari uyğun gəlmir; göndərilən run: {packet.snapshot.run_id}."
            elif current.status != DeviceStatus.RUNNING or packet.snapshot.status != DeviceStatus.RUNNING:
                code = "STATE_REJECTED"
                reason = "Device RUNNING vəziyyətində deyil; paket qəbul edilmədi."
            if code:
                if not current.run_id:
                    security.audit("TELEMETRY_REJECTION", "REJECTED", code,
                                   run_id=packet.snapshot.run_id, sequence_number=packet.snapshot.simulation_elapsed_seconds)
                    raise ValueError(code)
                rejection = self.store._reject_packet(packet, code, reason, time.perf_counter(),
                    {"schema_valid": True, "evidence": {"packet_run_id": packet.snapshot.run_id}},
                    self.ai.metadata["version"] if self.ai.metadata else None, run_id_override=current.run_id)
                events = [{"type": "telemetry_rejected", **rejection.model_dump(mode="json")},
                          {"type": "trust_assessment", "run_id": current.run_id,
                           "trust": self.store.read_trust_overview(current.run_id)}]
            else:
                self._pending.append(packet)
                events = self._flush_locked()
                if any(event["type"] == "telemetry_sample" for event in events):
                    self._external_snapshot = packet.snapshot
            accepted = any(event["type"] == "telemetry_sample" for event in events)
            if rejection is None:
                rejected_event = next((event for event in events if event["type"] == "telemetry_rejected"), None)
                reason_code = rejected_event["reason_code"] if rejected_event else None
            else:
                reason_code = rejection.reason_code
        await self._broadcast(events)
        return {"accepted": accepted, "reason_code": reason_code,
                "run_id": packet.snapshot.run_id, "sequence_number": packet.snapshot.simulation_elapsed_seconds}

    async def reject_malformed(self, raw_payload: object) -> dict:
        """Quarantine malformed JSON against the active run without trusting client fields."""
        async with self._lock:
            current = self._external_snapshot
            if not current.run_id:
                security.audit("TELEMETRY_REJECTION", "REJECTED", "SCHEMA_REJECTED")
                return {"accepted": False, "reason_code": "SCHEMA_REJECTED", "run_id": None}
            raw = raw_payload if isinstance(raw_payload, dict) else {}
            attempted = raw.get("snapshot") if isinstance(raw.get("snapshot"), dict) else {}
            sequence = attempted.get("simulation_elapsed_seconds")
            if not isinstance(sequence, int) or sequence < 1:
                sequence = max(1, current.simulation_elapsed_seconds + 1)
            synthetic = current.model_copy(update={"schema_version": "invalid-format",
                                                    "simulation_elapsed_seconds": sequence})
            packet = SignedTelemetryPacket(snapshot=synthetic,
                source_id=str(raw.get("source_id", "invalid"))[:64],
                signature=str(raw.get("signature", ""))[:128],
                packet_id=str(raw.get("packet_id", uuid4()))[:36])
            rejection = self.store._reject_packet(packet, "SCHEMA_REJECTED",
                "Paket formatı müqaviləyə uyğun deyil.", time.perf_counter(),
                {"schema_valid": False, "evidence": {"format_error": "pydantic_validation"}},
                self.ai.metadata["version"] if self.ai.metadata else None,
                raw_payload_override=raw_payload)
            events = [{"type": "telemetry_rejected", **rejection.model_dump(mode="json")},
                      {"type": "trust_assessment", "run_id": current.run_id,
                       "trust": self.store.read_trust_overview(current.run_id)}]
        await self._broadcast(events)
        return {"accepted": False, "reason_code": "SCHEMA_REJECTED",
                "run_id": current.run_id, "sequence_number": sequence}

    async def connect(self, websocket: WebSocket, principal: Principal) -> None:
        await websocket.accept()
        async with self._lock:
            current, events = self._sync_locked()
            run, latest = self.store.read_state(current.run_id) if current.run_id else (None, None)
            alerts, rejections = self.store.read_scenario_events(current.run_id) if current.run_id else ([], [])
            ai_status = self.ai.status(current.run_id)
            ai_events = self.ai.read_events(current.run_id)
            trust = self.store.read_trust_overview(current.run_id)
            await websocket.send_json({
                "type": "simulation_status",
                "device": current.model_dump(mode="json"),
                "run": run.model_dump(mode="json") if run else None,
                "latest_sample": latest.model_dump(mode="json") if latest else None,
                "rule_alerts": [alert.model_dump(mode="json") for alert in alerts],
                "rejections": [rejection.model_dump(mode="json") for rejection in rejections],
                "ai_status": ai_status.model_dump(mode="json"),
                "ai_events": [event.model_dump(mode="json") for event in ai_events],
                "trust": trust,
                "device_last_seen_at": self._last_device_seen_at.isoformat() if self._last_device_seen_at else None,
            })
            self._clients.add(websocket)
            self._client_tokens[websocket] = principal.token
        await self._broadcast(events)

    def disconnect(self, websocket: WebSocket) -> None:
        self._clients.discard(websocket)
        self._client_tokens.pop(websocket, None)

    async def revoke_token(self, token: str) -> None:
        for websocket, active_token in tuple(self._client_tokens.items()):
            if active_token == token:
                try:
                    await websocket.close(code=1008)
                finally:
                    self.disconnect(websocket)

    async def start(self) -> None:
        if self.store.integrity_key is None:
            raise RuntimeError("TELEMETRY_HMAC_KEY is not configured; run python -m scripts.setup_security")
        self.store.mark_interrupted_runs()
        self.ai.mark_interrupted()
        self.ai.initialize()
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run_loop(self) -> None:
        last_heartbeat = time.monotonic()
        while True:
            await asyncio.sleep(0.25)
            try:
                snapshot = await self.tick()
                if time.monotonic() - last_heartbeat >= 3:
                    await self._broadcast([{
                        "type": "heartbeat",
                        "sent_at": datetime.now(timezone.utc).isoformat(),
                        "run_id": snapshot.run_id,
                        "status": snapshot.status.value,
                        "device_last_seen_at": self._last_device_seen_at.isoformat() if self._last_device_seen_at else None,
                    }])
                    last_heartbeat = time.monotonic()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Telemetry tick failed; will retry")


telemetry = TelemetryCoordinator(simulator, TelemetryStore(engine, settings.telemetry_hmac_key_bytes), external=False)

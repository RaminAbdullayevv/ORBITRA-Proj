"""One-run report assembled only from committed SQLite records."""

import json
from datetime import datetime, timezone

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.models import (AIEvent, AuditEvent, OperatorEvent, ReportGeneration, RejectedTelemetry,
                        RuleAlert, RunAnalysis, SecurityIncident, SimulationRun, TelemetrySample, TrustAssessment, User)
from app.sentinel import RULESET_VERSION
from app.cyber_demo import summarize_tests
from app.simulator import SensorReadings
from app.subsystems import RULES_VERSION, final_subsystems


def list_runs(engine: Engine) -> list[dict]:
    with Session(engine) as db:
        rows = db.scalars(select(SimulationRun).order_by(SimulationRun.started_at.desc()).limit(100)).all()
        return [{"run_id": row.run_id, "scenario": row.scenario, "started_at": row.started_at,
                 "ended_at": row.ended_at, "status": row.last_status} for row in rows]


def generate_report(engine: Engine, run_id: str) -> str | None:
    with Session(engine) as db:
        run = db.get(SimulationRun, run_id)
        if run is None:
            return None
        if run.last_status != "ENDED":
            raise ValueError("Yekun hesabat yalnız ENDED sessiyası üçün yaradılır.")
        saved = db.get(ReportGeneration, run_id)
        if saved is None:
            proof = db.get(RunAnalysis, run_id)
            saved = ReportGeneration(run_id=run_id, generated_at=datetime.now(timezone.utc).isoformat(),
                                     rules_version=RULES_VERSION,
                                     model_version=proof.model_version if proof else None)
            db.add(saved)
            db.commit()
        return saved.generated_at


def read_report(engine: Engine, run_id: str) -> dict | None:
    with Session(engine) as db:
        run = db.get(SimulationRun, run_id)
        if run is None:
            return None
        latest = db.scalar(select(TelemetrySample).where(TelemetrySample.run_id == run_id)
                           .order_by(TelemetrySample.sequence_number.desc()).limit(1))
        accepted_count = db.scalar(select(func.count()).select_from(TelemetrySample)
                                   .where(TelemetrySample.run_id == run_id)) or 0
        rejections = db.scalars(select(RejectedTelemetry).where(RejectedTelemetry.run_id == run_id)
                                .order_by(RejectedTelemetry.rejected_at)).all()
        alerts = db.scalars(select(RuleAlert).where(RuleAlert.run_id == run_id)
                            .order_by(RuleAlert.opened_at)).all()
        ai_events = db.scalars(select(AIEvent).where(AIEvent.run_id == run_id)
                               .order_by(AIEvent.started_at)).all()
        incidents = db.scalars(select(SecurityIncident).where(SecurityIncident.run_id == run_id)
                               .order_by(SecurityIncident.created_at)).all()
        audit = db.scalars(select(AuditEvent).where(AuditEvent.run_id == run_id)
                          .order_by(AuditEvent.occurred_at)).all()
        operations = db.scalars(select(OperatorEvent).where(OperatorEvent.run_id == run_id)
                               .order_by(OperatorEvent.event_number)).all()
        user_ids = {item.user_id for item in operations if item.user_id is not None}
        usernames = {row.id: row.username for row in db.scalars(select(User).where(User.id.in_(user_ids)))} if user_ids else {}
        proof = db.get(RunAnalysis, run_id)
        generation = db.get(ReportGeneration, run_id)
        latest_trusted = db.scalar(select(TrustAssessment).where(TrustAssessment.mission_id == run_id,
            TrustAssessment.accepted.is_(True)).order_by(TrustAssessment.id.desc()).limit(1))
        trust_counts = dict(db.execute(select(TrustAssessment.final_verdict, func.count()).where(
            TrustAssessment.mission_id == run_id).group_by(TrustAssessment.final_verdict)).all())
        critical_trust = db.scalars(select(TrustAssessment).where(
            TrustAssessment.mission_id == run_id, TrustAssessment.severity.in_(("CRITICAL", "WARNING")))
            .order_by(TrustAssessment.id)).all()
        all_trust = db.scalars(select(TrustAssessment).where(
            TrustAssessment.mission_id == run_id).order_by(TrustAssessment.id)).all()
        cyber_security = summarize_tests([{
            "packet_id": item.packet_id, "sequence_number": item.sequence_number,
            "received_at": item.received_at, "accepted": item.accepted,
            "explanation": item.explanation, "evidence": json.loads(item.evidence_json),
        } for item in all_trust])
        last_action_seconds = max((item.simulation_elapsed_seconds for item in operations), default=0)
        duration = max(latest.simulation_elapsed_seconds if latest else 0, last_action_seconds)
        active_alert_codes = {item.rule_code for item in alerts if item.status == "ACTIVE"}
        reason_rows = incidents or rejections
        reasons = [item.reason_code for item in reason_rows]
        return {
            "run_id": run_id, "scenario": run.scenario, "status": run.last_status,
            "preview": run.last_status != "ENDED", "started_at": run.started_at, "ended_at": run.ended_at,
            "generated_at": generation.generated_at if generation else None,
            "rules_version": generation.rules_version if generation else RULES_VERSION,
            "model_version": (proof.model_version if proof else ai_events[0].model_version if ai_events else None),
            "ai_analysis": "EVALUATED" if proof or ai_events else "NOT_VERIFIABLE",
            "last_ai_evaluated_at": proof.last_evaluated_at if proof else None,
            "duration_seconds": duration, "accepted_count": accepted_count,
            "rejected_count": len(reason_rows), "rejection_reasons": reasons,
            "sequence_gaps": max(0, latest.sequence_number - accepted_count) if latest else 0,
            "latest_sample": ({"sequence_number": latest.sequence_number, "sample_time": latest.sample_time,
                               "sensors": {key: getattr(latest, key) for key in SensorReadings.model_fields}}
                              if latest else None),
            "subsystems": final_subsystems(latest, active_alert_codes,
                                            latest_trusted.final_verdict if latest_trusted else None),
            "telemetry_trust": {
                "accepted": accepted_count, "rejected": len(rejections), "quarantined": len(rejections),
                "system_anomaly": trust_counts.get("PROBABLE SYSTEM ANOMALY", 0),
                "sensor_fault": trust_counts.get("PROBABLE SENSOR FAULT", 0),
                "integrity_incident": trust_counts.get("INTEGRITY INCIDENT", 0),
                "replay_incident": trust_counts.get("REPLAY INCIDENT", 0),
                "stale_data": trust_counts.get("STALE DATA", 0),
                "ruleset_version": RULESET_VERSION,
                "model_version": proof.model_version if proof else None,
                "final_status": "NO DATA" if latest is None else
                    "DEGRADED" if any(item.status == "OPEN" for item in incidents) or
                    (rejections and rejections[-1].rejected_at > latest.sample_time) else
                    "TRUSTED HISTORICAL",
                "key_decisions": [{"id": item.id, "packet_id": item.packet_id,
                    "verdict": item.final_verdict, "explanation": item.explanation,
                    "evidence": json.loads(item.evidence_json)} for item in critical_trust],
            },
            "rule_alerts": [{"rule_code": item.rule_code, "reason": item.reason, "opened_at": item.opened_at,
                             "closed_at": item.closed_at, "status": item.status,
                             "metric_key": item.metric_key, "metric_value": item.metric_value}
                            for item in alerts],
            "ai_events": [{"event_id": item.event_id, "model_version": item.model_version,
                           "started_at": item.started_at, "ended_at": item.ended_at, "status": item.status,
                           "score": item.score, "explanation": item.explanation,
                           "start_sequence_number": item.start_sequence_number} for item in ai_events],
            "cyber_security": cyber_security,
            "security_incidents": [{"incident_id": item.incident_id, "created_at": item.created_at,
                                    "reason_code": item.reason_code, "summary": item.summary,
                                    "sequence_number": item.sequence_number, "status": item.status,
                                    "close_reason": item.close_reason} for item in incidents],
            "security_audit": [{"occurred_at": item.occurred_at, "action": item.action,
                                "outcome": item.outcome, "reason_code": item.reason_code,
                                "sequence_number": item.sequence_number} for item in audit],
            "operator_events": [{"event_number": item.event_number, "action": item.action,
                                 "received_at": item.received_at, "outcome": item.outcome,
                                 "reason": item.reason, "user_id": item.user_id,
                                 "username": usernames.get(item.user_id),
                                 "simulation_elapsed_seconds": item.simulation_elapsed_seconds}
                                for item in operations],
            "quality_note": ("Son etibarlı nümunə yoxdur; alt-sistemlərin vəziyyəti məlum deyil." if latest is None else
                             "Qəbul edilmiş nümunələr əsasında yekun vəziyyət. Rədd paketləri ölçmə sayılmır."),
            "limitations": ["Yalnız lokal sintetik tədris modelidir; fiziki aparatla kalibrasiya edilməyib.",
                            "AI balı nasazlıq ehtimalı deyil; köhnə sessiyada qiymətləndirmə sübutu olmaya bilər.",
                            "Server prosesi yenidən başladıqda aktiv sessiya davam etdirilmir."],
        }

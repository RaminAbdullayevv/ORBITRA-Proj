"""Read-only audit and analyst incident decisions."""

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Principal, current_principal, require_analyst, security, utc_now
from app.models import AuditEvent, IncidentNote, RejectedTelemetry, SecurityIncident, TrustAssessment, User
from app.cyber_demo import mitre_similarity


router = APIRouter(prefix="/api/v1/security", tags=["security"])


class NoteRequest(BaseModel):
    body: str = Field(min_length=2, max_length=1000)


class CloseRequest(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


def _overview() -> dict:
    with Session(security.engine) as db:
        incidents = list(db.scalars(select(SecurityIncident).order_by(SecurityIncident.created_at.desc()).limit(200)))
        audits = list(db.scalars(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(200)))
        incident_ids = [item.incident_id for item in incidents]
        rejections = {item.incident_id: item for item in db.scalars(select(RejectedTelemetry).where(
            RejectedTelemetry.incident_id.in_(incident_ids)))} if incident_ids else {}
        assessments = {item.incident_id: item for item in db.scalars(select(TrustAssessment).where(
            TrustAssessment.incident_id.in_(incident_ids)))} if incident_ids else {}
        notes = list(db.scalars(select(IncidentNote).where(IncidentNote.incident_id.in_(incident_ids))
                                .order_by(IncidentNote.created_at))) if incident_ids else []
        user_ids = {item.author_user_id for item in notes} | {item.closed_by_user_id for item in incidents if item.closed_by_user_id}
        users = {id_: db.get(User, id_) for id_ in user_ids}
        note_map: dict[str, list[dict]] = {}
        for note in notes:
            note_map.setdefault(note.incident_id, []).append({
                "id": note.id, "body": note.body, "created_at": note.created_at,
                "author_user_id": note.author_user_id,
                "author_username": users[note.author_user_id].username if users.get(note.author_user_id) else None,
            })
        def detail(row: SecurityIncident) -> dict | None:
            assessment = assessments.get(row.incident_id)
            rejection = rejections.get(row.incident_id)
            if assessment is None and rejection is None:
                return None
            evidence = json.loads(assessment.evidence_json) if assessment else {}
            payload = json.loads(rejection.raw_payload_json) if rejection and rejection.raw_payload_json else {}
            return {
                "test_name": evidence.get("test_name"), "test_kind": evidence.get("test_kind"),
                "observed_reason_code": row.reason_code, "observed_reason": row.summary,
                "outcome": "REJECTED" if rejection else "REVIEW_REQUIRED",
                "affected_block": evidence.get("affected_block", "telemetry"),
                "packet_id": rejection.packet_id if rejection else assessment.packet_id,
                "sent": {"source_id": row.source_id, "sequence_number": row.sequence_number,
                         "sample_time": payload.get("updated_at"), "sensors": payload.get("sensors")},
                "checks": {"schema_valid": assessment.schema_valid if assessment else None,
                           "source_valid": assessment.source_valid if assessment else None,
                           "signature_valid": assessment.signature_valid if assessment else None,
                           "replay_detected": assessment.replay_detected if assessment else None,
                           "freshness_valid": assessment.freshness_valid if assessment else None},
                "action": "Paket karantinə alındı; normal qrafikə və AI temperatur analizinə daxil edilmədi."
                          if rejection else "Operator araşdırması tələb olunur.",
                "mitre": mitre_similarity(evidence.get("test_kind"), row.reason_code),
            }
        return {
            "incidents": [{
                "incident_id": row.incident_id, "created_at": row.created_at, "kind": row.kind,
                "status": row.status, "reason_code": row.reason_code, "summary": row.summary,
                "run_id": row.run_id, "source_id": row.source_id,
                "sequence_number": row.sequence_number, "closed_at": row.closed_at,
                "closed_by_user_id": row.closed_by_user_id,
                "closed_by_username": users[row.closed_by_user_id].username if row.closed_by_user_id and users.get(row.closed_by_user_id) else None,
                "close_reason": row.close_reason, "notes": note_map.get(row.incident_id, []),
                "detail": detail(row),
            } for row in incidents],
            "audit": [{
                "id": row.id, "occurred_at": row.occurred_at, "user_id": row.user_id,
                "username": row.username, "action": row.action, "outcome": row.outcome,
                "reason_code": row.reason_code, "run_id": row.run_id,
                "incident_id": row.incident_id, "sequence_number": row.sequence_number,
            } for row in audits],
        }


@router.get("/overview")
def overview(_: Principal = Depends(current_principal)) -> dict:
    return _overview()


@router.post("/incidents/{incident_id}/notes", status_code=201)
def add_note(incident_id: str, payload: NoteRequest, principal: Principal = Depends(require_analyst)) -> dict:
    body = payload.body.strip()
    if len(body) < 2:
        raise HTTPException(status_code=422, detail="Qeyd boş ola bilməz.")
    with Session(security.engine) as db:
        incident = db.get(SecurityIncident, incident_id)
        if incident is None:
            raise HTTPException(status_code=404, detail="İnsident tapılmadı.")
        note = IncidentNote(incident_id=incident_id, author_user_id=principal.user_id,
                            created_at=utc_now().isoformat(), body=body)
        db.add(note)
        security.audit("INCIDENT_NOTE", "SUCCESS", "NOTE_ADDED", user_id=principal.user_id,
                       username=principal.username, run_id=incident.run_id, incident_id=incident_id, db=db)
        db.commit()
        return {"id": note.id, "incident_id": incident_id, "body": body, "created_at": note.created_at,
                "author_user_id": principal.user_id, "author_username": principal.username}


@router.post("/incidents/{incident_id}/close")
def close_incident(incident_id: str, payload: CloseRequest, principal: Principal = Depends(require_analyst)) -> dict:
    reason = payload.reason.strip()
    if len(reason) < 5:
        raise HTTPException(status_code=422, detail="Bağlama səbəbi ən azı 5 simvol olmalıdır.")
    with Session(security.engine) as db:
        incident = db.get(SecurityIncident, incident_id)
        if incident is None:
            raise HTTPException(status_code=404, detail="İnsident tapılmadı.")
        if incident.status != "OPEN":
            raise HTTPException(status_code=409, detail="İnsident artıq bağlanıb.")
        incident.status = "CLOSED"
        incident.closed_at = utc_now().isoformat()
        incident.closed_by_user_id = principal.user_id
        incident.close_reason = reason
        security.audit("INCIDENT_CLOSE", "SUCCESS", "REVIEWED_AND_CLOSED", user_id=principal.user_id,
                       username=principal.username, run_id=incident.run_id, incident_id=incident_id, db=db)
        db.commit()
        return {"incident_id": incident_id, "status": incident.status, "closed_at": incident.closed_at,
                "closed_by_user_id": principal.user_id, "close_reason": reason}

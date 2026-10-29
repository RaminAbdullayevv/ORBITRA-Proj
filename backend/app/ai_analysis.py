"""Read-only anomaly analysis of committed telemetry rows.

The joblib artifact path is fixed inside this project and checked against the
metadata written by scripts.train_ai. No client-provided model is loaded.
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import joblib
import numpy as np
import sklearn
from pydantic import BaseModel, Field
from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session

from app.ai_features import (
    FEATURE_DESCRIPTIONS, FEATURE_NAMES, FEATURE_SENSORS, WINDOW_SECONDS,
    extract_features, feature_vector,
)
from app.models import AIEvent, AIModelVersion, RunAnalysis, TelemetrySample
from app.simulator import SensorReadings


logger = logging.getLogger(__name__)
ARTIFACT_DIR = Path(__file__).resolve().parent.parent / "model_artifacts"
MODEL_FILE = ARTIFACT_DIR / "iforest_normal_v1.joblib"
METADATA_FILE = ARTIFACT_DIR / "metadata.json"


class BaselineDifference(BaseModel):
    description: str
    observed: float
    normal_mean: float
    normal_std: float
    standardized_difference: float


class AIEventPayload(BaseModel):
    event_id: str
    run_id: str
    model_version: str
    started_at: datetime
    updated_at: datetime
    ended_at: datetime | None
    start_sequence_number: int
    latest_sequence_number: int
    window_start_sequence_number: int
    score: float
    affected_sensors: list[str]
    baseline_comparison: dict[str, BaselineDifference]
    explanation: str
    status: str


class AIStatusPayload(BaseModel):
    model_status: str
    model_version: str | None = None
    message: str
    window_seconds: int = WINDOW_SECONDS
    accepted_window_count: int = 0
    latest_score: float | None = None
    threshold: float | None = None
    latest_sequence_number: int | None = None
    last_evaluated_at: datetime | None = None


def _event_payload(row: AIEvent) -> AIEventPayload:
    return AIEventPayload(
        event_id=row.event_id, run_id=row.run_id, model_version=row.model_version,
        started_at=datetime.fromisoformat(row.started_at),
        updated_at=datetime.fromisoformat(row.updated_at),
        ended_at=datetime.fromisoformat(row.ended_at) if row.ended_at else None,
        start_sequence_number=row.start_sequence_number,
        latest_sequence_number=row.latest_sequence_number,
        window_start_sequence_number=row.window_start_sequence_number,
        score=row.score, affected_sensors=json.loads(row.affected_sensors),
        baseline_comparison=json.loads(row.baseline_comparison),
        explanation=row.explanation, status=row.status,
    )


class AIAnalyzer:
    def __init__(self, database_engine: Engine):
        self.engine = database_engine
        self.model = None
        self.metadata: dict | None = None
        self.model_status = "PREPARING"
        self.error_message = "Model yüklənir."
        self._initialized = False
        self._latest: dict[str, AIStatusPayload] = {}
        self._streak: dict[str, int] = {}
        self._normal_streak: dict[str, int] = {}
        self._first_abnormal: dict[str, tuple[int, datetime]] = {}

    def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        if not MODEL_FILE.is_file() or not METADATA_FILE.is_file():
            self.model_status = "NOT_TRAINED"
            self.error_message = "Lokal təlim modeli tapılmadı. python -m scripts.train_ai işlədin."
            return
        try:
            metadata = json.loads(METADATA_FILE.read_text(encoding="utf-8"))
            digest = hashlib.sha256(MODEL_FILE.read_bytes()).hexdigest()
            if digest != metadata["model_sha256"]:
                raise ValueError("Model faylının SHA-256 yoxlaması uyğun gəlmir.")
            if metadata["window_seconds"] != WINDOW_SECONDS or tuple(metadata["feature_names"]) != FEATURE_NAMES:
                raise ValueError("Model xüsusiyyət müqaviləsi uyğun gəlmir.")
            if metadata["sklearn_version"] != sklearn.__version__:
                raise ValueError("Model və scikit-learn versiyaları fərqlidir.")
            model = joblib.load(MODEL_FILE)
            if not hasattr(model, "score_samples"):
                raise ValueError("Model skorlama funksiyasını dəstəkləmir.")
            with Session(self.engine) as db:
                existing = db.get(AIModelVersion, metadata["version"])
                if existing and existing.artifact_sha256 != digest:
                    raise ValueError("Eyni model versiyası fərqli artifact üçün istifadə olunub.")
                if existing is None:
                    db.add(AIModelVersion(
                        version=metadata["version"], trained_at=metadata["trained_at"],
                        training_summary=json.dumps({
                            "scenario": metadata["training_scenario"],
                            "training_seeds": metadata["training_seeds"],
                            "calibration_seeds": metadata["calibration_seeds"],
                            "training_windows": metadata["training_windows"],
                            "calibration_windows": metadata["calibration_windows"],
                            "window_seconds": metadata["window_seconds"],
                        }), artifact_sha256=digest, score_threshold=metadata["threshold"],
                    ))
                    db.commit()
            self.model = model
            self.metadata = metadata
            self.model_status = "READY"
            self.error_message = "Model hazırdır; yalnız qəbul edilmiş sensor pəncərələri qiymətləndirilir."
        except Exception as exc:
            self.model_status = "ERROR"
            self.error_message = str(exc)
            logger.exception("Local AI model could not be loaded")

    def fail(self, exc: Exception) -> None:
        self.model_status = "ERROR"
        self.error_message = f"AI analiz xətası: {exc}"
        logger.exception("AI analysis failed; committed telemetry continues")

    def read_events(self, run_id: str | None) -> list[AIEventPayload]:
        if not run_id:
            return []
        with Session(self.engine) as db:
            rows = list(db.scalars(select(AIEvent).where(AIEvent.run_id == run_id).order_by(AIEvent.start_sequence_number)))
            return [_event_payload(row) for row in rows]

    def _recent_rows(self, run_id: str) -> list[TelemetrySample]:
        with Session(self.engine) as db:
            rows = list(db.scalars(select(TelemetrySample).where(TelemetrySample.run_id == run_id)
                .order_by(TelemetrySample.sequence_number.desc()).limit(WINDOW_SECONDS)))
            rows.reverse()
            return rows

    @staticmethod
    def _contiguous_count(rows: list[TelemetrySample]) -> int:
        if not rows:
            return 0
        count = 1
        for previous, current in zip(reversed(rows[:-1]), reversed(rows[1:])):
            if current.sequence_number != previous.sequence_number + 1:
                break
            count += 1
        return count

    def status(self, run_id: str | None) -> AIStatusPayload:
        self.initialize()
        if self.model_status != "READY":
            return AIStatusPayload(model_status=self.model_status, message=self.error_message)
        assert self.metadata is not None
        if run_id and run_id in self._latest:
            return self._latest[run_id]
        count = self._contiguous_count(self._recent_rows(run_id)) if run_id else 0
        return AIStatusPayload(
            model_status="READY", model_version=self.metadata["version"],
            message=("Model hazırdır; sessiya başlayanda məlumat toplanacaq." if not run_id
                     else "Model məlumat toplayır." if count < WINDOW_SECONDS else "Model hazırdır."),
            accepted_window_count=count, threshold=self.metadata["threshold"],
        )

    def _comparison(self, features: dict[str, float]) -> tuple[dict[str, dict], list[str], str]:
        assert self.metadata is not None
        differences = []
        for name in FEATURE_NAMES:
            baseline = self.metadata["baseline_mean"][name]
            spread = max(self.metadata["baseline_std"][name], 1e-4)
            z = (features[name] - baseline) / spread
            differences.append((abs(z), name, z))
        selected = sorted(differences, reverse=True)[:5]
        comparison = {
            name: {
                "description": FEATURE_DESCRIPTIONS[name], "observed": round(features[name], 4),
                "normal_mean": round(self.metadata["baseline_mean"][name], 4),
                "normal_std": round(self.metadata["baseline_std"][name], 4),
                "standardized_difference": round(z, 2),
            } for _, name, z in selected
        }
        sensors = list(dict.fromkeys(sensor for _, name, _ in selected[:3] for sensor in FEATURE_SENSORS[name]))
        significant = [(name, z) for magnitude, name, z in selected if magnitude >= 2.0][:3]
        if significant:
            phrases = [f"{FEATURE_DESCRIPTIONS[name].lower()} normal bazadan {'yüksəkdir' if z > 0 else 'aşağıdır'}" for name, z in significant]
            explanation = "Müşahidə olunan dəyişikliklər: " + "; ".join(phrases) + "."
        else:
            explanation = "Müşahidə olunan dəyişikliklər: son sensor pəncərəsi normal sessiyalardan fərqlənir."
        return comparison, sensors, explanation

    def assess(self, run_id: str, sequence_number: int, sample_time: datetime) -> tuple[AIStatusPayload, AIEventPayload | None]:
        """Call only after the sample was committed to telemetry_samples."""
        self.initialize()
        if self.model_status != "READY":
            return self.status(run_id), None
        assert self.metadata is not None and self.model is not None
        rows = self._recent_rows(run_id)
        if not rows or rows[-1].sequence_number != sequence_number:
            return self.status(run_id), None
        readings = [(row.sequence_number, SensorReadings(**{
            key: getattr(row, key) for key in SensorReadings.model_fields
        })) for row in rows]
        features = extract_features(readings)
        if features is None:
            self._streak[run_id] = 0
            self._normal_streak[run_id] = 0
            self._first_abnormal.pop(run_id, None)
            result = AIStatusPayload(model_status="READY", model_version=self.metadata["version"],
                message="Model məlumat toplayır; 20 ardıcıl qəbul edilmiş nümunə lazımdır.",
                accepted_window_count=self._contiguous_count(rows), threshold=self.metadata["threshold"])
            self._latest[run_id] = result
            return result, None

        score = float(-self.model.score_samples(np.asarray([feature_vector(features)]))[0])
        result = AIStatusPayload(model_status="READY", model_version=self.metadata["version"],
            message="Son qəbul edilmiş pəncərə qiymətləndirildi.", accepted_window_count=WINDOW_SECONDS,
            latest_score=round(score, 4), threshold=self.metadata["threshold"],
            latest_sequence_number=sequence_number, last_evaluated_at=sample_time)
        self._latest[run_id] = result
        anomalous = score >= self.metadata["threshold"]
        comparison, sensors, explanation = self._comparison(features)
        with Session(self.engine) as db:
            proof = db.get(RunAnalysis, run_id)
            if proof is None:
                db.add(RunAnalysis(run_id=run_id, model_version=self.metadata["version"],
                    last_evaluated_at=sample_time.isoformat(), latest_sequence_number=sequence_number))
            else:
                proof.model_version = self.metadata["version"]
                proof.last_evaluated_at = sample_time.isoformat()
                proof.latest_sequence_number = sequence_number
            active = db.scalars(select(AIEvent).where(AIEvent.run_id == run_id, AIEvent.status == "ACTIVE")
                .order_by(AIEvent.start_sequence_number.desc()).limit(1)).first()
            changed: AIEvent | None = None
            if anomalous:
                self._streak[run_id] = self._streak.get(run_id, 0) + 1
                self._normal_streak[run_id] = 0
                if self._streak[run_id] == 1:
                    self._first_abnormal[run_id] = (sequence_number, sample_time)
                if active is None and self._streak[run_id] >= self.metadata["confirmation_windows"]:
                    first_sequence, first_time = self._first_abnormal[run_id]
                    changed = AIEvent(
                        event_id=str(uuid4()), run_id=run_id, model_version=self.metadata["version"],
                        started_at=first_time.isoformat(), updated_at=sample_time.isoformat(), ended_at=None,
                        start_sequence_number=first_sequence, latest_sequence_number=sequence_number,
                        window_start_sequence_number=sequence_number - WINDOW_SECONDS + 1,
                        score=score, affected_sensors=json.dumps(sensors),
                        baseline_comparison=json.dumps(comparison), explanation=explanation, status="ACTIVE",
                    )
                    db.add(changed)
                elif active is not None:
                    active.updated_at = sample_time.isoformat()
                    active.latest_sequence_number = sequence_number
                    active.window_start_sequence_number = sequence_number - WINDOW_SECONDS + 1
                    active.score = score
                    active.affected_sensors = json.dumps(sensors)
                    active.baseline_comparison = json.dumps(comparison)
                    active.explanation = explanation
                    if sequence_number % 5 == 0:
                        changed = active
                    db.commit()
            else:
                self._streak[run_id] = 0
                self._first_abnormal.pop(run_id, None)
                if active is not None:
                    self._normal_streak[run_id] = self._normal_streak.get(run_id, 0) + 1
                    if self._normal_streak[run_id] >= self.metadata["resolution_windows"]:
                        active.status = "RESOLVED"
                        active.ended_at = sample_time.isoformat()
                        active.updated_at = sample_time.isoformat()
                        changed = active
                        self._normal_streak[run_id] = 0
                if changed is not None:
                    db.commit()
            if changed is not None:
                db.commit()
                return result, _event_payload(changed)
            db.commit()
        return result, None

    def finish_run(self, run_id: str | None, finished_at: datetime) -> AIEventPayload | None:
        if not run_id:
            return None
        with Session(self.engine) as db:
            active = db.scalars(select(AIEvent).where(AIEvent.run_id == run_id, AIEvent.status == "ACTIVE")
                .order_by(AIEvent.start_sequence_number.desc()).limit(1)).first()
            if active is None:
                return None
            active.status = "ENDED"
            active.ended_at = finished_at.isoformat()
            active.updated_at = finished_at.isoformat()
            db.commit()
            return _event_payload(active)

    def mark_interrupted(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with Session(self.engine) as db:
            db.execute(update(AIEvent).where(AIEvent.status == "ACTIVE")
                .values(status="ENDED", ended_at=now, updated_at=now))
            db.commit()

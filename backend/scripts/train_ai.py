"""Reproducibly train the local Isolation Forest from normal simulator runs.

Run from backend: python -m scripts.train_ai
Only this script writes the trusted model_artifacts directory.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.ensemble import IsolationForest

from app.ai_features import FEATURE_NAMES, WINDOW_SECONDS, extract_features, feature_vector
from app.simulator import ScenarioName, VirtualSpacecraftSimulator


MODEL_VERSION = "iforest-normal-v1"
MODEL_SEED = 62026
TRAIN_SEEDS = [101, 102, 103, 104, 105, 106, 107, 108]
CALIBRATION_SEEDS = [201, 202, 203, 204, 24092026]
TEST_NORMAL_SEEDS = [901, 902, 903, 904]
TEST_ANOMALY_SEEDS = [1001, 1002, 1003, 1004]
SESSION_SECONDS = 110
CONFIRM_WINDOWS = 3
RESOLVE_WINDOWS = 10
ARTIFACT_DIR = Path(__file__).resolve().parent.parent / "model_artifacts"


class Clock:
    def __init__(self):
        self.time = 100.0

    def __call__(self):
        return self.time

    def advance(self):
        self.time += 1.0


def session_windows(seed: int, scenario: ScenarioName, reduce_at: int | None = None) -> list[tuple[int, dict[str, float]]]:
    """Use the existing simulator; the scenario label is only evaluation truth."""
    clock = Clock()
    device = VirtualSpacecraftSimulator(clock=clock, seed=seed)
    device.start(scenario)
    accepted: list[tuple[int, object]] = []
    windows: list[tuple[int, dict[str, float]]] = []
    for _ in range(SESSION_SECONDS):
        if reduce_at is not None and device.snapshot().simulation_elapsed_seconds == reduce_at:
            device.reduce_processing_load()
        clock.advance()
        device.snapshot()
        for sample in device.drain_samples():
            if sample.schema_version != "1.0":
                continue
            accepted.append((sample.simulation_elapsed_seconds, sample.sensors))
            features = extract_features(accepted[-WINDOW_SECONDS:])
            if features is not None:
                windows.append((sample.simulation_elapsed_seconds, features))
    return windows


def model_scores(model: IsolationForest, windows: list[tuple[int, dict[str, float]]]) -> list[tuple[int, float]]:
    values = np.asarray([feature_vector(features) for _, features in windows])
    scores = -model.score_samples(values)
    return [(windows[index][0], float(score)) for index, score in enumerate(scores)]


def confirmed_sequences(scores: list[tuple[int, float]], threshold: float) -> list[int]:
    streak = 0
    events: list[int] = []
    in_event = False
    normal_streak = 0
    for sequence, score in scores:
        if score >= threshold:
            streak += 1
            normal_streak = 0
            if streak >= CONFIRM_WINDOWS and not in_event:
                events.append(sequence)
                in_event = True
        else:
            streak = 0
            if in_event:
                normal_streak += 1
                if normal_streak >= RESOLVE_WINDOWS:
                    in_event = False
    return events


def main() -> None:
    training = [session_windows(seed, ScenarioName.NORMAL_MISSION, reduce_at) for seed in TRAIN_SEEDS for reduce_at in (None, 45)]
    calibration = [session_windows(seed, ScenarioName.NORMAL_MISSION, reduce_at) for seed in CALIBRATION_SEEDS for reduce_at in (None, 45)]
    matrix = np.asarray([feature_vector(features) for session in training for _, features in session])
    model = IsolationForest(n_estimators=180, max_samples=256, random_state=MODEL_SEED, n_jobs=1)
    model.fit(matrix)
    calibration_session_scores = [model_scores(model, session) for session in calibration]
    calibration_scores = [score for session in calibration_session_scores for _, score in session]
    candidates = sorted({round(score + 0.0005, 4) for score in calibration_scores})
    threshold = next(value for value in candidates if all(
        len(confirmed_sequences(session, value)) == 0 for session in calibration_session_scores
    ))
    baseline_mean = dict(zip(FEATURE_NAMES, np.mean(matrix, axis=0).tolist()))
    baseline_std = dict(zip(FEATURE_NAMES, np.std(matrix, axis=0).tolist()))

    # The holdout is evaluated only after the model and calibration threshold are fixed.
    normal_results = []
    for seed in TEST_NORMAL_SEEDS:
        for reduce_at in (None, 45):
            windows = session_windows(seed, ScenarioName.NORMAL_MISSION, reduce_at)
            detected = confirmed_sequences(model_scores(model, windows), threshold)
            normal_results.append({"seed": seed, "reduce_at": reduce_at, "false_alerts": len(detected), "alert_sequences": detected})
    anomaly_results = []
    for seed in TEST_ANOMALY_SEEDS:
        windows = session_windows(seed, ScenarioName.TEMPERATURE_ANOMALY)
        detected = confirmed_sequences(model_scores(model, windows), threshold)
        first = detected[0] if detected else None
        anomaly_results.append({"seed": seed, "detected": first is not None,
                                "first_alert_sequence": first, "delay_seconds_from_t8": first - 8 if first else None})

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    model_path = ARTIFACT_DIR / "iforest_normal_v1.joblib"
    joblib.dump(model, model_path, compress=3)
    digest = hashlib.sha256(model_path.read_bytes()).hexdigest()
    metadata = {
        "version": MODEL_VERSION, "trained_at": datetime.now(timezone.utc).isoformat(),
        "sklearn_version": sklearn.__version__, "random_seed": MODEL_SEED,
        "window_seconds": WINDOW_SECONDS, "feature_names": list(FEATURE_NAMES),
        "training_scenario": "NORMAL_MISSION", "training_seeds": TRAIN_SEEDS,
        "normal_load_reduction_at": [None, 45],
        "calibration_seeds": CALIBRATION_SEEDS, "test_normal_seeds": TEST_NORMAL_SEEDS,
        "test_anomaly_seeds": TEST_ANOMALY_SEEDS, "session_seconds": SESSION_SECONDS,
        "training_windows": sum(len(session) for session in training),
        "calibration_windows": sum(len(session) for session in calibration),
        "threshold": threshold, "confirmation_windows": CONFIRM_WINDOWS,
        "threshold_selection": "Lowest calibration-only cutoff with zero confirmed events; 0.0005 margin",
        "resolution_windows": RESOLVE_WINDOWS,
        "baseline_mean": baseline_mean, "baseline_std": baseline_std,
        "model_sha256": digest,
    }
    (ARTIFACT_DIR / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    report = {
        "model_version": MODEL_VERSION, "threshold_fixed_from_calibration": threshold,
        "normal_holdout": normal_results, "anomaly_holdout": anomaly_results,
        "true_synthetic_events": len(TEST_ANOMALY_SEEDS),
        "detected_synthetic_events": sum(item["detected"] for item in anomaly_results),
        "missed_synthetic_events": sum(not item["detected"] for item in anomaly_results),
        "false_alerts": sum(item["false_alerts"] for item in normal_results),
        "detection_delay_seconds": [item["delay_seconds_from_t8"] for item in anomaly_results if item["detected"]],
        "scope": "Ayrı sintetik simulator sessiyaları; real aparat dəqiqliyi deyil.",
    }
    (ARTIFACT_DIR / "training_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()

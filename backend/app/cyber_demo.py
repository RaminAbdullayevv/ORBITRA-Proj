"""Evidence labels for bounded, synthetic telemetry security tests.

A selected test records intent. The observed validation result supplies the evidence;
these labels never attribute an actor or identify a real-world attack.
"""

CYBER_TESTS = {
    "REPLAY": {
        "name": "Təkrar paket — Replay test",
        "expected_reason_code": "REPLAY_REJECTED",
        "affected_block": "communications",
    },
    "SPOOFING": {
        "name": "Saxta telemetriya mənbəyi — Telemetry Spoofing test",
        "expected_reason_code": "SOURCE_REJECTED",
        "affected_block": "communications",
    },
    "INTEGRITY": {
        "name": "Dəyişdirilmiş paket — Integrity test",
        "expected_reason_code": "INTEGRITY_REJECTED",
        "affected_block": "thermal",
    },
}


def test_evidence(kind: str | None) -> dict:
    if kind not in CYBER_TESTS:
        return {}
    test = CYBER_TESTS[kind]
    return {"test_kind": kind, "test_name": test["name"],
            "expected_reason_code": test["expected_reason_code"],
            "affected_block": test["affected_block"]}


def mitre_similarity(kind: str | None, observed_reason_code: str | None) -> dict | None:
    if kind == "SPOOFING" and observed_reason_code == "SOURCE_REJECTED":
        return {"code": "T1692.002", "name": "Reporting Message",
                "url": "https://attack.mitre.org/techniques/T1692/002/",
                "qualification": "Nəzəri uyğunluq; real hücumçu müəyyən edilməyib."}
    return None


def summarize_tests(rows: list[dict]) -> dict:
    """Compute the virtual-test rate from persisted, observed assessments."""
    events = []
    for row in rows:
        evidence = row["evidence"]
        kind = evidence.get("test_kind")
        if kind not in CYBER_TESTS:
            continue
        observed = evidence.get("rejection_code") if not row["accepted"] else None
        expected = CYBER_TESTS[kind]["expected_reason_code"]
        detected = not row["accepted"] and observed == expected
        events.append({
            "test_kind": kind, "test_name": CYBER_TESTS[kind]["name"],
            "packet_id": row["packet_id"], "sequence_number": row["sequence_number"],
            "created_at": row["received_at"], "expected_reason_code": expected,
            "observed_reason_code": observed, "outcome": "ACCEPTED" if row["accepted"] else "REJECTED",
            "detected_correctly": detected, "affected_block": CYBER_TESTS[kind]["affected_block"],
            "operator_alert": row["explanation"] if not row["accepted"] else
                "Test paketi qəbul edilib; nəticə araşdırılmalıdır.",
            "mitre": mitre_similarity(kind, observed),
        })
    total = len(events)
    detected_count = sum(item["detected_correctly"] for item in events)
    reasons: dict[str, int] = {}
    for item in events:
        if item["observed_reason_code"]:
            code = item["observed_reason_code"]
            reasons[code] = reasons.get(code, 0) + 1
    return {
        "total": total, "detected": detected_count,
        "rejected": sum(item["outcome"] == "REJECTED" for item in events),
        "accepted": sum(item["outcome"] == "ACCEPTED" for item in events),
        "detection_rate_percent": round(detected_count * 100 / total, 1) if total else None,
        "rejection_reasons": reasons, "events": events,
        "scope_note": "Faiz yalnız bu sessiyada nəticəsi saxlanmış virtual test paketlərinə aiddir; real hücumlara qarşı ölçü deyil.",
    }

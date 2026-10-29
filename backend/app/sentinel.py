"""Versioned, explainable teaching rules applied only after packet validation."""

from dataclasses import dataclass

from app.models import TelemetrySample
from app.simulator import SimulatorSnapshot


RULESET_VERSION = "sentinel-teaching-v1"
MAX_PAST_SECONDS = 10
MAX_FUTURE_SECONDS = 5


@dataclass(frozen=True)
class Attribution:
    verdict: str
    severity: str
    explanation: str
    cross_sensor_status: str
    digital_twin_status: str
    evidence: dict


def attribute(snapshot: SimulatorSnapshot, previous: TelemetrySample | None) -> Attribution:
    """Compare independent temperature channels and load; never infer an attack."""
    s = snapshot.sensors
    peer_temperature = round((s.temperature_2_c + s.temperature_3_c) / 2, 2)
    difference = round(s.temperature_1_c - peer_temperature, 2)
    previous_peer = ((previous.temperature_2_c + previous.temperature_3_c) / 2) if previous else None
    twin_expected = round(
        (previous_peer if previous_peer is not None else peer_temperature)
        + max(-0.4, min(0.4, (s.cpu_load_percent - 28) * 0.012 + (s.current_a - 1.9) * 0.5)), 2,
    )
    evidence = {
        "temp_1_c": s.temperature_1_c, "temp_2_c": s.temperature_2_c,
        "temp_3_c": s.temperature_3_c, "current_a": s.current_a,
        "cpu_load_percent": s.cpu_load_percent, "virtual_load_percent": s.cpu_load_percent,
        "power_w": round(s.voltage_v * s.current_a, 2),
        "twin_expected_temperature_c": twin_expected,
        "sensor_difference_c": difference,
        "previous_peer_temperature_c": round(previous_peer, 2) if previous_peer is not None else None,
        "twin_method": "previous peer temperature plus bounded CPU/current response",
    }
    if previous is None or snapshot.simulation_elapsed_seconds < 3:
        return Attribution("INSUFFICIENT EVIDENCE", "INFO", "Əvvəlki qəbul edilmiş ölçmə pəncərəsi hələ kifayət etmir.",
                           "NOT_EVALUATED", "NOT_EVALUATED", evidence)
    peers_agree = abs(s.temperature_2_c - s.temperature_3_c) <= 2.0
    load_normal = s.cpu_load_percent < 36 and s.current_a < 2.1
    if difference >= 5 and peers_agree and load_normal and abs(peer_temperature - twin_expected) <= 2:
        return Attribution(
            "PROBABLE SENSOR FAULT", "WARNING",
            "Temperatur sensoru 1 digər iki sensor və Rəqəmsal Modelin gözlənilən göstəricisi ilə uyğun gəlmir. Ehtimal edilən sensor nasazlığı müəyyən edilib.",
            "DIVERGENT", "PEERS_NORMAL", evidence,
        )
    coherent_heat = (
        min(s.temperature_1_c, s.temperature_2_c, s.temperature_3_c) >= 23.5
        and s.cpu_load_percent >= 36 and s.current_a >= 2.05
        and s.temperature_1_c > previous.temperature_1_c
        and s.temperature_2_c > previous.temperature_2_c
        and s.temperature_3_c > previous.temperature_3_c
        and max(s.temperature_1_c, s.temperature_2_c, s.temperature_3_c)
        - min(s.temperature_1_c, s.temperature_2_c, s.temperature_3_c) <= 3
    )
    if coherent_heat:
        return Attribution(
            "PROBABLE SYSTEM ANOMALY", "CRITICAL",
            "Üç temperatur sensorunda əlaqəli yüksəliş, artan elektrik cərəyanı və virtual yüklə birlikdə müşahidə edilib. Bu göstəricilər sistem səviyyəli istilik anomaliyasına uyğundur.",
            "COHERENT_RISE", "HEAT_CONFIRMED", evidence,
        )
    return Attribution("NORMAL TELEMETRY", "INFO", "Qəbul edilmiş ölçmələrdə Sentinel nasazlıq nümunəsi tapmadı.",
                       "CONSISTENT", "CONSISTENT", evidence)

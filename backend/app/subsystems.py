"""Versioned teaching thresholds for a final accepted telemetry sample."""

from app.models import TelemetrySample


RULES_VERSION = "teaching-health-v1"


def final_subsystems(sample: TelemetrySample | None, active_alert_codes: set[str], trust_verdict: str | None = None) -> dict[str, str]:
    if sample is None:
        return {key: "UNKNOWN" for key in ("energy", "thermal", "communications", "computer")}

    def level(warning: bool, critical: bool) -> str:
        return "CRITICAL" if critical else "WARNING" if warning else "NORMAL"

    sensor_fault = trust_verdict == "PROBABLE SENSOR FAULT"
    temperatures = (sample.temperature_2_c, sample.temperature_3_c) if sensor_fault else (
        sample.temperature_1_c, sample.temperature_2_c, sample.temperature_3_c)
    max_temperature = max(temperatures)

    return {
        "energy": level(sample.battery_level_percent < 20 or sample.voltage_v < 25,
                        sample.battery_level_percent < 10 or sample.voltage_v < 23),
        "thermal": level(max_temperature >= 24.5 or (not sensor_fault and "TEMP_1_HIGH" in active_alert_codes),
                         max_temperature >= 30),
        "communications": level(sample.signal_strength_percent < 80 or sample.communication_latency_ms > 60
                                or sample.packet_loss_percent >= 0.5 or "PACKET_LOSS_HIGH" in active_alert_codes,
                                sample.signal_strength_percent < 60 or sample.communication_latency_ms > 100
                                or sample.packet_loss_percent >= 1),
        "computer": level(sample.cpu_load_percent > 40 or sample.memory_usage_percent > 80,
                          sample.cpu_load_percent > 70 or sample.memory_usage_percent > 90),
    }

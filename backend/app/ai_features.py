"""Observable, accepted-sensor features shared by training and live scoring."""

from collections.abc import Sequence
from statistics import mean, pstdev

from app.simulator import SensorReadings


WINDOW_SECONDS = 20
FEATURE_NAMES = (
    "temperature_1_mean", "temperature_1_rate", "temperature_1_spread",
    "temperature_2_rate", "temperature_3_rate", "temperature_sensor_gap_mean",
    "temperature_sensor_gap_change", "current_mean", "current_rate", "current_spread",
    "battery_drain_rate", "voltage_mean", "power_mean", "power_rate",
    "cpu_mean", "cpu_rate", "cpu_spread", "heat_load_difference",
    "signal_mean", "packet_loss_mean",
)

FEATURE_SENSORS: dict[str, list[str]] = {
    "temperature_1_mean": ["temperature_1_c"],
    "temperature_1_rate": ["temperature_1_c"],
    "temperature_1_spread": ["temperature_1_c"],
    "temperature_2_rate": ["temperature_2_c"],
    "temperature_3_rate": ["temperature_3_c"],
    "temperature_sensor_gap_mean": ["temperature_1_c", "temperature_2_c", "temperature_3_c"],
    "temperature_sensor_gap_change": ["temperature_1_c", "temperature_2_c", "temperature_3_c"],
    "current_mean": ["current_a"], "current_rate": ["current_a"],
    "current_spread": ["current_a"], "battery_drain_rate": ["battery_level_percent"],
    "voltage_mean": ["voltage_v"], "power_mean": ["voltage_v", "current_a"],
    "power_rate": ["voltage_v", "current_a"], "cpu_mean": ["cpu_load_percent"],
    "cpu_rate": ["cpu_load_percent"], "cpu_spread": ["cpu_load_percent"],
    "heat_load_difference": ["temperature_1_c", "cpu_load_percent", "current_a"],
    "signal_mean": ["signal_strength_percent"], "packet_loss_mean": ["packet_loss_percent"],
}

FEATURE_DESCRIPTIONS = {
    "temperature_1_mean": "Temperatur 1 səviyyəsi",
    "temperature_1_rate": "Temperatur 1 artım sürəti",
    "temperature_1_spread": "Temperatur 1 yayılması",
    "temperature_2_rate": "Temperatur 2 dəyişmə sürəti",
    "temperature_3_rate": "Temperatur 3 dəyişmə sürəti",
    "temperature_sensor_gap_mean": "Temperatur sensorları arasındakı fərq",
    "temperature_sensor_gap_change": "Temperatur sensorları fərqinin dəyişməsi",
    "current_mean": "Cərəyan səviyyəsi", "current_rate": "Cərəyan dəyişmə sürəti",
    "current_spread": "Cərəyan yayılması", "battery_drain_rate": "Batareya azalma sürəti",
    "voltage_mean": "Gərginlik səviyyəsi", "power_mean": "Enerji istifadəsi",
    "power_rate": "Enerji istifadəsinin dəyişməsi", "cpu_mean": "CPU yükü",
    "cpu_rate": "CPU dəyişmə sürəti", "cpu_spread": "CPU yayılması",
    "heat_load_difference": "CPU, cərəyan və istilik davranışı arasındakı fərq",
    "signal_mean": "Siqnal səviyyəsi", "packet_loss_mean": "Paket itkisi",
}


def extract_features(readings: Sequence[tuple[int, SensorReadings]]) -> dict[str, float] | None:
    """Return a window only for 20 consecutive accepted sequence numbers."""
    if len(readings) != WINDOW_SECONDS:
        return None
    sequences = [sequence for sequence, _ in readings]
    if any(current != previous + 1 for previous, current in zip(sequences, sequences[1:])):
        return None
    sensors = [sensor for _, sensor in readings]

    def values(key: str) -> list[float]:
        return [getattr(sensor, key) for sensor in sensors]

    def rate(items: list[float]) -> float:
        return (items[-1] - items[0]) / (WINDOW_SECONDS - 1)

    t1, t2, t3 = (values(f"temperature_{index}_c") for index in (1, 2, 3))
    current = values("current_a")
    cpu = values("cpu_load_percent")
    battery = values("battery_level_percent")
    voltage = values("voltage_v")
    power = [v * a for v, a in zip(voltage, current)]
    gaps = [max(a, b, c) - min(a, b, c) for a, b, c in zip(t1, t2, t3)]
    return {
        "temperature_1_mean": mean(t1), "temperature_1_rate": rate(t1),
        "temperature_1_spread": pstdev(t1), "temperature_2_rate": rate(t2),
        "temperature_3_rate": rate(t3), "temperature_sensor_gap_mean": mean(gaps),
        "temperature_sensor_gap_change": rate(gaps), "current_mean": mean(current),
        "current_rate": rate(current), "current_spread": pstdev(current),
        "battery_drain_rate": -rate(battery), "voltage_mean": mean(voltage),
        "power_mean": mean(power), "power_rate": rate(power), "cpu_mean": mean(cpu),
        "cpu_rate": rate(cpu), "cpu_spread": pstdev(cpu),
        "heat_load_difference": rate(t1) - rate(cpu) * 0.10 - rate(current) * 0.5,
        "signal_mean": mean(values("signal_strength_percent")),
        "packet_loss_mean": mean(values("packet_loss_percent")),
    }


def feature_vector(features: dict[str, float]) -> list[float]:
    return [features[name] for name in FEATURE_NAMES]

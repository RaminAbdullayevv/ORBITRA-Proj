import type { RuleAlert, SensorReadings, TelemetrySample } from './api'

export type HealthStatus = 'NORMAL' | 'WARNING' | 'CRITICAL' | 'UNKNOWN'
export type SubsystemKey = 'energy' | 'thermal' | 'communications' | 'computer'
export type Reading = { label: string; value: string }
export type SubsystemView = { key: SubsystemKey; name: string; status: HealthStatus; readings: Reading[]; alertIds: string[] }
export const RULES_VERSION = 'teaching-health-v1'

const level = (warning: boolean, critical: boolean): HealthStatus => critical ? 'CRITICAL' : warning ? 'WARNING' : 'NORMAL'

export function assessSubsystems(sample: TelemetrySample | null, alerts: RuleAlert[], trusted: boolean, trustVerdict?: string): SubsystemView[] {
  const s: SensorReadings | null = sample?.sensors ?? null
  const active = alerts.filter(item => item.status === 'ACTIVE')
  const linked = (metric: string) => active.filter(item => item.metric_key === metric).map(item => item.alert_id)
  const fmt = (value: number | undefined, digits: number, unit: string) => value === undefined ? '—' : `${value.toFixed(digits)} ${unit}`
  const status = (warning: boolean, critical: boolean): HealthStatus => s && trusted ? level(warning, critical) : 'UNKNOWN'
  const sensorFault = trustVerdict === 'PROBABLE SENSOR FAULT'
  const maxTemp = s ? Math.max(...(sensorFault ? [s.temperature_2_c, s.temperature_3_c] : [s.temperature_1_c, s.temperature_2_c, s.temperature_3_c])) : 0
  return [
    { key: 'energy', name: 'Enerji bloku', status: status(!!s && (s.battery_level_percent < 20 || s.voltage_v < 25), !!s && (s.battery_level_percent < 10 || s.voltage_v < 23)),
      readings: [{ label: 'Batareya', value: fmt(s?.battery_level_percent, 1, '%') }, { label: 'Gərginlik', value: fmt(s?.voltage_v, 2, 'V') }, { label: 'Cərəyan', value: fmt(s?.current_a, 2, 'A') }], alertIds: [] },
    { key: 'thermal', name: 'İstilik sistemi', status: status(maxTemp >= 24.5 || (!sensorFault && linked('temperature_1_c').length > 0), maxTemp >= 30),
      readings: [{ label: 'Temperatur 1', value: fmt(s?.temperature_1_c, 2, '°C') }, { label: 'Temperatur 2', value: fmt(s?.temperature_2_c, 2, '°C') }, { label: 'Temperatur 3', value: fmt(s?.temperature_3_c, 2, '°C') }], alertIds: linked('temperature_1_c') },
    { key: 'communications', name: 'Telemetriya və rabitə', status: status(!!s && (s.signal_strength_percent < 80 || s.communication_latency_ms > 60 || s.packet_loss_percent >= .5 || linked('packet_loss_percent').length > 0), !!s && (s.signal_strength_percent < 60 || s.communication_latency_ms > 100 || s.packet_loss_percent >= 1)),
      readings: [{ label: 'Siqnal', value: fmt(s?.signal_strength_percent, 1, '%') }, { label: 'Gecikmə', value: fmt(s?.communication_latency_ms, 1, 'ms') }, { label: 'Paket itkisi', value: fmt(s?.packet_loss_percent, 2, '%') }], alertIds: linked('packet_loss_percent') },
    { key: 'computer', name: 'Bort kompüteri', status: status(!!s && (s.cpu_load_percent > 40 || s.memory_usage_percent > 80), !!s && (s.cpu_load_percent > 70 || s.memory_usage_percent > 90)),
      readings: [{ label: 'CPU', value: fmt(s?.cpu_load_percent, 1, '%') }, { label: 'Yaddaş', value: fmt(s?.memory_usage_percent, 1, '%') }], alertIds: [] },
  ]
}

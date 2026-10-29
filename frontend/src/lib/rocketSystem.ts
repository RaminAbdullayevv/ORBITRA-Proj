import type { TelemetrySample } from './api'
import type { HealthStatus, SubsystemView } from './subsystems'

export type RocketBlock = { id: string; name: string; status: HealthStatus; reading: string; note: string }

export function rocketBlocks(sample: TelemetrySample | null, health: SubsystemView[], trusted: boolean, verdict?: string): RocketBlock[] {
  const s = trusted ? sample?.sensors : null
  const status = (key: string): HealthStatus => trusted ? health.find(item => item.key === key)?.status ?? 'UNKNOWN' : 'UNKNOWN'
  const sensorFault = verdict === 'PROBABLE SENSOR FAULT'
  return [
    { id: 'sensors', name: 'Sensor bloku', status: s ? sensorFault ? 'WARNING' : 'NORMAL' : 'UNKNOWN',
      reading: s ? `T1 ${s.temperature_1_c.toFixed(1)} °C` : 'Etibarlı məlumat yoxdur', note: sensorFault ? 'Temperatur sensoru 1 ayrılıqda yoxlanmalıdır' : 'Üç temperatur kanalı' },
    { id: 'computer', name: 'Bort kompüteri', status: status('computer'),
      reading: s ? `CPU ${s.cpu_load_percent.toFixed(1)} %` : 'Etibarlı məlumat yoxdur', note: 'CPU və yaddaş' },
    { id: 'telemetry', name: 'Telemetriya və rabitə', status: status('communications'),
      reading: s ? `Siqnal ${s.signal_strength_percent.toFixed(1)} %` : 'Etibarlı məlumat yoxdur', note: 'Qəbul edilmiş paket axını' },
    { id: 'power', name: 'Enerji bloku', status: status('energy'),
      reading: s ? `Batareya ${s.battery_level_percent.toFixed(1)} %` : 'Etibarlı məlumat yoxdur', note: 'Batareya və gərginlik' },
    { id: 'thermal', name: 'İstilik monitorinqi', status: status('thermal'),
      reading: s ? `T2 ${s.temperature_2_c.toFixed(1)} °C · T3 ${s.temperature_3_c.toFixed(1)} °C` : 'Etibarlı məlumat yoxdur', note: 'Qəbul edilmiş temperatur ölçmələri' },
    { id: 'payload', name: 'Virtual faydalı yük', status: status('computer'),
      reading: s ? `Virtual yük ${s.cpu_load_percent.toFixed(1)} %` : 'Etibarlı məlumat yoxdur', note: 'CPU yükü əsasında tədris göstəricisi' },
  ]
}

import type { DeviceAction, DeviceStatus, ScenarioName } from './api'

export const projectName = 'ORBITRA — Raket Sistemləri üçün Ağıllı Telemetriya və Virtual Sınaq Platforması'
export const projectTagline = 'Raket sistemlərini fiziki risk olmadan sına, izlə və qoru.'
export const projectDescription = 'ORBITRA raketin bort elektronikasını, sensorlarını, enerji, istilik və telemetriya sistemlərini virtual mühitdə simulyasiya edən ağıllı sınaq platformasıdır. Sistem canlı telemetriyanı izləyir, nasazlıqları aşkarlayır, məlumat bütövlüyünü yoxlayır və avtomatik sınaq hesabatı hazırlayır.'

export const scenarioNames: Record<ScenarioName, string> = {
  NORMAL_MISSION: 'Normal raket sistemi sınağı',
  TEMPERATURE_ANOMALY: 'Bort sistemində temperatur anomaliyası',
  INVALID_TELEMETRY: 'Etibarsız telemetriya paketi',
  SINGLE_SENSOR_FAULT: 'Temperatur sensorunda nasazlıq',
  INVALID_SIGNATURE: 'Yanlış imzalı telemetriya paketi',
  REPLAYED_TELEMETRY: 'Təkrar göndərilmiş telemetriya paketi',
  SPOOFED_TELEMETRY: 'Saxta telemetriya mənbəyi testi',
}
export const scenarioName = (value: ScenarioName | string | null | undefined) => value ? scenarioNames[value as ScenarioName] ?? value : 'Ssenari yoxdur'

export const actionNames: Record<DeviceAction, string> = {
  start: 'Başlat', pause: 'Dayandır', resume: 'Davam etdir', reset: 'Sıfırla',
  end: 'Missiyanı bitir', reduce_processing_load: 'Virtual yükü azalt',
}
export const deviceStatusNames: Record<DeviceStatus, string> = {
  IDLE: 'Başlanmayıb', RUNNING: 'İşləyir', PAUSED: 'Dayandırılıb', ENDED: 'Bitirilib',
}
export const stateName = (value: string | null | undefined): string => ({
  NORMAL: 'Normal', WARNING: 'Xəbərdarlıq', CRITICAL: 'Kritik', UNKNOWN: 'Etibarlı məlumat yoxdur',
  ONLINE: 'Aktiv', DEGRADED: 'Diqqət tələb edir', 'NO DATA': 'Məlumat yoxdur',
  'NO TRUSTED DATA': 'Etibarlı məlumat yoxdur', 'TRUSTED HISTORICAL': 'Etibarlı tarixi məlumat',
  OPEN: 'Açıq', CLOSED: 'Bağlanıb', ACTIVE: 'Aktiv', RESOLVED: 'Bərpa olunub',
  SUCCESS: 'Uğurlu', FAILED: 'Uğursuz', DENIED: 'İcazə verilməyib', REJECTED: 'Rədd edilib', RESET: 'Sıfırlanıb', INTERRUPTED: 'Yarımçıq qalıb',
  EVALUATED: 'Qiymətləndirilib', NOT_VERIFIABLE: 'Təsdiqlənmir',
  STANDBY: 'Gözləmə', NOMINAL: 'Normal', HOLD: 'Saxlama',
  IDLE: 'Başlanmayıb', RUNNING: 'İşləyir', PAUSED: 'Dayandırılıb', ENDED: 'Bitirilib',
}[value ?? ''] ?? value ?? 'Məlumat yoxdur')

const verdictNames: Record<string, string> = {
  'NORMAL TELEMETRY': 'Etibarlı telemetriya',
  'PROBABLE SYSTEM ANOMALY': 'Ehtimal edilən sistem anomaliyası',
  'PROBABLE SENSOR FAULT': 'Ehtimal edilən sensor nasazlığı',
  'INTEGRITY INCIDENT': 'Məlumat bütövlüyü hadisəsi',
  'REPLAY INCIDENT': 'Təkrar paket hadisəsi',
  'STALE DATA': 'Köhnəlmiş məlumat',
  'UNKNOWN SOURCE': 'Naməlum mənbə',
  'INSUFFICIENT EVIDENCE': 'Kifayət qədər sübut yoxdur',
}
export const verdictName = (value: string | null | undefined) => value ? verdictNames[value] ?? value : 'Qərar gözlənilir'

export const severityName = (value: string) => ({ INFO: 'Məlumat', WARNING: 'Xəbərdarlıq', CRITICAL: 'Kritik' }[value] ?? value)
export const sensorName = (key: string) => ({
  battery_level_percent: 'Batareya səviyyəsi', voltage_v: 'Gərginlik', current_a: 'Elektrik cərəyanı',
  temperature_1_c: 'Temperatur sensoru 1', temperature_2_c: 'Temperatur sensoru 2', temperature_3_c: 'Temperatur sensoru 3',
  cpu_load_percent: 'CPU yükü', memory_usage_percent: 'Yaddaş istifadəsi',
  signal_strength_percent: 'Siqnal gücü', communication_latency_ms: 'Gecikmə', packet_loss_percent: 'Paket itkisi',
}[key] ?? key)
export const rejectionName = (value: string) => ({
  SCHEMA_REJECTED: 'Format rədd edilib', SOURCE_REJECTED: 'Naməlum mənbə',
  INTEGRITY_REJECTED: 'İmza rədd edilib', REPLAY_REJECTED: 'Təkrar paket rədd edilib',
  STALE_REJECTED: 'Köhnəlmiş vaxt rədd edilib', REPORT_READY: 'Hesabat hazırdır',
}[value] ?? value)
export const auditActionName = (value: string) => ({
  LOGIN: 'Giriş', LOGOUT: 'Çıxış', CSRF_CHECK: 'Sorğu qoruması',
  TELEMETRY_REJECTION: 'Telemetriya rəddi', INCIDENT_NOTE: 'İnsidentə qeyd',
  INCIDENT_CLOSE: 'İnsidentin bağlanması', REPORT_GENERATE: 'Hesabat yaradılması',
  START: 'Başlat', PAUSE: 'Dayandır', RESUME: 'Davam etdir', RESET: 'Sıfırla',
  END: 'Missiyanı bitir', REDUCE_PROCESSING_LOAD: 'Virtual yükü azalt',
}[value] ?? value)

// Old stored Sentinel explanations keep their audit text; only the displayed label changes.
export const displayModelTerm = (value: string): string => value
  .split('Rəqəmsal Əkizin').join('Rəqəmsal Modelin')
  .split('Rəqəmsal Əkizə').join('Rəqəmsal Modelə')
  .split('Rəqəmsal Əkizdə').join('Rəqəmsal Modeldə')
  .split('Rəqəmsal Əkiz').join('Rəqəmsal Model')
  .split('RƏQƏMSAL ƏKİZ').join('RƏQƏMSAL MODEL')

import type { HealthStatus } from './subsystems'

export type ReadinessLevel = 'HAZIR' | 'DİQQƏT' | 'HAZIR DEYİL' | 'MƏLUMAT YOXDUR'
export type ReadinessInput = {
  missionStarted: boolean; hasTrustedSample: boolean; connectionLost: boolean; paused: boolean
  health: HealthStatus[]; activeCriticalAlert: boolean; integrityIncident: boolean
  quarantinedCritical: boolean; sentinelDegraded: boolean
}
export type ReadinessResult = { level: ReadinessLevel; reason: string }

/** A teaching indicator derived only from committed telemetry and backend incidents. */
export function assessReadiness(input: ReadinessInput): ReadinessResult {
  if (!input.missionStarted) return { level: 'MƏLUMAT YOXDUR', reason: 'Aktiv sınaq yoxdur.' }
  if (!input.hasTrustedSample) return { level: 'MƏLUMAT YOXDUR', reason: 'Etibarlı telemetriya hələ qəbul edilməyib.' }
  if (input.connectionLost) return { level: 'HAZIR DEYİL', reason: 'Etibarlı telemetriya qəbul edilmir.' }
  if (input.integrityIncident || input.quarantinedCritical) return { level: 'HAZIR DEYİL', reason: 'Kritik telemetriya bütövlüyü hadisəsi aşkarlanıb.' }
  if (input.activeCriticalAlert || input.health.includes('CRITICAL')) return { level: 'HAZIR DEYİL', reason: 'Əsas virtual sistemlərdən birində kritik vəziyyət var.' }
  if (input.health.includes('UNKNOWN')) return { level: 'HAZIR DEYİL', reason: 'Əsas sistemlərdən etibarlı vəziyyət alınmır.' }
  if (input.paused) return { level: 'DİQQƏT', reason: 'Virtual sınaq dayandırılıb; yeni telemetriya gözlənilir.' }
  if (input.health.includes('WARNING') || input.sentinelDegraded) return { level: 'DİQQƏT', reason: 'Xəbərdarlıq və ya Sentinel etibarlılıq qeydi mövcuddur.' }
  return { level: 'HAZIR', reason: 'Bütün əsas virtual sistemlər normaldır.' }
}

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')
let csrfToken: string | null = null

export function setCsrfToken(value: string | null): void { csrfToken = value }
function expired(): void { window.dispatchEvent(new Event('orbitra-auth-expired')) }

export type Role = 'ADMIN' | 'VIRTUAL' | 'OPERATOR' | 'SECURITY_ANALYST' | 'OBSERVER'
export type Identity = { user_id: number; username: string; role: Role; expires_at: string; csrf_token: string }

export async function getIdentity(): Promise<Identity> {
  const response = await fetch(`${apiBaseUrl}/api/v1/auth/me`, { credentials: 'include', cache: 'no-store' })
  if (!response.ok) throw new ApiRequestError('Sessiya oxunmadı.', response.status)
  return await response.json() as Identity
}

export async function login(username: string, password: string): Promise<Identity> {
  const response = await fetch(`${apiBaseUrl}/api/v1/auth/login`, {
    method: 'POST', credentials: 'include', cache: 'no-store',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username, password }),
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new ApiRequestError(typeof body?.detail === 'string' ? body.detail : 'Giriş baş tutmadı.', response.status)
  }
  return await response.json() as Identity
}

export async function logout(): Promise<void> {
  const response = await fetch(`${apiBaseUrl}/api/v1/auth/logout`, {
    method: 'POST', credentials: 'include', cache: 'no-store',
    headers: { 'X-CSRF-Token': csrfToken ?? '' },
  })
  if (!response.ok) throw new ApiRequestError('Çıxış baş tutmadı.', response.status)
}

export type HealthResponse = {
  status: string
  database: string
}

export async function checkBackend(): Promise<boolean> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), 4000)
  try {
    const response = await fetch(`${apiBaseUrl}/api/v1/health`, {
      signal: controller.signal,
      cache: 'no-store',
    })
    if (!response.ok) return false
    const health: HealthResponse = await response.json()
    return health.status === 'ok' && health.database === 'connected'
  } finally {
    window.clearTimeout(timeout)
  }
}

export type DeviceStatus = 'IDLE' | 'RUNNING' | 'PAUSED' | 'ENDED'
export type ScenarioName = 'NORMAL_MISSION' | 'TEMPERATURE_ANOMALY' | 'INVALID_TELEMETRY' | 'SINGLE_SENSOR_FAULT' | 'INVALID_SIGNATURE' | 'REPLAYED_TELEMETRY' | 'SPOOFED_TELEMETRY'
export type SubsystemStatus = 'STANDBY' | 'NOMINAL' | 'PAUSED'
export type DeviceAction = 'start' | 'pause' | 'resume' | 'reset' | 'end' | 'reduce_processing_load'

export type SensorReadings = {
  battery_level_percent: number
  voltage_v: number
  current_a: number
  temperature_1_c: number
  temperature_2_c: number
  temperature_3_c: number
  cpu_load_percent: number
  memory_usage_percent: number
  signal_strength_percent: number
  communication_latency_ms: number
  packet_loss_percent: number
}

export type VirtualDeviceSnapshot = {
  schema_version: string
  run_id: string | null
  scenario: ScenarioName | null
  status: DeviceStatus
  simulation_elapsed_seconds: number
  system_mode: 'STANDBY' | 'NOMINAL' | 'HOLD'
  subsystem_statuses: {
    power: SubsystemStatus
    thermal: SubsystemStatus
    communications: SubsystemStatus
    computer: SubsystemStatus
  }
  sensors: SensorReadings
  updated_at: string
}

export class ApiRequestError extends Error {
  constructor(message: string, readonly status: number) {
    super(message)
  }
}

async function requestDevice(path: string, method: 'GET' | 'POST', scenario?: ScenarioName): Promise<VirtualDeviceSnapshot> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), 4000)
  try {
    const response = await fetch(`${apiBaseUrl}/api/v1/virtual-device${path}`, {
      method,
      headers: method === 'POST' ? { ...(scenario ? { 'Content-Type': 'application/json' } : {}), 'X-CSRF-Token': csrfToken ?? '' } : undefined,
      body: scenario ? JSON.stringify({ scenario }) : undefined,
      signal: controller.signal,
      cache: 'no-store',
      credentials: 'include',
    })
    if (!response.ok) {
      if (response.status === 401) expired()
      const body = await response.json().catch(() => null)
      const message = typeof body?.detail?.message === 'string'
        ? body.detail.message
        : `Sorğu yerinə yetirilmədi (HTTP ${response.status}).`
      throw new ApiRequestError(message, response.status)
    }
    return await response.json() as VirtualDeviceSnapshot
  } finally {
    window.clearTimeout(timeout)
  }
}

export function getVirtualDevice(): Promise<VirtualDeviceSnapshot> {
  return requestDevice('', 'GET')
}

export function performVirtualDeviceAction(action: DeviceAction, scenario?: ScenarioName): Promise<VirtualDeviceSnapshot> {
  return requestDevice(`/${action === 'reduce_processing_load' ? 'reduce-processing-load' : action}`, 'POST', action === 'start' ? scenario : undefined)
}

export type TelemetrySample = {
  run_id: string
  sequence_number: number
  simulation_elapsed_seconds: number
  sample_time: string
  status: DeviceStatus
  sensors: SensorReadings
}

export type RunSummary = {
  run_id: string
  scenario: ScenarioName
  started_at: string
  last_status: string
  ended_at: string | null
}

export type TelemetryState = {
  device: VirtualDeviceSnapshot | null
  device_last_seen_at?: string | null
  run: RunSummary | null
  latest_sample: TelemetrySample | null
  active_alerts: RuleAlert[]
  rule_alerts: RuleAlert[]
  rejections: RejectedTelemetry[]
  ai_status: AIStatus
  ai_events: AIEvent[]
  trust: TrustOverview
}

export type TrustDecision = {
  id: number; packet_id: string; mission_id: string; device_id: string; sequence_number: number
  received_at: string; schema_valid: boolean; source_valid: boolean | null
  signature_valid: boolean | null; replay_detected: boolean | null; freshness_valid: boolean | null
  cross_sensor_status: string; digital_twin_status: string; final_verdict: string; severity: string
  explanation: string; evidence: Record<string, string | number | boolean | null>
  ruleset_version: string; model_version: string | null; processing_time_ms: number
  accepted: boolean; incident_id: string | null
}
export type TrustStats = { accepted: number; quarantined: number; system_anomaly: number; sensor_fault: number
  integrity_incident: number; replay_incident: number; stale_data: number }
export type TrustOverview = { status: 'ONLINE' | 'DEGRADED' | 'NO DATA'; latest: TrustDecision | null
  latest_accepted: TrustDecision | null; stats: TrustStats; quarantine: RejectedTelemetry[]; last_successful_at: string | null
  active_integrity_count: number; active_integrity_assessment_id: number | null; untrusted_blocks: string[] }
export type TrustHistory = { decisions: TrustDecision[]; has_more: boolean }

export type AIStatus = {
  model_status: 'PREPARING' | 'READY' | 'NOT_TRAINED' | 'ERROR'
  model_version: string | null
  message: string
  window_seconds: number
  accepted_window_count: number
  latest_score: number | null
  threshold: number | null
  latest_sequence_number: number | null
  last_evaluated_at: string | null
}

export type BaselineDifference = {
  description: string
  observed: number
  normal_mean: number
  normal_std: number
  standardized_difference: number
}

export type AIEvent = {
  event_id: string
  run_id: string
  model_version: string
  started_at: string
  updated_at: string
  ended_at: string | null
  start_sequence_number: number
  latest_sequence_number: number
  window_start_sequence_number: number
  score: number
  affected_sensors: string[]
  baseline_comparison: Record<string, BaselineDifference>
  explanation: string
  status: 'ACTIVE' | 'RESOLVED' | 'ENDED'
}

export type RuleAlert = {
  alert_id: string
  run_id: string
  opened_at: string
  closed_at: string | null
  reason: string
  metric_key: string
  metric_value: number
  resolved_value: number | null
  status: string
}

export type RejectedTelemetry = {
  rejection_id: string
  run_id: string
  sequence_number: number
  rejected_at: string
  schema_version: string
  reason: string
  reason_code: 'SCHEMA_REJECTED' | 'INTEGRITY_REJECTED' | 'SOURCE_REJECTED' | 'REPLAY_REJECTED' | 'STALE_REJECTED' | 'RUN_REJECTED' | 'STATE_REJECTED'
  source_id: string
  packet_id: string | null
  signature_status: string | null
  packet_timestamp: string | null
  incident_id: string | null
}

export type TelemetryHistory = {
  run_id: string
  samples: TelemetrySample[]
  has_more: boolean
}

export type OperatorEvent = {
  event_number: number
  event_id: string
  run_id: string | null
  action: DeviceAction
  received_at: string
  simulation_elapsed_seconds: number
  before_status: DeviceStatus
  after_status: DeviceStatus
  outcome: 'SUCCESS' | 'REJECTED'
  reason: string
  source: string
  user_id: number | null
}

export type OperatorEventHistory = {
  run_id: string
  events: OperatorEvent[]
  has_more: boolean
}

export type TelemetryEvent =
  | ({ type: 'telemetry_sample' } & TelemetrySample)
  | { type: 'simulation_status'; device: VirtualDeviceSnapshot; device_last_seen_at?: string | null; run: RunSummary | null; latest_sample: TelemetrySample | null; rule_alerts: RuleAlert[]; rejections: RejectedTelemetry[]; ai_status: AIStatus; ai_events: AIEvent[]; trust: TrustOverview }
  | { type: 'heartbeat'; sent_at: string; run_id: string | null; status: DeviceStatus; device_last_seen_at?: string | null }
  | ({ type: 'operator_event' } & OperatorEvent)
  | ({ type: 'rule_alert' } & RuleAlert)
  | ({ type: 'telemetry_rejected' } & RejectedTelemetry)
  | { type: 'ai_assessment'; run_id: string; ai_status: AIStatus }
  | ({ type: 'ai_event' } & AIEvent)
  | { type: 'trust_assessment'; run_id: string; trust: TrustOverview }

async function requestTelemetry<T>(path: string): Promise<T> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), 4000)
  try {
    const response = await fetch(`${apiBaseUrl}/api/v1/telemetry${path}`, {
      signal: controller.signal,
      cache: 'no-store',
      credentials: 'include',
    })
    if (response.status === 401) expired()
    if (!response.ok) throw new ApiRequestError(`Telemetriya sorğusu uğursuz oldu (HTTP ${response.status}).`, response.status)
    return await response.json() as T
  } finally {
    window.clearTimeout(timeout)
  }
}

export function getTelemetryState(runId?: string): Promise<TelemetryState> {
  const query = runId ? `?run_id=${encodeURIComponent(runId)}` : ''
  return requestTelemetry<TelemetryState>(`/state${query}`)
}

export function getTelemetryHistory(runId: string, afterSequence?: number): Promise<TelemetryHistory> {
  const query = afterSequence === undefined ? '?limit=300' : `?after_sequence=${afterSequence}&limit=600`
  return requestTelemetry<TelemetryHistory>(`/runs/${encodeURIComponent(runId)}/samples${query}`)
}

export function getOperatorEvents(runId: string, afterId = 0): Promise<OperatorEventHistory> {
  return requestTelemetry<OperatorEventHistory>(`/runs/${encodeURIComponent(runId)}/events?after_id=${afterId}&limit=600`)
}

export function telemetrySocketUrl(): string {
  const origin = new URL(apiBaseUrl || window.location.origin, window.location.origin)
  origin.protocol = origin.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${origin.origin}${origin.pathname.replace(/\/$/, '')}/api/v1/telemetry/ws`
}

export async function getTrustDecisions(runId: string, beforeId?: number): Promise<TrustHistory> {
  const query = beforeId ? `?before_id=${beforeId}&limit=30` : '?limit=30'
  const response = await fetch(`${apiBaseUrl}/api/v1/sentinel/runs/${encodeURIComponent(runId)}/decisions${query}`,
    { credentials: 'include', cache: 'no-store' })
  if (response.status === 401) expired()
  if (!response.ok) throw new ApiRequestError(`Sentinel qərarları alınmadı (HTTP ${response.status}).`, response.status)
  return await response.json() as TrustHistory
}

export async function getTrustDecision(runId: string, assessmentId: number): Promise<TrustDecision> {
  const response = await fetch(`${apiBaseUrl}/api/v1/sentinel/runs/${encodeURIComponent(runId)}/decisions/${assessmentId}`,
    { credentials: 'include', cache: 'no-store' })
  if (response.status === 401) expired()
  if (!response.ok) throw new ApiRequestError(`Sentinel qərarı alınmadı (HTTP ${response.status}).`, response.status)
  return await response.json() as TrustDecision
}

export type AuditEvent = {
  id: number; occurred_at: string; user_id: number | null; username: string | null
  action: string; outcome: string; reason_code: string; run_id: string | null
  incident_id: string | null; sequence_number: number | null
}
export type IncidentNote = { id: number; body: string; created_at: string; author_user_id: number; author_username: string | null }
export type SecurityIncident = {
  incident_id: string; created_at: string; kind: string; status: 'OPEN' | 'CLOSED'
  reason_code: string; summary: string; run_id: string | null; source_id: string | null
  sequence_number: number | null; closed_at: string | null; closed_by_user_id: number | null
  closed_by_username: string | null; close_reason: string | null; notes: IncidentNote[]
  detail: { test_name: string | null; test_kind: string | null; observed_reason_code: string
    observed_reason: string; outcome: 'REJECTED' | 'REVIEW_REQUIRED'; affected_block: string
    packet_id: string | null; sent: { source_id: string | null; sequence_number: number | null
      sample_time: string | null; sensors: SensorReadings | null }
    checks: { schema_valid: boolean | null; source_valid: boolean | null
      signature_valid: boolean | null; replay_detected: boolean | null; freshness_valid: boolean | null }
    action: string; mitre: { code: string; name: string; url: string; qualification: string } | null } | null
}
export type SecurityOverview = { incidents: SecurityIncident[]; audit: AuditEvent[] }

async function securityRequest<T>(path: string, method: 'GET' | 'POST' = 'GET', body?: object): Promise<T> {
  const response = await fetch(`${apiBaseUrl}/api/v1/security${path}`, {
    method, credentials: 'include', cache: 'no-store',
    headers: method === 'POST' ? { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken ?? '' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (response.status === 401) expired()
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new ApiRequestError(typeof payload?.detail === 'string' ? payload.detail : `Sorğu yerinə yetirilmədi (HTTP ${response.status}).`, response.status)
  }
  return await response.json() as T
}

export function getSecurityOverview(): Promise<SecurityOverview> { return securityRequest('/overview') }
export function addIncidentNote(id: string, body: string): Promise<IncidentNote> {
  return securityRequest(`/incidents/${encodeURIComponent(id)}/notes`, 'POST', { body })
}
export function closeIncident(id: string, reason: string): Promise<{ status: string }> {
  return securityRequest(`/incidents/${encodeURIComponent(id)}/close`, 'POST', { reason })
}

export type ReportRun = { run_id: string; scenario: ScenarioName; started_at: string; ended_at: string | null; status: string }
export type MissionReport = {
  run_id: string; scenario: ScenarioName; status: string; preview: boolean; started_at: string; ended_at: string | null
  generated_at: string | null; rules_version: string; model_version: string | null; ai_analysis: 'EVALUATED' | 'NOT_VERIFIABLE'; last_ai_evaluated_at: string | null
  duration_seconds: number; accepted_count: number; rejected_count: number; rejection_reasons: string[]; sequence_gaps: number
  latest_sample: { sequence_number: number; sample_time: string; sensors: SensorReadings } | null
  subsystems: Record<'energy' | 'thermal' | 'communications' | 'computer', 'NORMAL' | 'WARNING' | 'CRITICAL' | 'UNKNOWN'>
  rule_alerts: { rule_code: string; reason: string; opened_at: string; closed_at: string | null; status: string; metric_key: string; metric_value: number }[]
  ai_events: { event_id: string; model_version: string; started_at: string; ended_at: string | null; status: string; score: number; explanation: string; start_sequence_number: number }[]
  security_incidents: { incident_id: string; created_at: string; reason_code: string; summary: string; sequence_number: number | null; status: string; close_reason: string | null }[]
  security_audit: { occurred_at: string; action: string; outcome: string; reason_code: string; sequence_number: number | null }[]
  operator_events: { event_number: number; action: string; received_at: string; outcome: string; reason: string; user_id: number | null; username: string | null; simulation_elapsed_seconds: number }[]
  quality_note: string; limitations: string[]
  cyber_security: { total: number; detected: number; rejected: number; accepted: number
    detection_rate_percent: number | null; rejection_reasons: Record<string, number>; scope_note: string
    events: { test_kind: string; test_name: string; packet_id: string; sequence_number: number
      created_at: string; expected_reason_code: string; observed_reason_code: string | null
      outcome: 'REJECTED' | 'ACCEPTED'; detected_correctly: boolean; affected_block: string
      operator_alert: string; mitre: { code: string; name: string; url: string; qualification: string } | null }[] }
  telemetry_trust: { accepted: number; rejected: number; quarantined: number; system_anomaly: number
    sensor_fault: number; integrity_incident: number; replay_incident: number; stale_data: number
    ruleset_version: string; model_version: string | null; final_status: string
    key_decisions: { id: number; packet_id: string; verdict: string; explanation: string
      evidence: Record<string, string | number | boolean | null> }[] }
}

async function reportRequest<T>(path: string, method: 'GET' | 'POST' = 'GET'): Promise<T> {
  const response = await fetch(`${apiBaseUrl}/api/v1/reports${path}`, {
    method, credentials: 'include', cache: 'no-store',
    headers: method === 'POST' ? { 'X-CSRF-Token': csrfToken ?? '' } : undefined,
  })
  if (!response.ok) {
    if (response.status === 401) expired()
    const body = await response.json().catch(() => null)
    throw new ApiRequestError(typeof body?.detail === 'string' ? body.detail : `Hesabat sorğusu alınmadı (HTTP ${response.status}).`, response.status)
  }
  return await response.json() as T
}

export function getReportRuns(): Promise<ReportRun[]> { return reportRequest('/runs') }
export function getMissionReport(runId: string): Promise<MissionReport> { return reportRequest(`/runs/${encodeURIComponent(runId)}`) }
export function generateMissionReport(runId: string): Promise<{ run_id: string; generated_at: string }> {
  return reportRequest(`/runs/${encodeURIComponent(runId)}/generate`, 'POST')
}

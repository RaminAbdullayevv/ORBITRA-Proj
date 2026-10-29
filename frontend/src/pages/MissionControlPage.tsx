import { Link } from 'react-router-dom'
import { Activity, AlertTriangle, Battery, CheckCircle2, Clock3, Cpu, Radio, ShieldCheck, Thermometer, type LucideIcon } from 'lucide-react'
import { type OperatorEvent, type RejectedTelemetry, type RuleAlert, type SensorReadings, type TelemetrySample } from '../lib/api'
import { useLiveTelemetry, type LiveState } from '../lib/useLiveTelemetry'
import { assessSubsystems, type SubsystemKey } from '../lib/subsystems'
import { actionNames, deviceStatusNames, scenarioName, sensorName, stateName, verdictName } from '../lib/labels'
import { assessReadiness } from '../lib/readiness'
import './mission-control.css'

type Series = { key: keyof SensorReadings; label: string; color: string }

const stateLabels: Record<LiveState, string> = {
  connecting: 'Qoşulur', live: 'Canlı bağlantı var', paused: 'Simulyasiya dayandırılıb',
  ended: 'Missiya bitirilib', disconnected: 'Bağlantı kəsilib', stale: 'Məlumat köhnəlib', no_data: 'Məlumat hələ yoxdur',
}

function formatElapsed(seconds: number): string {
  return `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`
}

function formatDuration(seconds: number): string {
  return `${String(Math.floor(seconds / 3600)).padStart(2, '0')}:${formatElapsed(seconds % 3600)}`
}

function EventRow({ event }: { event: OperatorEvent }) {
  const Icon = event.outcome === 'SUCCESS' ? CheckCircle2 : AlertTriangle
  return <li className={`mission-event event-${event.outcome.toLowerCase()}`} data-event-id={event.event_id}>
    <div className="event-symbol"><Icon size={16} aria-hidden="true" /></div>
    <div className="event-copy"><div className="event-title"><strong>{actionNames[event.action]}</strong><span>{event.outcome === 'SUCCESS' ? 'Uğurlu' : 'Rədd edildi'}</span></div>
      <p>{event.reason}</p><small title={event.run_id ?? undefined}>SESSİYA {event.run_id ?? '—'} · {stateName(event.before_status)} → {stateName(event.after_status)} · T+{formatDuration(event.simulation_elapsed_seconds)}</small></div>
    <time dateTime={event.received_at}>{new Date(event.received_at).toLocaleTimeString('az-AZ')}</time>
  </li>
}

type TimelineItem =
  | { kind: 'operator'; at: string; key: string; event: OperatorEvent }
  | { kind: 'alert_open'; at: string; key: string; alert: RuleAlert }
  | { kind: 'alert_resolved'; at: string; key: string; alert: RuleAlert }
  | { kind: 'rejected'; at: string; key: string; rejection: RejectedTelemetry }

const rejectionTitles: Record<RejectedTelemetry['reason_code'], string> = {
  SCHEMA_REJECTED: 'Telemetriya formatı qəbul edilmədi',
  SOURCE_REJECTED: 'Naməlum mənbə rədd edildi',
  INTEGRITY_REJECTED: 'Paket imzası rədd edildi',
  REPLAY_REJECTED: 'Təkrar paket rədd edildi',
  STALE_REJECTED: 'Paket vaxtı rədd edildi',
  RUN_REJECTED: 'Sessiya uyğun gəlmir',
  STATE_REJECTED: 'Cihaz vəziyyəti uyğun deyil',
}

function TimelineRow({ item }: { item: TimelineItem }) {
  if (item.kind === 'operator') return <EventRow event={item.event} />
  const alert = item.kind === 'alert_open' || item.kind === 'alert_resolved' ? item.alert : null
  const rejection = item.kind === 'rejected' ? item.rejection : null
  const title = item.kind === 'alert_open' ? 'Qayda xəbərdarlığı açıldı' : item.kind === 'alert_resolved'
    ? 'Qayda xəbərdarlığı bərpa olundu' : rejection ? rejectionTitles[rejection.reason_code] : ''
  const description = item.kind === 'alert_open' ? `${alert?.reason} Temperatur 1: ${alert?.metric_value.toFixed(2)} °C.`
    : item.kind === 'alert_resolved' ? `Temperatur 1: ${alert?.resolved_value?.toFixed(2)} °C; bərpa həddi 23.3 °C.`
      : `${item.rejection.reason} Nümunə #${item.rejection.sequence_number}.`
  const runId = alert?.run_id ?? (item.kind === 'rejected' ? item.rejection.run_id : '')
  return <li className={`mission-event ${item.kind === 'alert_open' || item.kind === 'rejected' ? 'event-rejected' : ''}`} data-event-id={item.key}>
    <div className="event-symbol"><AlertTriangle size={16} aria-hidden="true" /></div>
    <div className="event-copy"><div className="event-title"><strong>{title}</strong><span>{item.kind === 'rejected' ? 'SENTINEL' : 'QAYDA'}</span></div>
      <p>{description}</p><small title={runId}>Sessiya {runId} · {alert ? sensorName(alert.metric_key) : rejection ? rejectionTitles[rejection.reason_code] : ''}</small></div>
    <time dateTime={item.at}>{new Date(item.at).toLocaleTimeString('az-AZ')}</time>
  </li>
}

const healthIcons: Record<SubsystemKey, LucideIcon> = {
  energy: Battery, thermal: Thermometer, communications: Radio, computer: Cpu,
}

function Chart({ title, unit, samples, series }: { title: string; unit: string; samples: TelemetrySample[]; series: Series[] }) {
  const width = 700, height = 235, left = 53, right = 18, top = 20, bottom = 38
  const latest = samples[samples.length - 1]?.simulation_elapsed_seconds ?? 0
  const xMin = Math.max(0, latest - 300)
  const xMax = Math.max(30, latest)
  const values = samples.flatMap(sample => series.map(line => sample.sensors[line.key]))
  const rawMin = values.length ? Math.min(...values) : 0
  const rawMax = values.length ? Math.max(...values) : 1
  const padding = Math.max((rawMax - rawMin) * .15, unit === '%' ? 2 : unit === '°C' ? 1 : .2)
  const yMin = Math.max(0, rawMin - padding)
  const yMax = rawMax + padding
  const x = (elapsed: number) => left + ((elapsed - xMin) / (xMax - xMin)) * (width - left - right)
  const y = (value: number) => top + (1 - (value - yMin) / (yMax - yMin)) * (height - top - bottom)
  const ticks = [0, .5, 1].map(fraction => xMin + Math.round((xMax - xMin) * fraction))

  const pathFor = (line: Series) => samples.map((sample, index) => {
    const previous = samples[index - 1]
    const command = !previous || sample.sequence_number !== previous.sequence_number + 1 ? 'M' : 'L'
    return `${command}${x(sample.simulation_elapsed_seconds).toFixed(1)},${y(sample.sensors[line.key]).toFixed(1)}`
  }).join(' ')

  return <section className="telemetry-chart" aria-label={`${title} qrafiki`}>
    <div className="telemetry-chart-header"><h3>{title}</h3><span>{unit}</span></div>
    <div className="telemetry-chart-legend">
      {series.map(line => <span key={line.key}><i style={{ backgroundColor: line.color }} />{line.label}
        {samples.length > 0 && <b data-sensor={line.key}>{samples[samples.length - 1].sensors[line.key].toFixed(2)} {unit}</b>}
      </span>)}
    </div>
    {samples.length === 0 ? <div className="telemetry-chart-empty">Saxlanmış nümunə gözlənilir</div> :
      <svg viewBox={`0 0 ${width} ${height}`} className="telemetry-chart-svg" role="img" aria-label={`${title}: ${samples.length} saxlanmış nümunə, son beş dəqiqə`}>
        {[0, .5, 1].map(fraction => {
          const value = yMin + (yMax - yMin) * fraction
          const position = y(value)
          return <g key={fraction}>
            <line x1={left} y1={position} x2={width - right} y2={position} stroke="#354048" strokeDasharray="3 5" />
            <text x={left - 8} y={position + 4} textAnchor="end" className="telemetry-axis-label">{value.toFixed(unit === 'A' ? 1 : 0)}</text>
          </g>
        })}
        {ticks.map((tick, index) => <g key={index}>
          <line x1={x(tick)} y1={top} x2={x(tick)} y2={height - bottom} stroke="#2b353b" />
          <text x={x(tick)} y={height - 12} textAnchor="middle" className="telemetry-axis-label">{formatElapsed(tick)}</text>
        </g>)}
        {series.map(line => <g key={line.key}>
          {samples.length > 1 && <path d={pathFor(line)} fill="none" stroke={line.color} strokeWidth="2.2" strokeLinejoin="round" strokeLinecap="round" />}
          {samples.length === 1 && <circle cx={x(samples[0].simulation_elapsed_seconds)} cy={y(samples[0].sensors[line.key])} r="3.5" fill={line.color} />}
        </g>)}
        <text x={width - right} y={height - 12} textAnchor="end" className="telemetry-axis-title">SİMULYASİYA VAXTI</text>
      </svg>}
  </section>
}

export function MissionControlPage() {
  const { device, run, samples, events, alerts, rejections, aiStatus, aiEvents, trust, latestSample, state, sampleAgeSeconds } = useLiveTelemetry()
  const visibleSamples = device?.run_id ? samples.filter(sample => sample.run_id === device.run_id) : []
  const timeline: TimelineItem[] = [
    ...events.map(event => ({ kind: 'operator' as const, at: event.received_at, key: event.event_id, event })),
    ...alerts.flatMap(alert => [
      { kind: 'alert_open' as const, at: alert.opened_at, key: `${alert.alert_id}-open`, alert },
      ...(alert.closed_at ? [{ kind: 'alert_resolved' as const, at: alert.closed_at, key: `${alert.alert_id}-resolved`, alert }] : []),
    ]),
    ...rejections.map(rejection => ({ kind: 'rejected' as const, at: rejection.rejected_at, key: rejection.rejection_id, rejection })),
  ].sort((a, b) => Date.parse(b.at) - Date.parse(a.at))
  const recentEvents = timeline.slice(0, 5)
  const activeAlerts = alerts.filter(alert => alert.status === 'ACTIVE')
  const activeAIEvents = aiEvents.filter(event => event.status === 'ACTIVE')
  const hasTrustworthyData = state === 'live' || state === 'paused'
  const health = assessSubsystems(latestSample, activeAlerts, hasTrustworthyData, trust?.latest_accepted?.final_verdict)
  const readiness = assessReadiness({ missionStarted: device?.status === 'RUNNING' || device?.status === 'PAUSED', hasTrustedSample: !!latestSample,
    connectionLost: state === 'stale' || state === 'disconnected', paused: state === 'paused',
    health: health.map(item => item.status), activeCriticalAlert: activeAlerts.some(item =>
      item.metric_key === 'temperature_1_c' && item.metric_value >= 30 && trust?.latest_accepted?.final_verdict !== 'PROBABLE SENSOR FAULT' || item.metric_key === 'packet_loss_percent' && item.metric_value >= 1),
    integrityIncident: (trust?.active_integrity_count ?? 0) > 0, quarantinedCritical: (trust?.stats.integrity_incident ?? 0) > 0,
    sentinelDegraded: trust?.status === 'DEGRADED' })

  return <main id="main-content" className="main-content mission-page">
    <div className="page-crumb">ORBITRA <span>/</span> MİSSİYA İDARƏETMƏSİ</div>
    <div className="mission-heading">
      <div><p className="eyebrow">İŞ SAHƏSİ <span>01 / 07 · SENTINEL</span></p><h1>Missiya İdarəetmə</h1>
        <p className="page-description">Virtual raket sisteminin telemetriya və sınaq idarəetmə mərkəzi</p></div>
    </div>

    <div className={`mission-connection mission-${state}`} role={state === 'disconnected' || state === 'stale' ? 'alert' : 'status'}>
      <span className="mission-connection-dot" /><strong>{stateLabels[state]}</strong>
      {state === 'stale' && <span>Son nümunə {sampleAgeSeconds} saniyə əvvəl alınıb.</span>}
      {state === 'disconnected' && <span>Tarixi göstəricilər canlı deyil. Bağlantı avtomatik bərpa olunacaq.</span>}
      {state === 'paused' && <span>Yeni nümunə yaradılmır; bağlantı aktivdir.</span>}
      {state === 'ended' && <span>Sessiya tamamlanıb; yeni başlatma ayrıca sessiya yaradacaq.</span>}
    </div>

    <section className="mission-command-deck" aria-label="Missiya vəziyyəti və əməliyyatlar">
      <div className="mission-status-panel">
        <div className="mission-panel-heading"><span>MİSSİYANIN VƏZİYYƏTİ</span><ShieldCheck size={17} aria-hidden="true" /></div>
        <div className="mission-status-main"><strong data-testid="mission-status">{device ? deviceStatusNames[device.status] : '—'}</strong><span>{device?.status === 'ENDED' ? 'Bitmiş sessiya' : device?.status === 'RUNNING' ? 'Virtual raket modeli işləyir' : device?.status === 'PAUSED' ? 'Vaxt dondurulub' : 'Aktiv sessiya yoxdur'}</span></div>
        <dl className="mission-status-details">
          <div><dt>SESSİYA ID</dt><dd title={device?.run_id ?? undefined} data-testid="mission-run-id">{device?.run_id ?? 'Sessiya yoxdur'}</dd></div>
          <div><dt>BAŞLANMA</dt><dd>{run?.started_at ? new Date(run.started_at).toLocaleString('az-AZ') : '—'}</dd></div>
          <div><dt>SINAQ VAXTI</dt><dd data-testid="mission-elapsed">{formatDuration(device?.simulation_elapsed_seconds ?? 0)}</dd></div>
          <div><dt>CARİ SİSTEM REJİMİ</dt><dd>{stateName(device?.system_mode)}</dd></div>
          <div><dt>SSENARİ</dt><dd>{scenarioName(run?.scenario ?? device?.scenario)}</dd></div>
        </dl>
      </div>
      <div className="mission-operations">
        <div className="mission-panel-heading"><span>VİRTUAL CİHAZIN İDARƏSİ</span></div>
        <p className="mission-operation-note">Ssenari və əmrlər ORBITRA Device tətbiqindən idarə edilir. Burada yalnız Main tərəfindən qəbul edilmiş göstəricilər göstərilir.</p>
        <span className="mission-device-link">Virtual cihaz bu sistemdə ayrıca hesabla idarə olunur.</span>
      </div>
    </section>

    <section className={`mission-readiness readiness-${readiness.level === 'HAZIR' ? 'ready' : readiness.level === 'DİQQƏT' ? 'attention' : readiness.level === 'HAZIR DEYİL' ? 'blocked' : 'unknown'}`} aria-label="Sınağa hazırlıq" data-testid="readiness-card">
      <div><span>SINAĞA HAZIRLIQ</span><strong>{readiness.level}</strong><p>{readiness.reason}</p><small>Yalnız virtual sınağın göstəricisidir; real buraxılış və uçuş qərarı deyil.</small></div>
      <div className="readiness-checks"><span>Bağlantı: {state === 'live' || state === 'paused' ? 'Aktiv' : 'Məlumat yoxdur'}</span><span>Etibarlı paket: {latestSample && hasTrustworthyData ? `#${latestSample.sequence_number}` : 'Yoxdur'}</span><span>Sentinel: {stateName(trust?.status)}</span><span>Aktiv xəbərdarlıq: {activeAlerts.length}</span></div>
    </section>

    <div className="mission-workspace">
      <section className="mission-telemetry" aria-labelledby="live-telemetry-title">
        <div className="mission-section-heading"><div><p className="eyebrow">QƏBUL EDİLMİŞ AXIN</p><h2 id="live-telemetry-title">Canlı telemetriya</h2></div><span><Clock3 size={14} aria-hidden="true" /> #{latestSample?.sequence_number ?? '—'} · {latestSample ? new Date(latestSample.sample_time).toLocaleTimeString('az-AZ') : 'Nümunə yoxdur'}</span></div>
        {(state === 'disconnected' || state === 'stale' || state === 'ended') && <p className="mission-history-label">Qrafiklər son saxlanmış tarixi nümunələrdir; canlı ölçmə deyil.</p>}
        {rejections.length > 0 && <p className="mission-gap-note">Qrafikdə rədd edilmiş nümunə üçün dəyər yoxdur: {rejections.map(item => `#${item.sequence_number}`).join(', ')}. Xətlər həmin sıra boşluğunda qırılır.</p>}
        <div className="mission-chart-grid">
          <Chart title="Temperatur dəyişməsi" unit="°C" samples={visibleSamples} series={[
        { key: 'temperature_1_c', label: 'Sensor 1', color: '#ddac68' },
        { key: 'temperature_2_c', label: 'Sensor 2', color: '#8ab9bd' },
        { key: 'temperature_3_c', label: 'Sensor 3', color: '#b5a0d2' },
          ]} />
          <Chart title="Enerji göstəriciləri · batareya" unit="%" samples={visibleSamples} series={[{ key: 'battery_level_percent', label: 'Batareya', color: '#a9c9a9' }]} />
          <Chart title="Gərginlik" unit="V" samples={visibleSamples} series={[{ key: 'voltage_v', label: 'Gərginlik', color: '#8ab9bd' }]} />
          <Chart title="Elektrik cərəyanı" unit="A" samples={visibleSamples} series={[{ key: 'current_a', label: 'Cərəyan', color: '#ddac68' }]} />
          <Chart title="CPU və yaddaş istifadəsi" unit="%" samples={visibleSamples} series={[{ key: 'cpu_load_percent', label: 'CPU', color: '#c9a5d5' }, { key: 'memory_usage_percent', label: 'Yaddaş', color: '#8ab9bd' }]} />
          <Chart title="Rabitə keyfiyyəti · siqnal" unit="%" samples={visibleSamples} series={[{ key: 'signal_strength_percent', label: 'Siqnal', color: '#8ab9bd' }]} />
          <Chart title="Rabitə gecikməsi" unit="ms" samples={visibleSamples} series={[{ key: 'communication_latency_ms', label: 'Gecikmə', color: '#b5a0d2' }]} />
          <Chart title="Paket itkisi" unit="%" samples={visibleSamples} series={[{ key: 'packet_loss_percent', label: 'Paket itkisi', color: '#ddac68' }]} />
        </div>
      </section>
      <aside className="mission-side-stack">
        <section className="mission-side-card mission-trust-card" aria-labelledby="mission-trust-title">
          <div className="mission-side-heading"><h2 id="mission-trust-title">Telemetriya etibarlılığı</h2><ShieldCheck size={17} aria-hidden="true" /></div>
          <p><strong>{stateName(state === 'disconnected' || state === 'stale' ? 'NO DATA' : trust?.status ?? 'NO DATA')}</strong> · {verdictName(trust?.latest?.final_verdict)}</p>
          <p>Qəbul: {trust?.stats.accepted ?? 0} · Karantin: {trust?.stats.quarantined ?? 0}</p>
          <p>{trust?.active_integrity_count ? `${trust.active_integrity_count} açıq imza bütövlüyü insidenti` : 'Açıq imza insidenti yoxdur'}</p>
          {rejections.length > 0 && <p role="alert">Operator xəbərdarlığı: {rejectionTitles[rejections[rejections.length - 1].reason_code]}. Rədd edilmiş paket qrafikə və AI temperatur analizinə daxil edilməyib. <Link to="/security">Hadisəni aç →</Link></p>}
          <Link to={trust?.latest && device?.run_id ? `/telemetry-trust?run_id=${encodeURIComponent(device.run_id)}&assessment_id=${trust.active_integrity_assessment_id ?? trust.latest.id}` : '/telemetry-trust'}>Sübutlara bax →</Link>
        </section>
        <section className="mission-side-card" aria-labelledby="system-health-title">
          <div className="mission-side-heading"><h2 id="system-health-title">Sistem vəziyyəti</h2><Activity size={17} aria-hidden="true" /></div>
          <p className="mission-side-subtitle">Son etibarlı nümunə üzrə tədris qaydaları</p>
          {!latestSample && <p className="mission-empty">Məlumat yoxdur.</p>}
          {health.map(({ key, name, status, readings }) => { const Icon = healthIcons[key]; return <div className="health-row" key={key}>
            <div className="health-icon"><Icon size={17} aria-hidden="true" /></div>
            <div><div className="health-title"><strong>{name}</strong><span className={`health-${status.toLowerCase()}`}>
              {status === 'UNKNOWN' ? state === 'stale' || state === 'disconnected' ? 'Məlumat köhnəlib' : state === 'ended' ? 'Bitmiş sessiya' : 'Etibarlı məlumat yoxdur' : stateName(status)}
            </span></div><p>{latestSample ? readings.map(item => `${item.label} ${item.value}`).join(' · ') : 'Son etibarlı ölçmə yoxdur.'}</p></div>
          </div> })}
        </section>
        <section className="mission-side-card" aria-labelledby="active-alerts-title">
          <div className="mission-side-heading"><h2 id="active-alerts-title">Aktiv xəbərdarlıqlar · Qayda</h2><AlertTriangle size={17} aria-hidden="true" /></div>
          {state === 'connecting' || state === 'disconnected' || state === 'stale' ? <p className="mission-empty">Bağlantı olmadığı üçün xəbərdarlıq vəziyyəti təsdiqlənmir.</p> :
            !device?.run_id ? <p className="mission-empty">Aktiv sessiya yoxdur.</p> :
              activeAlerts.length === 0 ? <p className="mission-empty">Bu sessiyada aktiv xəbərdarlıq yoxdur.</p> :
                <ul className="mission-alert-list">{activeAlerts.map(alert => <AlertRow key={alert.alert_id} alert={alert} />)}</ul>}
        </section>
        <section className="mission-side-card mission-ai-card" aria-labelledby="mission-ai-title">
          <div className="mission-side-heading"><h2 id="mission-ai-title">AI analizi</h2><Cpu size={17} aria-hidden="true" /></div>
          {activeAIEvents.length > 0 ? activeAIEvents.map(event => <div className="mission-ai-alert" key={event.event_id}>
            <strong>Normal davranışdan fərqli sensor pəncərəsi</strong><p>{event.explanation}</p>
            <small>Bal {event.score.toFixed(4)} · #{event.window_start_sequence_number}–#{event.latest_sequence_number} · {event.affected_sensors.map(sensorName).join(', ')}</small>
            <Link to={`/ai-alerts#${event.event_id}`}>İzah və baza müqayisəsinə bax →</Link>
          </div>) : <p className="mission-empty">{aiStatus?.model_status === 'READY' ?
            (aiStatus.accepted_window_count < aiStatus.window_seconds ? 'Model məlumat toplayır.' : 'Aktiv AI anomaliya hadisəsi yoxdur.') : 'AI hazır deyil.'}</p>}
        </section>
      </aside>
    </div>
    <section className="mission-timeline" aria-labelledby="mission-timeline-title">
      <div className="mission-section-heading"><div><p className="eyebrow">SQLITE HADİSƏLƏRİ</p><h2 id="mission-timeline-title">Missiya zaman xətti</h2></div><span>{timeline.length} hadisə · yalnız cari sessiya</span></div>
      {!device?.run_id ? <p className="mission-empty">Sessiya başladıqda əməliyyatlar burada görünəcək.</p> :
        timeline.length === 0 ? <p className="mission-empty">Bu sessiya üçün hadisə gözlənilir.</p> : <>
          <ul className="mission-event-list">{recentEvents.map(item => <TimelineRow key={item.key} item={item} />)}</ul>
          {timeline.length > 5 && <details className="mission-full-history"><summary>Tam tarixçəni aç · {timeline.length} hadisə</summary><ul className="mission-event-list">{timeline.map(item => <TimelineRow key={item.key} item={item} />)}</ul></details>}
        </>}
    </section>
    <p className="device-footer">{visibleSamples.length} nümunə göstərilir · yalnız cari sessiya</p>
  </main>
}

function AlertRow({ alert }: { alert: RuleAlert }) {
  return <li className="mission-alert"><strong>QAYDA · {alert.reason}</strong><span>{alert.metric_key}: {alert.metric_value.toFixed(2)}</span>
    <small>{new Date(alert.opened_at).toLocaleString('az-AZ')} · {stateName(alert.status)}</small></li>
}

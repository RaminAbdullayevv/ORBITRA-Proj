import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Printer } from 'lucide-react'
import { generateMissionReport, getMissionReport, getReportRuns, type MissionReport, type ReportRun } from '../lib/api'
import { actionNames, auditActionName, displayModelTerm, rejectionName, scenarioName, sensorName, stateName, verdictName } from '../lib/labels'
import { assessReadiness } from '../lib/readiness'
import './mission-report.css'

const when = (value: string | null) => value ? new Date(value).toLocaleString('az-AZ') : '—'
const duration = (value: number) => `${String(Math.floor(value / 3600)).padStart(2, '0')}:${String(Math.floor(value % 3600 / 60)).padStart(2, '0')}:${String(value % 60).padStart(2, '0')}`
const statusNames = { energy: 'Enerji bloku', thermal: 'İstilik sistemi', communications: 'Telemetriya və rabitə', computer: 'Bort kompüteri' }
const sensorRows: { key: keyof NonNullable<MissionReport['latest_sample']>['sensors']; label: string; unit: string }[] = [
  { key: 'battery_level_percent', label: 'Batareya səviyyəsi', unit: '%' }, { key: 'voltage_v', label: 'Gərginlik', unit: 'V' }, { key: 'current_a', label: 'Elektrik cərəyanı', unit: 'A' },
  { key: 'temperature_1_c', label: 'Temperatur sensoru 1', unit: '°C' }, { key: 'temperature_2_c', label: 'Temperatur sensoru 2', unit: '°C' }, { key: 'temperature_3_c', label: 'Temperatur sensoru 3', unit: '°C' },
  { key: 'signal_strength_percent', label: 'Siqnal', unit: '%' }, { key: 'communication_latency_ms', label: 'Gecikmə', unit: 'ms' }, { key: 'packet_loss_percent', label: 'Paket itkisi', unit: '%' },
  { key: 'cpu_load_percent', label: 'CPU', unit: '%' }, { key: 'memory_usage_percent', label: 'Yaddaş', unit: '%' },
]

export function MissionReportPage() {
  const [params, setParams] = useSearchParams()
  const selected = params.get('run_id')
  const [runs, setRuns] = useState<ReportRun[]>([])
  const [report, setReport] = useState<MissionReport | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const readiness = report ? assessReadiness({ missionStarted: true, hasTrustedSample: !!report.latest_sample,
    connectionLost: false, paused: false, health: Object.values(report.subsystems),
    activeCriticalAlert: report.rule_alerts.some(item => item.status === 'ACTIVE' && (item.metric_key === 'temperature_1_c' && item.metric_value >= 30 && report.subsystems.thermal !== 'NORMAL' || item.metric_key === 'packet_loss_percent' && item.metric_value >= 1)),
    integrityIncident: report.security_incidents.some(item => item.status === 'OPEN' && item.reason_code === 'INTEGRITY_REJECTED'),
    quarantinedCritical: report.telemetry_trust.integrity_incident > 0,
    sentinelDegraded: report.telemetry_trust.final_status === 'DEGRADED' }) : null
  useEffect(() => {
    let active = true
    void getReportRuns().then(list => {
      if (!active) return
      setRuns(list)
      if (!selected && list.length > 0) setParams({ run_id: list[0].run_id }, { replace: true })
    }).catch(cause => { if (active) setError(cause instanceof Error ? cause.message : 'Run siyahısı alınmadı.') })
    return () => { active = false }
  }, [selected, setParams])
  useEffect(() => {
    if (!selected) { setReport(null); return }
    let active = true
    setLoading(true); setError(null); setReport(null)
    void (async () => {
      try {
        let result = await getMissionReport(selected)
        if (!active) return
        if (!result.preview && !result.generated_at) {
          await generateMissionReport(selected)
          if (!active) return
          result = await getMissionReport(selected)
        }
        if (active) setReport(result)
      } catch (cause) { if (active) setError(cause instanceof Error ? cause.message : 'Hesabat alınmadı.') }
      finally { if (active) setLoading(false) }
    })()
    return () => { active = false }
  }, [selected])
  return <main id="main-content" className="main-content report-page">
    <div className="page-crumb">ORBITRA <span>/</span> MİSSİYA HESABATI</div>
    <div className="report-heading"><div><p className="eyebrow">İŞ SAHƏSİ <span>06 / 07 · SENTINEL</span></p><h1>Missiya Hesabatı</h1>
      <p className="page-description">Virtual raket sisteminin sınaq nəticələri</p></div></div>
    <div className="report-controls"><label>Missiya sessiyası<select value={selected ?? ''} onChange={event => setParams({ run_id: event.target.value })} disabled={runs.length === 0}>
      {runs.length === 0 && <option value="">Sessiya yoxdur</option>}
      {runs.map(run => <option key={run.run_id} value={run.run_id}>{scenarioName(run.scenario)} · {stateName(run.status)} · {new Date(run.started_at).toLocaleString('az-AZ')} · {run.run_id.slice(0, 8)}</option>)}
    </select></label><button type="button" disabled={!report || report.preview || !report.generated_at} onClick={() => window.print()}><Printer size={16} /> PDF kimi çap et</button></div>
    {error && <p className="report-error" role="alert">{error}</p>}
    {loading && <p className="report-empty">Hesabat bazadan yüklənir…</p>}
    {!loading && !report && !error && <p className="report-empty">Hesabat üçün sessiya seçin.</p>}
    {report && <article className="report-sheet">
      <table className="report-print-frame"><thead><tr><th><span>ORBITRA · MİSSİYA HESABATI</span><span>SESSİYA {report.run_id}</span></th></tr></thead><tbody><tr><td>
      <header className="report-cover"><div><p className="eyebrow">ORBITRA · VİRTUAL RAKET SİSTEMİ</p><h2>Missiya hesabatı</h2><p>{report.preview ? 'İlkin görünüş — sınaq hələ yekunlaşmayıb.' : 'Tamamlanmış virtual raket sistemi sınağı'}</p></div><div className="report-badges"><span>Virtual sınaq</span><span>Saxlanmış nəticələr</span></div></header>
      <dl className="report-facts"><div><dt>SESSİYA ID</dt><dd data-testid="report-run-id">{report.run_id}</dd></div><div><dt>MİSSİYANIN ADI</dt><dd>{scenarioName(report.scenario)}</dd></div><div><dt>VƏZİYYƏT</dt><dd>{stateName(report.status)}</dd></div><div><dt>BAŞLANMA</dt><dd>{when(report.started_at)}</dd></div><div><dt>BİTMƏ</dt><dd>{when(report.ended_at)}</dd></div><div><dt>MÜDDƏT</dt><dd>{duration(report.duration_seconds)}</dd></div><div><dt>YARADILMA</dt><dd>{when(report.generated_at)}</dd></div><div><dt>QAYDA / MODEL</dt><dd>{report.rules_version} / {report.model_version ?? 'təsdiqlənməyib'}</dd></div></dl>
      <section className="report-section"><h3>Telemetriya və məlumat keyfiyyəti</h3><div className="report-metrics"><div><b>{report.accepted_count}</b><span>Qəbul edilmiş nümunə</span></div><div><b>{report.rejected_count}</b><span>Rədd qərarı</span></div><div><b>{report.sequence_gaps}</b><span>Sıra boşluğu</span></div></div><p>{report.quality_note}</p>
        {report.rejection_reasons.length > 0 && <p>Rədd səbəbləri: {report.rejection_reasons.map(rejectionName).join(', ')}</p>}
        {report.latest_sample && <p>Son etibarlı nümunə: #{report.latest_sample.sequence_number} · {when(report.latest_sample.sample_time)}</p>}
      </section>
      <section className="report-section"><h3>Yekun sistem vəziyyəti</h3><div className="report-status-grid">{Object.entries(report.subsystems).map(([key, value]) => <div key={key}><strong>{statusNames[key as keyof typeof statusNames]}</strong><span className={`report-status report-${value.toLowerCase()}`}>{stateName(value)}</span></div>)}</div>
        {report.latest_sample ? <div className="report-sensor-grid">{sensorRows.map(row => <div key={row.key}><span>{row.label}</span><strong>{report.latest_sample!.sensors[row.key].toFixed(2)} {row.unit}</strong></div>)}</div> : <p>Qəbul edilmiş son ölçmə yoxdur; vəziyyət təsdiqlənmir.</p>}
      </section>
      <section className="report-section"><h3>Qayda xəbərdarlıqları</h3>{report.rule_alerts.length === 0 ? <p>Saxlanmış qayda xəbərdarlığı yoxdur.</p> : <ul>{report.rule_alerts.map(item => <li key={`${item.rule_code}-${item.opened_at}`}>{item.reason} · {stateName(item.status)} · {when(item.opened_at)}{item.closed_at ? ` → ${when(item.closed_at)}` : ''}</li>)}</ul>}</section>
      <section className="report-section"><h3>AI analizi</h3><p>{report.ai_analysis === 'EVALUATED' ? `Saxlanmış qiymətləndirmə izi var${report.last_ai_evaluated_at ? ` · son: ${when(report.last_ai_evaluated_at)}` : ''}. Model: ${report.model_version ?? '—'}.` : 'Bu sessiyada AI analizi əlçatan olmayıb; saxlanmış qiymətləndirmə izi yoxdur.'}</p>
        {report.ai_events.length > 0 && <ul>{report.ai_events.map(item => <li key={item.event_id}>#{item.start_sequence_number} · {stateName(item.status)} · {item.explanation} · {when(item.started_at)} · {item.model_version}</li>)}</ul>}
        {report.ai_analysis === 'EVALUATED' && report.ai_events.length === 0 && <p>Qiymətləndirmə olub, təsdiqlənmiş anomaliya hadisəsi saxlanmayıb.</p>}</section>
      <section className="report-section report-trust-section"><h3>Telemetriya etibarlılığı və səbəb təhlili</h3>
        <div className="report-metrics"><div><b>{report.telemetry_trust.accepted}</b><span>Qəbul edilmiş paket</span></div><div><b>{report.telemetry_trust.rejected}</b><span>Rədd edilmiş / karantin</span></div><div><b>{report.telemetry_trust.system_anomaly}</b><span>Sistem anomaliyası</span></div><div><b>{report.telemetry_trust.sensor_fault}</b><span>Sensor nasazlığı</span></div><div><b>{report.telemetry_trust.integrity_incident}</b><span>İmza problemi</span></div><div><b>{report.telemetry_trust.replay_incident}</b><span>Təkrar paket</span></div><div><b>{report.telemetry_trust.stale_data}</b><span>Köhnəlmiş məlumat</span></div></div>
        <p>Yekun etibarlılıq: <strong>{stateName(report.telemetry_trust.final_status)}</strong> · Qaydalar: {report.telemetry_trust.ruleset_version} · AI modeli: {report.telemetry_trust.model_version ?? 'əlçatan deyil'}.</p>
        {report.telemetry_trust.key_decisions.length === 0 ? <p>Əsas Sentinel qərarı yoxdur.</p> : <ul>{report.telemetry_trust.key_decisions.map(item => <li key={item.id}><strong>{verdictName(item.verdict)}</strong> · {displayModelTerm(item.explanation)}<small>Paket {item.packet_id} · {Object.entries(item.evidence).filter(([key]) => ['temp_1_c', 'temp_2_c', 'temp_3_c', 'current_a', 'sensor_difference_c', 'rejection_code'].includes(key)).map(([key, value]) => `${sensorName(key)}: ${value}`).join(' · ')}</small></li>)}</ul>}
        <p>Administrator əməliyyatları: {report.operator_events.filter(item => item.action === 'reduce_processing_load' && item.outcome === 'SUCCESS').length} virtual yük azaltma əməliyyatı. Bütün əməliyyatlar aşağıda vaxt və istifadəçi ilə göstərilir.</p>
      </section>
      <section className="report-section report-cyber-section"><h3>Kibertəhlükəsizlik sınağının nəticələri</h3>
        <p>{report.cyber_security.scope_note}</p>
        <div className="report-metrics"><div><b>{report.cyber_security.total}</b><span>Test hadisəsi</span></div><div><b>{report.cyber_security.detected}</b><span>Düzgün aşkarlandı</span></div><div><b>{report.cyber_security.rejected}</b><span>Rədd edildi</span></div><div><b>{report.cyber_security.accepted}</b><span>Qəbul edildi</span></div></div>
        <p><strong>{report.cyber_security.total > 0 ? `${report.cyber_security.detected}/${report.cyber_security.total} sınaq hadisəsi düzgün aşkarlandı — ${report.cyber_security.detection_rate_percent}%` : 'Nəticəsi məlum olan virtual kiber test yoxdur; faiz hesablanmır.'}</strong></p>
        {Object.keys(report.cyber_security.rejection_reasons).length > 0 && <p>Faktiki rədd səbəbləri: {Object.entries(report.cyber_security.rejection_reasons).map(([code, count]) => `${rejectionName(code)}: ${count}`).join(' · ')}</p>}
        {report.cyber_security.events.length > 0 && <ul>{report.cyber_security.events.map(item => <li key={`${item.packet_id}-${item.created_at}`}>
          <strong>{item.test_name}</strong> · #{item.sequence_number} · {when(item.created_at)} · {item.outcome === 'REJECTED' ? 'Rədd edildi' : 'Qəbul edildi'} · {item.detected_correctly ? 'Gözlənilən yoxlama səbəbi ilə aşkarlandı' : 'Araşdırma tələb edir'}.
          <br />Müşahidə olunan səbəb: {item.observed_reason_code ? rejectionName(item.observed_reason_code) : 'Rədd səbəbi yoxdur'}.
          <br />Operator xəbərdarlığı: {item.operator_alert}
          {item.mitre && <><br />Oxşar MITRE ATT&amp;CK ICS texnikası: <a href={item.mitre.url} target="_blank" rel="noopener noreferrer">{item.mitre.code} — {item.mitre.name}</a> ({item.mitre.qualification})</>}
        </li>)}</ul>}
      </section>
      {readiness && <section className="report-section"><h3>Sınağa hazırlıq nəticəsi</h3><p><strong>{readiness.level}</strong> · {readiness.reason}</p><p>{report.preview ? 'Bu, sınağın ilkin göstəricisidir' : 'Bu, saxlanmış virtual sınaq nəticələrinin retrospektiv göstəricisidir'}; real buraxılış qərarı deyil.</p></section>}
      <section className="report-section"><h3>Təhlükəsizlik hadisələri</h3>{report.security_incidents.length === 0 && report.security_audit.length === 0 ? <p>Bu sessiya üçün saxlanmış təhlükəsizlik hadisəsi yoxdur.</p> : <>
        <ul>{report.security_incidents.map(item => <li key={item.incident_id}>{rejectionName(item.reason_code)} · #{item.sequence_number ?? '—'} · {stateName(item.status)} · {item.summary} · {when(item.created_at)}{item.close_reason ? ` · Qərar: ${item.close_reason}` : ''}</li>)}</ul>
        <ul>{report.security_audit.map((item, index) => <li key={index}>{auditActionName(item.action)} · {stateName(item.outcome)} · {rejectionName(item.reason_code)} · {when(item.occurred_at)}</li>)}</ul></>}
      </section>
      <section className="report-section"><h3>Administrator əməliyyatları</h3>{report.operator_events.length === 0 ? <p>Bu sınaq üçün əməliyyat qeydi yoxdur.</p> : <table><thead><tr className="report-table-run"><th colSpan={5}>ORBITRA · MİSSİYA HESABATI · SESSİYA {report.run_id}</th></tr><tr><th>Vaxt</th><th>Əməliyyat</th><th>Nəticə</th><th>İstifadəçi</th><th>Sınaq vaxtı</th></tr></thead><tbody>{report.operator_events.map(item => <tr key={item.event_number}><td>{when(item.received_at)}</td><td>{actionNames[item.action as keyof typeof actionNames] ?? item.action}<small>{item.reason}</small></td><td>{stateName(item.outcome)}</td><td>{item.username ?? (item.user_id === null ? 'Köhnə demo qeydi' : `#${item.user_id}`)}</td><td>{duration(item.simulation_elapsed_seconds)}</td></tr>)}</tbody></table>}</section>
      <section className="report-section report-limitations"><h3>Məlum məhdudiyyətlər</h3><ul>{report.limitations.map(item => <li key={item}>{item.replace('aktiv run', 'aktiv sessiya')}</li>)}</ul><p>Bağlantı keyfiyyəti barədə qeyd: canlı axının əvvəlki fasilələri ayrıca ölçülməyib; hesabat yalnız saxlanmış sıra boşluqlarını göstərir. Heç bir real raketə qoşulmayıb.</p></section>
      <p className="report-virtual-note">Bu hesabat ORBITRA virtual raket sistemi sınaq mühitində yaradılıb.</p>
      </td></tr></tbody></table>
    </article>}
    <p className="device-footer">ORBITRA · Raket sistemləri üçün virtual sınaq platforması</p>
  </main>
}

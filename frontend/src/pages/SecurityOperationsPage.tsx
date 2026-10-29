import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { ShieldAlert, ShieldCheck } from 'lucide-react'
import { addIncidentNote, closeIncident, getSecurityOverview, type SecurityIncident, type SecurityOverview } from '../lib/api'
import { useAuth } from '../lib/AuthContext'
import { useLiveTelemetry } from '../lib/useLiveTelemetry'
import { auditActionName, rejectionName, scenarioName, stateName } from '../lib/labels'
import './security-operations.css'

const reasonLabels: Record<string, string> = {
  SCHEMA_REJECTED: 'Format rəddi', INTEGRITY_REJECTED: 'İmza rəddi', SOURCE_REJECTED: 'Mənbə rəddi', REPLAY_REJECTED: 'Təkrar paket rəddi',
  ROLE_DENIED: 'Rol icazəsi yoxdur', INVALID_CREDENTIALS: 'Yanlış giriş', RATE_LIMITED: 'Giriş məhdudiyyəti',
  AUTHENTICATED: 'Giriş', SESSION_REVOKED: 'Çıxış', NOTE_ADDED: 'Qeyd əlavə edildi',
  REVIEWED_AND_CLOSED: 'İnsident bağlandı', CSRF_REJECTED: 'Sorğu qoruması rəddi', REPORT_READY: 'Hesabat hazırdır',
}

const blockNames: Record<string, string> = {
  thermal: 'İstilik bloku / temperatur sensoru 1',
  communications: 'Telemetriya və rabitə bloku', telemetry: 'Telemetriya paketi',
}
const checkNames: Record<string, string> = {
  schema_valid: 'Paket formatı', source_valid: 'Mənbə', signature_valid: 'Bütövlük imzası',
  replay_detected: 'Təkrar sıra nömrəsi', freshness_valid: 'Vaxt pəncərəsi',
}
const checkResult = (key: string, value: boolean | null) => value === null ? 'Yoxlanılmadı'
  : key === 'replay_detected' ? value ? 'Təkrar aşkarlandı' : 'Təkrar yoxdur'
    : value ? 'Keçdi' : 'Uğursuz oldu'

function IncidentCard({ incident, canReview, refresh }: { incident: SecurityIncident; canReview: boolean; refresh: () => Promise<void> }) {
  const [note, setNote] = useState('')
  const [reason, setReason] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const submitNote = async (event: FormEvent) => {
    event.preventDefault(); setPending(true); setError(null)
    try { await addIncidentNote(incident.incident_id, note); setNote(''); await refresh() }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Qeyd saxlanmadı.') }
    finally { setPending(false) }
  }
  const submitClose = async (event: FormEvent) => {
    event.preventDefault(); setPending(true); setError(null)
    try { await closeIncident(incident.incident_id, reason); setReason(''); await refresh() }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'İnsident bağlanmadı.') }
    finally { setPending(false) }
  }
  return <li className="security-incident" id={incident.incident_id}>
    <div className="security-incident-top"><strong>{reasonLabels[incident.reason_code] ?? incident.reason_code}</strong><span className={incident.status === 'OPEN' ? 'security-open' : 'security-closed'}>{incident.status === 'OPEN' ? 'AÇIQ' : 'BAĞLANIB'}</span></div>
    <p>{incident.summary}</p>
    <small>{new Date(incident.created_at).toLocaleString('az-AZ')} · Sessiya {incident.run_id ?? '—'} · {incident.source_id ?? '—'} · #{incident.sequence_number ?? '—'}</small>
    {incident.detail && <details className="security-incident-detail">
      <summary>Göndərilən paket və yoxlama nəticəsi</summary>
      {incident.detail.test_name && <p><strong>Seçilmiş virtual test:</strong> {incident.detail.test_name}. Test adı müşahidə edilmiş hücum növünün sübutu deyil.</p>}
      <div className="security-detail-grid">
        <section><h3>Nə göndərildi?</h3>
          <p>Paket: {incident.detail.packet_id ?? '—'} · Sıra: #{incident.detail.sent.sequence_number ?? '—'}</p>
          <p>Mənbə: {incident.detail.sent.source_id ?? '—'} · Vaxt: {incident.detail.sent.sample_time ? new Date(incident.detail.sent.sample_time).toLocaleString('az-AZ') : '—'}</p>
          {incident.detail.sent.sensors && <p>Göndərilən temperatur 1: {incident.detail.sent.sensors.temperature_1_c.toFixed(2)} °C</p>}
          <p>Təsirlənən məlumat: {blockNames[incident.detail.affected_block] ?? incident.detail.affected_block}</p>
        </section>
        <section><h3>Hansı yoxlama uğursuz oldu?</h3>
          <p><strong>{rejectionName(incident.detail.observed_reason_code)}</strong> · {incident.detail.observed_reason}</p>
          <ul>{Object.entries(incident.detail.checks).map(([key, value]) => <li key={key}>{checkNames[key] ?? key}: {checkResult(key, value)}</li>)}</ul>
        </section>
        <section><h3>Sistem nə etdi?</h3><p>Nəticə: {incident.detail.outcome === 'REJECTED' ? 'Rədd edildi' : 'Araşdırma tələb edir'}</p><p>{incident.detail.action}</p></section>
      </div>
      <p>{incident.detail.mitre ? <>Oxşar MITRE ATT&amp;CK ICS texnikası: <a href={incident.detail.mitre.url} target="_blank" rel="noopener noreferrer">{incident.detail.mitre.code} — {incident.detail.mitre.name}</a> · {incident.detail.mitre.qualification}</> : 'Oxşar MITRE ATT&CK ICS texnikası: Dəqiq texnika müəyyən edilməyib.'}</p>
    </details>}
    {incident.notes.length > 0 && <div className="security-notes"><strong>Analitik qeydləri</strong>{incident.notes.map(item => <p key={item.id}>{item.body}<small>{item.author_username ?? `#${item.author_user_id}`} · {new Date(item.created_at).toLocaleString('az-AZ')}</small></p>)}</div>}
    {incident.status === 'CLOSED' && <p className="security-decision">Qərar: {incident.close_reason} · {incident.closed_by_username ?? 'Analitik'} · {incident.closed_at ? new Date(incident.closed_at).toLocaleString('az-AZ') : '—'}</p>}
    {canReview && <div className="security-review">
      <form onSubmit={event => void submitNote(event)}><label>İnsidentə qeyd<textarea value={note} onChange={event => setNote(event.target.value)} minLength={2} maxLength={1000} required /></label><button disabled={pending || note.trim().length < 2}>Qeydi əlavə et</button></form>
      {incident.status === 'OPEN' && <form onSubmit={event => void submitClose(event)}><label>Bağlama səbəbi<input value={reason} onChange={event => setReason(event.target.value)} minLength={5} maxLength={500} required /></label><button disabled={pending || reason.trim().length < 5}>Əsaslandırıb bağla</button></form>}
    </div>}
    {error && <p role="alert" className="security-error">{error}</p>}
  </li>
}

export function SecurityOperationsPage() {
  const { identity } = useAuth()
  const canReview = identity?.role === 'SECURITY_ANALYST' || identity?.role === 'ADMIN'
  const { device, run, samples, rejections, state } = useLiveTelemetry()
  const [overview, setOverview] = useState<SecurityOverview | null>(null)
  const [error, setError] = useState<string | null>(null)
  const refresh = useCallback(async () => {
    try { setOverview(await getSecurityOverview()); setError(null) }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Audit məlumatı alınmadı.') }
  }, [])
  useEffect(() => {
    void refresh()
    const timer = window.setInterval(() => void refresh(), 2000)
    return () => window.clearInterval(timer)
  }, [refresh])
  const accepted = device?.run_id ? samples.filter(item => item.run_id === device.run_id) : []
  return <main id="main-content" className="main-content security-page">
    <div className="page-crumb">ORBITRA <span>/</span> TƏHLÜKƏSİZLİK ƏMƏLİYYATLARI</div>
    <div className="security-heading"><div><p className="eyebrow">İŞ SAHƏSİ <span>04 / 07 · SENTINEL</span></p>
      <h1>Təhlükəsizlik Mərkəzi</h1><p className="page-description">Lokal giriş, rol qərarları və paket rədləri. Qeydlər təsdiqlənmiş kiberhücum sübutu kimi təqdim edilmir.</p></div></div>
    <section className="security-run" aria-label="Cari sessiya">
      <div><span>CARİ SESSİYA ID</span><strong data-testid="security-run-id">{device?.run_id ?? 'Sessiya yoxdur'}</strong></div>
      <div><span>SSENARİ</span><strong>{scenarioName(run?.scenario ?? device?.scenario)}</strong></div>
      <div><span>BAĞLANTI</span><strong>{state === 'live' ? 'Canlı' : state === 'paused' ? 'Dayandırılıb' : state === 'ended' ? 'Bitmiş sessiya' : state === 'stale' ? 'Məlumat köhnəlib' : state === 'disconnected' ? 'Kəsilib' : 'Gözlənilir'}</strong></div>
      <div><span>ROL</span><strong>{identity?.role === 'ADMIN' ? 'Administrator' : identity?.role === 'SECURITY_ANALYST' ? 'Təhlükəsizlik analitiki' : identity?.role === 'OPERATOR' ? 'Operator' : identity?.role === 'OBSERVER' ? 'Müşahidəçi' : '—'}</strong></div>
    </section>
    <div className="security-grid">
      <section className="security-card" aria-labelledby="accepted-title">
        <div className="security-card-heading"><ShieldCheck size={19} aria-hidden="true" /><h2 id="accepted-title">Qəbul edilmiş telemetriya</h2><span>{accepted.length} göstərilir</span></div>
        <p>Yalnız imza və format yoxlamasından keçmiş SQLite nümunələri qrafikə, canlı axına və AI analizinə daxil olur.</p>
        {accepted.length === 0 ? <div className="security-empty">Bu sessiyada hələ qəbul edilmiş nümunə yoxdur.</div> :
          <ul className="security-sample-list">{accepted.slice(-8).reverse().map(item => <li key={item.sequence_number}><strong>#{item.sequence_number}</strong><span>{new Date(item.sample_time).toLocaleTimeString('az-AZ')}</span><span>T1 {item.sensors.temperature_1_c.toFixed(2)} °C</span></li>)}</ul>}
      </section>
      <section className="security-card security-rejected" aria-labelledby="rejected-title">
        <div className="security-card-heading"><ShieldAlert size={19} aria-hidden="true" /><h2 id="rejected-title">Rədd edilmiş test nümunələri</h2><span>{rejections.length} hadisə</span></div>
        <p>Format, imza və təkrar paket qərarları ayrıca səbəb kodları ilə qeydə alınır.</p>
        {rejections.length === 0 ? <div className="security-empty">Bu sessiyada rədd edilmiş nümunə yoxdur.</div> :
          <ul className="security-rejection-list">{rejections.map(item => <li key={item.rejection_id} data-rejection-sequence={item.sequence_number}>
            <strong>{reasonLabels[item.reason_code] ?? rejectionName(item.reason_code)}</strong><p>{item.reason}</p>
            <dl><div><dt>SESSİYA ID</dt><dd>{item.run_id}</dd></div><div><dt>SIRA</dt><dd>#{item.sequence_number}</dd></div>
              <div><dt>VAXT</dt><dd>{new Date(item.rejected_at).toLocaleString('az-AZ')}</dd></div><div><dt>SƏBƏB</dt><dd>{rejectionName(item.reason_code)}</dd></div></dl>
          </li>)}</ul>}
      </section>
    </div>
    <section className="security-card security-history" aria-labelledby="incidents-title">
      <div className="security-card-heading"><ShieldAlert size={19} aria-hidden="true" /><h2 id="incidents-title">İnsidentlər</h2><span>{overview?.incidents.length ?? 0} qeyd</span></div>
      <p>{canReview ? 'Təhlükəsizlik analitiki qeyd əlavə edib əsaslandırılmış qərarla insidenti bağlaya bilər.' : 'Bu rol insidentləri oxuya bilər; qərar verə bilməz.'}</p>
      {error && <p role="alert" className="security-error">{error}</p>}
      {!overview ? <div className="security-empty">İnsident tarixçəsi yüklənir.</div> : overview.incidents.length === 0 ? <div className="security-empty">Saxlanmış insident yoxdur.</div> :
        <ul className="security-incident-list">{overview.incidents.map(item => <IncidentCard key={item.incident_id} incident={item} canReview={canReview} refresh={refresh} />)}</ul>}
    </section>
    <section className="security-card security-history" aria-labelledby="audit-title">
      <div className="security-card-heading"><ShieldCheck size={19} aria-hidden="true" /><h2 id="audit-title">Audit tarixçəsi</h2><span>son {overview?.audit.length ?? 0} qeyd</span></div>
      <p>Giriş, çıxış, uğursuz giriş, rol rəddi və paket rəddi. Parol, sessiya cookie-si və HMAC açarı burada saxlanmır. Lokal baza administratoru bu tarixçəni dəyişə bilər.</p>
      {overview?.audit.length ? <ul className="security-audit-list">{overview.audit.map(item => <li key={item.id}>
        <strong>{reasonLabels[item.reason_code] ?? rejectionName(item.reason_code)}</strong><span>{auditActionName(item.action)} · {stateName(item.outcome)}</span>
        <small>{new Date(item.occurred_at).toLocaleString('az-AZ')} · {item.username ?? 'sistem'}{item.user_id ? ` (#${item.user_id})` : ''} · Sessiya {item.run_id ?? '—'} · #{item.sequence_number ?? '—'}</small>
      </li>)}</ul> : <div className="security-empty">Audit qeydi yoxdur.</div>}
    </section>
    <p className="device-footer">Audit və insidentlər lokal SQLite bazasından gəlir.</p>
  </main>
}

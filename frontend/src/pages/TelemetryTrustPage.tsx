import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Activity, ArrowRight, ShieldAlert, ShieldCheck } from 'lucide-react'
import { getTrustDecision, getTrustDecisions, type TrustDecision } from '../lib/api'
import { useLiveTelemetry } from '../lib/useLiveTelemetry'
import { mergeTrustHistory } from '../lib/trustHistory'
import { displayModelTerm, rejectionName, scenarioName, severityName, stateName, verdictName } from '../lib/labels'
import './telemetry-trust.css'

const when = (value: string | null | undefined) => value ? new Date(value).toLocaleString('az-AZ') : '—'
const checkDetail = (value: string) => ({ NOT_EVALUATED: 'Yoxlanılmayıb', DIVERGENT: 'Sensorlar fərqlənir', COHERENT_RISE: 'Əlaqəli temperatur artımı', CONSISTENT: 'Sensorlar uyğundur', PEERS_NORMAL: 'Digər sensorlar normaldır', HEAT_CONFIRMED: 'İstilik artımı təsdiqlənib', NO_BASELINE: 'Baza məlumatı yoxdur' }[value] ?? value)

type Stage = { name: string; state: 'passed' | 'warning' | 'rejected' | 'idle'; detail: string }
const check = (value: boolean | null, negative = false): Stage['state'] => value === null ? 'idle' : value === negative ? 'rejected' : 'passed'
function stages(item: TrustDecision | null): Stage[] {
  if (!item) return ['Format', 'Mənbə kimliyi', 'İmza bütövlüyü', 'Təkrar paket', 'Vaxt uyğunluğu', 'Sensor uyğunluğu', 'Rəqəmsal Model', 'Yekun qərar']
    .map(name => ({ name, state: 'idle', detail: 'Məlumat gözlənilir' }))
  const cross = item.cross_sensor_status
  const twin = item.digital_twin_status
  return [
    { name: 'Format', state: check(item.schema_valid), detail: item.schema_valid ? 'Format uyğundur' : 'Format rədd edildi' },
    { name: 'Mənbə kimliyi', state: check(item.source_valid), detail: item.source_valid === null ? 'Yoxlanılmadı' : item.device_id },
    { name: 'İmza bütövlüyü', state: check(item.signature_valid), detail: item.signature_valid === null ? 'Yoxlanılmadı' : item.signature_valid ? 'HMAC-SHA256 uyğundur' : 'İmza yanlışdır' },
    { name: 'Təkrar paket', state: check(item.replay_detected, true), detail: item.replay_detected === null ? 'Yoxlanılmadı' : item.replay_detected ? 'Sıra təkrarı' : 'Yeni sıra nömrəsi' },
    { name: 'Vaxt uyğunluğu', state: check(item.freshness_valid), detail: item.freshness_valid === null ? 'Yoxlanılmadı' : item.freshness_valid ? 'Vaxt pəncərəsindədir' : 'Vaxt rədd edildi' },
    { name: 'Sensor uyğunluğu', state: cross === 'NOT_EVALUATED' ? 'idle' : cross === 'DIVERGENT' || cross === 'COHERENT_RISE' ? 'warning' : 'passed', detail: checkDetail(cross) },
    { name: 'Rəqəmsal Model', state: twin === 'NOT_EVALUATED' ? 'idle' : twin === 'PEERS_NORMAL' || twin === 'HEAT_CONFIRMED' ? 'warning' : 'passed', detail: checkDetail(twin) },
    { name: 'Yekun qərar', state: item.accepted ? item.severity === 'INFO' ? 'passed' : 'warning' : 'rejected', detail: verdictName(item.final_verdict) },
  ]
}

const evidenceLabels: Record<string, string> = {
  temp_1_c: 'Temperatur 1 · °C', temp_2_c: 'Temperatur 2 · °C', temp_3_c: 'Temperatur 3 · °C',
  current_a: 'Cərəyan · A', cpu_load_percent: 'CPU yükü · %', virtual_load_percent: 'Virtual yük · %',
  power_w: 'Enerji sərfi · W', twin_expected_temperature_c: 'Rəqəmsal Modelin gözlədiyi · °C',
  sensor_difference_c: 'Sensor fərqi · °C', previous_peer_temperature_c: 'Əvvəlki digər sensor temperaturu · °C',
  packet_age_seconds: 'Paket yaşı · saniyə', last_accepted_sequence: 'Son qəbul edilmiş sıra',
  rejection_code: 'Rədd kodu',
}

export function TelemetryTrustPage() {
  const { device, trust, state } = useLiveTelemetry()
  const [params, setParams] = useSearchParams()
  const runId = params.get('run_id') ?? device?.run_id ?? null
  const selectedId = Number(params.get('assessment_id')) || null
  const [history, setHistory] = useState<TrustDecision[]>([])
  const [selectedDetail, setSelectedDetail] = useState<TrustDecision | null>(null)
  const [page, setPage] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!runId) { setHistory([]); setHasMore(false); return }
    let active = true
    setHistory([]); setPage(0); setError(null)
    void getTrustDecisions(runId).then(result => {
      if (active) { setHistory(result.decisions); setHasMore(result.has_more) }
    }).catch(cause => { if (active) setError(cause instanceof Error ? cause.message : 'Qərarlar alınmadı.') })
    return () => { active = false }
  }, [runId])

  useEffect(() => {
    if (!trust?.latest || trust.latest.mission_id !== runId || page !== 0) return
    setHistory(current => mergeTrustHistory(current, [trust.latest!], 30))
  }, [trust?.latest?.id, runId, page])

  useEffect(() => {
    setSelectedDetail(null)
    if (!runId || !selectedId) return
    let active = true
    setError(null)
    void getTrustDecision(runId, selectedId).then(result => { if (active) setSelectedDetail(result) })
      .catch(cause => { if (active) setError(cause instanceof Error ? cause.message : 'Seçilmiş qərar alınmadı.') })
    return () => { active = false }
  }, [runId, selectedId])

  const selected = selectedId ? history.find(item => item.id === selectedId) ??
    (selectedDetail?.id === selectedId && selectedDetail.mission_id === runId ? selectedDetail : null) :
    (trust?.latest?.mission_id === runId ? trust.latest : null) ?? history[0] ?? null
  const activeTrust = trust?.latest?.mission_id === runId ? trust : null
  const status = state === 'disconnected' || state === 'stale' || state === 'connecting' ? 'NO DATA' : activeTrust?.status ?? 'NO DATA'
  const stats = activeTrust?.stats
  const evidenceCoverage = selected ? Math.round(([
    selected.schema_valid, selected.source_valid, selected.signature_valid,
    selected.replay_detected, selected.freshness_valid,
  ].filter(value => value !== null).length +
    (selected.cross_sensor_status !== 'NOT_EVALUATED' ? 1 : 0) +
    (selected.digital_twin_status !== 'NOT_EVALUATED' ? 1 : 0)) / 7 * 100) : 0

  const loadMore = async () => {
    if (!runId || busy || history.length === 0) return
    setBusy(true); setError(null)
    try {
      const result = await getTrustDecisions(runId, history[history.length - 1].id)
      setHistory(result.decisions)
      setPage(current => current + 1)
      setHasMore(result.has_more)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Tarixçə alınmadı.') }
    finally { setBusy(false) }
  }

  return <main id="main-content" className="main-content trust-page">
    <div className="page-crumb">ORBITRA <span>/</span> SENTINEL</div>
    <div className="trust-heading"><div><p className="eyebrow">İŞ SAHƏSİ <span>07 / 07 · SENTINEL</span></p><h1>Telemetriya Etibarlılığı</h1>
      <p className="page-description">Virtual raket sistemindən qəbul və karantinə qədər hər paketin ardıcıl yoxlaması. Qərar və sübut backend-də saxlanır.</p></div></div>
    <section className="trust-summary" aria-label="Sentinel vəziyyəti">
      <div><small>SENTINEL VƏZİYYƏTİ</small><strong className={`trust-${status.toLowerCase().replace(' ', '-')}`}>{stateName(status)}</strong><span>Son etibarlı qəbul: {when(activeTrust?.last_successful_at)}</span></div>
      <div><small>SON PAKETİN QƏRARI</small><strong>{activeTrust?.latest ? verdictName(activeTrust.latest.final_verdict) : 'Paket gözlənilir'}</strong><span>{activeTrust?.latest ? `#${activeTrust.latest.sequence_number} · ${when(activeTrust.latest.received_at)}` : 'Qəbul edilmiş canlı məlumat yoxdur'}</span></div>
      <div><small>SESSİYA ID</small><strong className="trust-run">{runId ?? 'Sessiya yoxdur'}</strong><span>{state === 'disconnected' || state === 'stale' ? 'Canlı bağlantı təsdiqlənmir' : scenarioName(device?.scenario)}</span></div>
    </section>
    {error && <p className="trust-error" role="alert">{error}</p>}
    <div className="trust-main-grid">
      <section className="trust-card"><div className="trust-card-title"><Activity size={18} /><h2>Canlı etibarlılıq yoxlaması</h2></div>
        <ol className="trust-pipeline">{stages(selected).map((stage, index) => <li key={stage.name} className={`trust-stage trust-stage-${stage.state}`}>
          <b>{String(index + 1).padStart(2, '0')}</b><div><strong>{stage.name}</strong><span>{stage.detail}</span></div><em>{stage.state === 'passed' ? 'KEÇİB' : stage.state === 'warning' ? 'XƏBƏRDARLIQ' : stage.state === 'rejected' ? 'RƏDD EDİLİB' : 'YOXLANILMAYIB'}</em>
        </li>)}</ol>
        <p className="trust-flow">Virtual raket sistemi <ArrowRight size={13} /> Qəbul qapısı <ArrowRight size={13} /> Sentinel <ArrowRight size={13} /> {selected?.accepted ? 'Qəbul → AI + Rəqəmsal Model → Missiya İdarəetmə' : 'Karantin'} <ArrowRight size={13} /> Audit + Hesabat</p>
      </section>
      <section className="trust-card trust-evidence"><div className="trust-card-title"><ShieldCheck size={18} /><h2>Sübutlar</h2></div>
        {!selected ? <p className="trust-empty">Paket başladıqda saxlanmış qərarın sübutları burada görünəcək.</p> : <>
          <span className={`trust-verdict trust-severity-${selected.severity.toLowerCase()}`}>{verdictName(selected.final_verdict)} · {severityName(selected.severity)}</span>
          <p>{displayModelTerm(selected.explanation)}</p><dl>
            <div><dt>Paket ID</dt><dd>{selected.packet_id}</dd></div><div><dt>Cihaz ID</dt><dd>{selected.device_id}</dd></div>
            {Object.entries(selected.evidence).filter(([key]) => key !== 'twin_method').map(([key, value]) => <div key={key}><dt>{evidenceLabels[key] ?? key}</dt><dd>{value ?? '—'}</dd></div>)}
            <div><dt>Qayda versiyası</dt><dd>{selected.ruleset_version}</dd></div><div><dt>AI model versiyası</dt><dd>{selected.model_version ?? 'Əlçatan deyil'}</dd></div>
            <div><dt>Emal müddəti</dt><dd>{selected.processing_time_ms.toFixed(3)} ms</dd></div>
            <div><dt>Sübut əhatəsi</dt><dd>{evidenceCoverage}%</dd></div>
          </dl><small>Sübut əhatəsi qiymətləndirilmiş 7 yoxlama mərhələsinin payıdır. Bu, hücum ehtimalı deyil. Rəqəmsal Modelin istilik müqayisəsi sadələşdirilmiş tədris modelidir.</small>
        </>}
      </section>
    </div>
    <section className="trust-card"><div className="trust-card-title"><ShieldAlert size={18} /><h2>Karantinə alınmış paketlər</h2></div>
      {!activeTrust?.quarantine.length ? <p className="trust-empty">Bu sessiyada karantinə alınmış paket yoxdur.</p> : <div className="trust-table-wrap"><table><thead><tr><th>Paket ID</th><th>Cihaz</th><th>Vaxt</th><th>Səbəb</th><th>İmza</th><th>Təkrar</th><th>Qrafik</th><th>İnsident</th></tr></thead><tbody>
        {activeTrust.quarantine.map(item => <tr key={item.rejection_id}><td>{item.packet_id ?? 'Tarixi qeyd'}</td><td>{item.source_id}</td><td>{when(item.rejected_at)}</td><td>{rejectionName(item.reason_code)}<small>{item.reason}</small></td><td>{item.signature_status === 'VALID' ? 'Etibarlı' : item.signature_status === 'INVALID' ? 'Yanlış' : 'Naməlum'}</td><td>{item.reason_code === 'REPLAY_REJECTED' ? 'Bəli' : 'Xeyr'}</td><td>Buraxılmadı</td><td>{item.incident_id ? <Link to={`/security#${item.incident_id}`}>Aç →</Link> : 'Tarixi qeyd'}</td></tr>)}
      </tbody></table></div>}
    </section>
    <section className="trust-card"><div className="trust-card-title"><Activity size={18} /><h2>Son etibarlılıq qərarları</h2></div>
      {history.length === 0 ? <p className="trust-empty">Bu sessiya üçün qərar yoxdur.</p> : <div className="trust-history">{history.map(item => <button key={item.id} type="button" className={selected?.id === item.id ? 'selected' : ''}
        onClick={() => setParams({ run_id: item.mission_id, assessment_id: String(item.id) })}><time>{when(item.received_at)}</time><span>#{item.sequence_number} · {item.packet_id.slice(0, 8)}</span><strong>{verdictName(item.final_verdict)}</strong><em>{severityName(item.severity)}</em><small>{displayModelTerm(item.explanation)}</small></button>)}</div>}
      {hasMore && <button className="trust-load" type="button" disabled={busy} onClick={() => void loadMore()}>{busy ? 'Yüklənir…' : 'Daha əvvəlki qərarlar'}</button>}
      {page > 0 && <button className="trust-load" type="button" onClick={() => {
        if (!runId) return
        setPage(0)
        void getTrustDecisions(runId).then(result => { setHistory(result.decisions); setHasMore(result.has_more) })
          .catch(cause => setError(cause instanceof Error ? cause.message : 'Qərarlar alınmadı.'))
      }}>Son qərarlara qayıt</button>}
    </section>
    <section className="trust-card"><div className="trust-card-title"><ShieldCheck size={18} /><h2>Sessiya statistikası</h2></div>
      <div className="trust-stats">{[
        ['Qəbul edilmiş', stats?.accepted], ['Karantin', stats?.quarantined], ['Sistem anomaliyası', stats?.system_anomaly],
        ['Sensor nasazlığı', stats?.sensor_fault], ['İmza problemi', stats?.integrity_incident],
        ['Təkrar paket', stats?.replay_incident], ['Köhnəlmiş məlumat', stats?.stale_data],
      ].map(([label, value]) => <div key={label}><strong>{value ?? 0}</strong><span>{label}</span></div>)}</div>
    </section>
    <p className="device-footer">Yoxlama nəticələri və sübutlar lokal bazadan alınır.</p>
  </main>
}

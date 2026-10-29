import { useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { AlertTriangle, BrainCircuit, DatabaseZap, ShieldAlert, ShieldCheck } from 'lucide-react'
import type { AIEvent } from '../lib/api'
import { useLiveTelemetry } from '../lib/useLiveTelemetry'
import { displayModelTerm, scenarioName, sensorName, stateName, verdictName } from '../lib/labels'
import './ai-alerts.css'

function AIEventCard({ event }: { event: AIEvent }) {
  return <li id={event.event_id} className={`ai-event-card ai-event-${event.status.toLowerCase()}`}>
    <div className="ai-event-top"><span className="ai-source-tag">AI ANALİZİ</span><span>{event.status === 'ACTIVE' ? 'DAVAM EDİR' : event.status === 'RESOLVED' ? 'BƏRPA OLUNUB' : 'SESSİYA BİTİB'}</span></div>
    <h3>Normal davranışdan fərqli sensor pəncərəsi</h3>
    <p><strong>Qərarın izahı:</strong> {event.explanation}</p>
    <dl className="ai-event-meta">
      <div><dt>SESSİYA ID</dt><dd>{event.run_id}</dd></div>
      <div><dt>MODEL VERSİYASI</dt><dd>{event.model_version}</dd></div>
      <div><dt>HADİSƏNİN BAŞLAMA VAXTI</dt><dd>{new Date(event.started_at).toLocaleString('az-AZ')}</dd></div>
      <div><dt>SON YENİLƏNMƏ</dt><dd>{new Date(event.updated_at).toLocaleString('az-AZ')}</dd></div>
      <div><dt>BİTMƏ</dt><dd>{event.ended_at ? new Date(event.ended_at).toLocaleString('az-AZ') : 'Davam edir'}</dd></div>
      <div><dt>SIRA ARALIĞI</dt><dd>#{event.window_start_sequence_number}–#{event.latest_sequence_number} · ilk # {event.start_sequence_number}</dd></div>
      <div><dt>ANOMALİYA BALI</dt><dd>{event.score.toFixed(4)}</dd></div>
      <div><dt>DƏYİŞƏN SENSORLAR</dt><dd>{event.affected_sensors.map(sensorName).join(', ')}</dd></div>
      <div><dt>XƏBƏRDARLIQ SƏVİYYƏSİ</dt><dd>Təsdiqlənmiş AI müşahidəsi</dd></div>
    </dl>
    <div className="ai-comparison"><strong>Normal baza ilə müqayisə</strong>
      <ul>{Object.entries(event.baseline_comparison).map(([key, value]) => <li key={key}>
        <span>{value.description}</span><span>Cari göstərici {value.observed.toFixed(3)} · normal göstərici {value.normal_mean.toFixed(3)}</span>
        <small>Normal vəziyyətdən fərq: {value.standardized_difference > 0 ? '+' : ''}{value.standardized_difference.toFixed(1)} standart yayılma</small>
      </li>)}</ul>
    </div>
  </li>
}

export function AIAlertsPage() {
  const location = useLocation()
  const { device, run, aiStatus, aiEvents, alerts, rejections, trust, state, sampleAgeSeconds } = useLiveTelemetry()
  useEffect(() => {
    if (location.hash && aiEvents.length) {
      document.getElementById(decodeURIComponent(location.hash.slice(1)))?.scrollIntoView({ block: 'start' })
    }
  }, [location.hash, aiEvents])
  const modelReady = aiStatus?.model_status === 'READY'
  const collecting = modelReady && !!device?.run_id && (aiStatus?.accepted_window_count ?? 0) < (aiStatus?.window_seconds ?? 20)
  const modelLabel = !aiStatus || aiStatus.model_status === 'PREPARING' ? 'Hazırlanır' :
    aiStatus.model_status === 'NOT_TRAINED' || aiStatus.model_status === 'ERROR' ? 'AI hazır deyil' :
      collecting ? 'Model məlumat toplayır' : 'Model hazırdır'
  const qualityWarning = device?.status === 'RUNNING' && (state === 'stale' || state === 'disconnected')
  const sortedEvents = [...aiEvents].sort((a, b) => b.start_sequence_number - a.start_sequence_number)

  return <main id="main-content" className="main-content ai-page">
    <div className="page-crumb">ORBITRA <span>/</span> ANALİZ VƏ XƏBƏRDARLIQLAR</div>
    <div className="ai-heading"><div><p className="eyebrow">İŞ SAHƏSİ <span>03 / 07 · SENTINEL</span></p>
      <h1>AI Analizi və Xəbərdarlıqlar</h1><p className="page-description">Qəbul edilmiş telemetriyanın öyrənilmiş normal davranışla müqayisəsi. Model yalnız müşahidə və xəbərdarlıq yaradır.</p></div></div>

    <section className="ai-model-strip" aria-label="AI modelinin vəziyyəti">
      <div className="ai-model-icon"><BrainCircuit size={27} strokeWidth={1.4} aria-hidden="true" /></div>
      <div className="ai-model-description"><span>LOKAL MODEL VƏZİYYƏTİ</span><strong>{modelLabel}</strong><p>{aiStatus?.message ?? 'Backend-dən model vəziyyəti gözlənilir.'}</p></div>
      <div className="ai-model-meta"><span>MODEL VERSİYASI</span><strong>{aiStatus?.model_version ?? '—'}</strong><span>PƏNCƏRƏ</span><strong>{aiStatus?.accepted_window_count ?? 0}/{aiStatus?.window_seconds ?? 20} qəbul edilmiş saniyə</strong></div>
    </section>

    <div className="ai-summary-grid">
      <section className="ai-summary-card"><span className="ai-source-tag">AI ANALİZİ</span><h2>Son anomaliya balı</h2>
        {aiStatus?.latest_score != null ? <><strong className="ai-score">{aiStatus.latest_score.toFixed(4)}</strong>
          <p>Kalibrasiya həddi {aiStatus.threshold?.toFixed(4)} · nümunə #{aiStatus.latest_sequence_number} · {aiStatus.last_evaluated_at ? new Date(aiStatus.last_evaluated_at).toLocaleTimeString('az-AZ') : '—'}</p>
          {state === 'disconnected' || state === 'stale' || state === 'ended' ? <p className="ai-data-note">Bu, son saxlanmış qiymətləndirmədir; canlı məlumat deyil.</p> : null}</> :
          <div className="ai-no-score">{modelReady ? device?.run_id ? '20 ardıcıl qəbul edilmiş nümunə gözlənilir. Saxta bal göstərilmir.' : 'Sessiya başladıqda ilk 20 qəbul edilmiş nümunə toplanacaq.' : 'Model hazır olmadığından bal yoxdur.'}</div>}
        <p className="ai-score-note">Bal nasazlıq ehtimalı və ya əminlik faizi deyil; normal davranışdan fərqlilik göstəricisidir.</p>
      </section>
      <section className="ai-summary-card"><span className="ai-source-tag">CARİ SESSİYA</span><h2>Qiymətləndirmə konteksti</h2>
        <dl><div><dt>SESSİYA ID</dt><dd>{device?.run_id ?? 'Aktiv sessiya yoxdur'}</dd></div>
          <div><dt>SSENARİ</dt><dd>{scenarioName(run?.scenario ?? device?.scenario)}</dd></div>
          <div><dt>AI HADİSƏSİ</dt><dd>{aiEvents.filter(event => event.status === 'ACTIVE').length} aktiv · {aiEvents.length} saxlanmış</dd></div>
          <div><dt>SENTINEL QƏRARI</dt><dd>{verdictName(trust?.latest?.final_verdict)}</dd></div></dl>
        <p>AI girişinə ssenari adı verilmir; burada yalnız operator üçün göstərilir.</p>
        {trust?.latest_accepted?.explanation && <p><strong>Sentinel səbəb izahı:</strong> {displayModelTerm(trust.latest_accepted.explanation)}</p>}
      </section>
    </div>

    <section className="ai-sources" aria-label="Xəbərdarlıq mənbələri">
      <h2>Xəbərdarlıq mənbələri</h2>
      <div className="ai-source-grid">
        <div className="ai-source-card"><AlertTriangle size={18} aria-hidden="true" /><strong>Qayda</strong><p>{alerts.length === 0 ? 'Cari sessiyada qayda xəbərdarlığı yoxdur.' : `${alerts.length} qayda qeydi. ${alerts.filter(alert => alert.status === 'ACTIVE').length} aktiv.`}</p>
          {alerts.map(alert => <small key={alert.alert_id}>{alert.reason} · {sensorName(alert.metric_key)} {alert.metric_value.toFixed(2)} · {stateName(alert.status)}</small>)}</div>
        <div className="ai-source-card"><BrainCircuit size={18} aria-hidden="true" /><strong>AI analizi</strong><p>{aiEvents.length ? `${aiEvents.length} davamlı anomaliya hadisəsi saxlanıb.` : 'Təsdiqlənmiş AI anomaliya hadisəsi yoxdur.'}</p></div>
        <div className="ai-source-card"><DatabaseZap size={18} aria-hidden="true" /><strong>Məlumat keyfiyyəti</strong>
          <p>{qualityWarning ? `Aktiv sınaqda yeni qəbul edilmiş məlumat təsdiqlənmir${sampleAgeSeconds != null ? `; son nümunə ${sampleAgeSeconds} saniyə əvvəl gəlib` : ''}.` : state === 'paused' ? 'Dayandırılmış sınaqda yeni nümunə gözlənilmir; bu rabitə xətası deyil.' : 'Cari bağlantıda məlumat kəsilməsi xəbərdarlığı yoxdur.'}</p></div>
        <div className="ai-source-card"><ShieldAlert size={18} aria-hidden="true" /><strong>Təhlükəsizlik yoxlaması</strong><p>{rejections.length ? `${rejections.length} paket rəddi ayrıca qeydə alınıb; AI girişinə daxil deyil.` : 'Cari sessiyada rədd edilmiş paket yoxdur.'}</p>
          {rejections.length > 0 && <Link to="/security">Təhlükəsizlik Mərkəzində bax →</Link>}</div>
      </div>
    </section>

    <section className="ai-timeline" aria-labelledby="ai-timeline-title"><div className="ai-section-heading"><div><p className="eyebrow">SQLITE HADİSƏLƏRİ</p><h2 id="ai-timeline-title">AI hadisələrinin zaman xətti</h2></div><span>{aiEvents.length} hadisə · yalnız cari sessiya</span></div>
      {sortedEvents.length ? <ul>{sortedEvents.map(event => <AIEventCard key={event.event_id} event={event} />)}</ul> :
        <div className="ai-empty"><ShieldCheck size={19} aria-hidden="true" /><p>{collecting ? 'Model məlumat toplayır. Yetərli ardıcıl qəbul edilmiş pəncərə hələ yoxdur.' : modelReady ? 'Bu sessiyada təsdiqlənmiş AI anomaliya hadisəsi yoxdur.' : 'Model hazır olanda qəbul edilmiş telemetriya burada qiymətləndiriləcək.'}</p></div>}
    </section>
    <p className="device-footer">AI nəticələri qəbul edilmiş tədris telemetriyasına əsaslanır; avtomatik idarəetmə əmri verilmir.</p>
  </main>
}

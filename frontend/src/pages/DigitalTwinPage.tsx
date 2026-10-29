import { useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, Battery, CircleHelp, Cpu, Radio, ShieldCheck, Thermometer, Gauge, RadioTower, type LucideIcon } from 'lucide-react'
import { useLiveTelemetry } from '../lib/useLiveTelemetry'
import { assessSubsystems, type HealthStatus, type SubsystemKey, type SubsystemView } from '../lib/subsystems'
import { RocketSystemDiagram } from '../components/RocketSystemDiagram'
import { rocketBlocks } from '../lib/rocketSystem'
import { scenarioName, stateName } from '../lib/labels'
import './digital-twin.css'

type TwinKey = SubsystemKey | 'sensors' | 'payload'
type TwinBlock = Omit<SubsystemView, 'key'> & { key: TwinKey }
const icons: Record<TwinKey, LucideIcon> = { energy: Battery, thermal: Thermometer, communications: Radio, computer: Cpu, sensors: Gauge, payload: RadioTower }
const stateIcons: Record<HealthStatus, LucideIcon> = { NORMAL: ShieldCheck, WARNING: AlertTriangle, CRITICAL: AlertTriangle, UNKNOWN: CircleHelp }
const relatedSensors: Record<TwinKey, string[]> = {
  energy: ['battery_level_percent', 'voltage_v', 'current_a'],
  thermal: ['temperature_1_c', 'temperature_2_c', 'temperature_3_c'],
  communications: ['signal_strength_percent', 'communication_latency_ms', 'packet_loss_percent'],
  computer: ['cpu_load_percent', 'memory_usage_percent'],
  sensors: ['temperature_1_c', 'temperature_2_c', 'temperature_3_c'],
  payload: ['cpu_load_percent'],
}

export function DigitalTwinPage() {
  const { device, run, latestSample, alerts, aiEvents, rejections, trust, state, sampleAgeSeconds } = useLiveTelemetry()
  const [selected, setSelected] = useState<TwinKey>('energy')
  const trusted = state === 'live' || state === 'paused'
  const health = assessSubsystems(latestSample, alerts, trusted, trust?.latest_accepted?.final_verdict)
  const diagramBlocks = rocketBlocks(latestSample, health, trusted, trust?.latest_accepted?.final_verdict)
  const sensors = latestSample?.sensors
  const extraBlocks: TwinBlock[] = [
    { key: 'sensors', name: 'Sensorlar', status: diagramBlocks[0].status,
      readings: [{ label: 'Temperatur sensoru 1', value: trusted && sensors ? `${sensors.temperature_1_c.toFixed(2)} °C` : '—' },
        { label: 'Temperatur sensoru 2', value: trusted && sensors ? `${sensors.temperature_2_c.toFixed(2)} °C` : '—' },
        { label: 'Temperatur sensoru 3', value: trusted && sensors ? `${sensors.temperature_3_c.toFixed(2)} °C` : '—' }], alertIds: [] },
    { key: 'payload', name: 'Virtual faydalı yük', status: diagramBlocks[5].status,
      readings: [{ label: 'CPU yükü əsasında virtual yük', value: trusted && sensors ? `${sensors.cpu_load_percent.toFixed(1)} %` : '—' }], alertIds: [] },
  ]
  const blocks: TwinBlock[] = [...health, ...extraBlocks]
  const detail = blocks.find(item => item.key === selected) ?? blocks[0]
  const invalidFor = (key: TwinKey) => (trust?.untrusted_blocks ?? []).includes(key) ||
    (key === 'sensors' && (trust?.untrusted_blocks ?? []).includes('thermal'))
  const selectedAlerts = alerts.filter(item => relatedSensors[selected].includes(item.metric_key))
  const selectedAI = aiEvents.filter(item => item.affected_sensors.some(sensor => relatedSensors[selected].includes(sensor)))
  const sampleTime = latestSample ? new Date(latestSample.sample_time).toLocaleString('az-AZ') : '—'
  const modeNote = state === 'paused' ? 'Simulyasiya istifadəçi tərəfindən dayandırılıb; yeni nümunə gözlənilmir.'
    : state === 'stale' || state === 'disconnected' ? `Son etibarlı məlumat köhnəlib${sampleAgeSeconds === null ? '' : ` (${sampleAgeSeconds} saniyə)`}; cari vəziyyət təsdiqlənmir.`
      : state === 'ended' ? 'Sessiya bitib. Ölçmələr tarixidir, cari vəziyyət təsdiqlənmir.'
        : state === 'live' ? 'Yalnız backend-in qəbul etdiyi son imzalı nümunə göstərilir.'
          : 'Qəbul edilmiş canlı nümunə gözlənilir.'
  return <main id="main-content" className="main-content twin-page">
    <div className="page-crumb">ORBITRA <span>/</span> RƏQƏMSAL MODEL</div>
    <div className="twin-heading"><div><p className="eyebrow">İŞ SAHƏSİ <span>05 / 07 · SENTINEL</span></p><h1>Rəqəmsal Model</h1>
      <p className="page-description">Virtual raket bort sistemlərinin real vaxt vəziyyət modeli</p></div></div>
    <section className={`twin-context twin-context-${state}`} role={state === 'stale' || state === 'disconnected' ? 'alert' : 'status'}>
      <div><strong>{state === 'live' ? 'CANLI' : state === 'paused' ? 'DAYANDIRILIB' : state === 'ended' ? 'BİTİB' : 'MƏLUMAT YOXDUR'}</strong><span>{modeNote}</span></div>
      <div className="twin-run"><span>SESSİYA ID</span><strong data-testid="twin-run-id">{device?.run_id ?? 'Sessiya yoxdur'}</strong><span>{scenarioName(run?.scenario)}</span></div>
    </section>
    <section className="twin-data-trust"><strong>MƏLUMAT ETİBARLILIĞI</strong><span>{stateName(trusted ? trust?.status ?? 'NO DATA' : 'NO TRUSTED DATA')}</span>
      <p>{trust?.latest_accepted?.final_verdict === 'PROBABLE SENSOR FAULT' ? 'Temperatur 1 ayrıca sensor xəbərdarlığıdır; istilik bloku sübutsuz kritik sayılmır.' : 'Yalnız qəbul edilmiş paketlər alt-sistem vəziyyətini dəyişir.'}</p>
      <Link to="/telemetry-trust">Sentinel sübutlarına bax →</Link></section>
    <div className="twin-layout">
      <section className="twin-map" aria-label="Altı virtual raket bloku">
        <RocketSystemDiagram blocks={diagramBlocks} />
        <div className="twin-card-grid">{blocks.map(item => { const Icon = icons[item.key], StateIcon = stateIcons[item.status]; return <div className="twin-card-shell" key={item.key}><button type="button" onClick={() => setSelected(item.key)} aria-pressed={selected === item.key} className={`twin-card twin-${item.status.toLowerCase()} ${selected === item.key ? 'selected' : ''}`}>
          <span className="twin-card-heading"><Icon size={21} aria-hidden="true" /><strong>{item.name}</strong></span>
          <span className="twin-card-status"><StateIcon size={16} aria-hidden="true" /> {stateName(item.status)}</span>
          {invalidFor(item.key) && <span className="twin-card-data-invalid">Gələn məlumat etibarsızdır · son rədd edilmiş sınaq paketi</span>}
          {!trusted && <span className="twin-card-data-unknown">Cari məlumat köhnəlib və ya naməlumdur</span>}
          <span className="twin-card-readings">{item.readings.map(reading => <span key={reading.label}>{reading.label} <b>{reading.value}</b></span>)}</span>
          <small>Son etibarlı ölçmə: {sampleTime}</small>
          {item.alertIds.length > 0 && <span className="twin-card-alert">{item.alertIds.length} aktiv qayda xəbərdarlığı</span>}
        </button>{item.alertIds.length > 0 && <Link className="twin-card-alert-link" to="/mission-control#active-alerts-title">Xəbərdarlığa keç →</Link>}</div> })}</div>
      </section>
      <aside className="twin-detail" aria-live="polite"><p className="eyebrow">ALT-SİSTEM DETALI</p><h2>{detail.name}</h2><div className={`twin-detail-status twin-${detail.status.toLowerCase()}`}>{stateName(detail.status)}</div>
        <p className="twin-detail-note">{modeNote}</p>{invalidFor(selected) && <p className="twin-sensor-note">Gələn məlumat etibarsızdır. Bu, fiziki blokun xarab olduğunu göstərmir; fiziki vəziyyət yalnız son qəbul edilmiş nümunədən hesablanır.</p>}{(selected === 'thermal' || selected === 'sensors') && trust?.latest_accepted?.final_verdict === 'PROBABLE SENSOR FAULT' && <p className="twin-sensor-note">Temperatur sensoru 1 digər kanallar və Rəqəmsal Model ilə fərqlənir. Sensoru yoxlayın.</p>}<dl>{detail.readings.map(reading => <div key={reading.label}><dt>{reading.label}</dt><dd>{reading.value}</dd></div>)}<div><dt>Nümunə vaxtı</dt><dd>{sampleTime}</dd></div></dl>
        <h3>Əlaqəli hadisələr</h3>{selectedAlerts.length === 0 && selectedAI.length === 0 ? <p className="twin-detail-note">Bu alt-sistem üçün saxlanmış qayda və AI hadisəsi yoxdur.</p> : <ul>
          {selectedAlerts.map(item => <li key={item.alert_id}>Qayda · {item.reason} · {stateName(item.status)} · {new Date(item.opened_at).toLocaleString('az-AZ')}</li>)}
          {selectedAI.map(item => <li key={item.event_id}>AI analizi · {item.explanation} · {stateName(item.status)}</li>)}
        </ul>}
        {detail.alertIds.length > 0 && <Link to="/mission-control#active-alerts-title">Aktiv xəbərdarlığa keç →</Link>}
        {rejections.length > 0 && <p className="twin-detail-note">{rejections.length} rədd edilmiş paket etibarlı ölçməyə daxil edilməyib. <Link to="/security">Təhlükəsizlik qeydlərinə bax →</Link></p>}
      </aside>
    </div>
    <p className="device-footer">Yalnız qəbul edilmiş telemetriya · sadələşdirilmiş tədris qaydaları</p>
  </main>
}

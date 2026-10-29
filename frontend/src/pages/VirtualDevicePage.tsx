import { useRef, useState } from 'react'
import { Activity, Battery, Cpu, Pause, Play, Radio, RotateCcw, Square, Thermometer, type LucideIcon } from 'lucide-react'
import {
  ApiRequestError,
  type DeviceAction, type DeviceStatus, type ScenarioName, type SensorReadings,
  type SubsystemStatus, type VirtualDeviceSnapshot,
} from '../lib/api'
import { useLiveTelemetry } from '../lib/useVirtualDeviceTelemetry'
import { useAuth } from '../lib/AuthContext'
import { ScenarioPicker } from '../components/ScenarioPicker'
import { RocketSystemDiagram } from '../components/RocketSystemDiagram'
import { projectDescription, projectTagline, stateName } from '../lib/labels'
import { assessSubsystems } from '../lib/subsystems'
import { rocketBlocks } from '../lib/rocketSystem'
import './virtual-device.css'

const statusText: Record<DeviceStatus, string> = {
  IDLE: 'Başlanmayıb', RUNNING: 'İşləyir', PAUSED: 'Dayandırılıb', ENDED: 'Bitirilib',
}
const modeText: Record<VirtualDeviceSnapshot['system_mode'], string> = {
  STANDBY: 'Gözləmə', NOMINAL: 'Normal', HOLD: 'Saxlama',
}

const controls: { action: DeviceAction; label: string; description: string; icon: LucideIcon; allowed: DeviceStatus[] }[] = [
  { action: 'start', label: 'Başlat', description: 'Yeni sınaq', icon: Play, allowed: ['IDLE', 'ENDED'] },
  { action: 'pause', label: 'Dayandır', description: 'Axını dondur', icon: Pause, allowed: ['RUNNING'] },
  { action: 'resume', label: 'Davam etdir', description: 'Eyni sessiya', icon: Play, allowed: ['PAUSED'] },
  { action: 'reset', label: 'Sıfırla', description: 'İlkin vəziyyət', icon: RotateCcw, allowed: ['IDLE', 'RUNNING', 'PAUSED', 'ENDED'] },
  { action: 'end', label: 'Bitir', description: 'Sessiyanı bağla', icon: Square, allowed: ['RUNNING', 'PAUSED'] },
  { action: 'reduce_processing_load', label: 'Yükü azalt', description: 'Virtual CPU yükü', icon: Cpu, allowed: ['RUNNING'] },
]

type SensorItem = { key: keyof SensorReadings; label: string; unit: string }
type SensorGroup = { name: string; icon: LucideIcon; statusKey: keyof VirtualDeviceSnapshot['subsystem_statuses']; items: SensorItem[] }

const sensorGroups: SensorGroup[] = [
  {
    name: 'Enerji bloku', icon: Battery, statusKey: 'power', items: [
      { key: 'battery_level_percent', label: 'Batareya səviyyəsi', unit: '%' },
      { key: 'voltage_v', label: 'Gərginlik', unit: 'V' },
      { key: 'current_a', label: 'Elektrik cərəyanı', unit: 'A' },
    ],
  },
  {
    name: 'İstilik nəzarət sistemi', icon: Thermometer, statusKey: 'thermal', items: [
      { key: 'temperature_1_c', label: 'Temperatur sensoru 1', unit: '°C' },
      { key: 'temperature_2_c', label: 'Temperatur sensoru 2', unit: '°C' },
      { key: 'temperature_3_c', label: 'Temperatur sensoru 3', unit: '°C' },
    ],
  },
  {
    name: 'Telemetriya və rabitə bloku', icon: Radio, statusKey: 'communications', items: [
      { key: 'signal_strength_percent', label: 'Siqnal gücü', unit: '%' },
      { key: 'communication_latency_ms', label: 'Gecikmə', unit: 'ms' },
      { key: 'packet_loss_percent', label: 'Paket itkisi', unit: '%' },
    ],
  },
  {
    name: 'Bort kompüteri', icon: Cpu, statusKey: 'computer', items: [
      { key: 'cpu_load_percent', label: 'CPU yükü', unit: '%' },
      { key: 'memory_usage_percent', label: 'Yaddaş istifadəsi', unit: '%' },
    ],
  },
]

function formatElapsed(total: number): string {
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const seconds = total % 60
  return [hours, minutes, seconds].map(value => String(value).padStart(2, '0')).join(':')
}

function stateClass(status: SubsystemStatus): string {
  return `state-${status.toLowerCase()}`
}

export function VirtualDevicePage() {
  const { identity } = useAuth()
  const canOperate = identity?.role === 'VIRTUAL'
  const { device: snapshot, latestSample, alerts, trust, state, sampleAgeSeconds, command, deliveries } = useLiveTelemetry()
  const [pending, setPending] = useState<DeviceAction | null>(null)
  const [selectedScenario, setSelectedScenario] = useState<ScenarioName>('NORMAL_MISSION')
  const [actionError, setActionError] = useState<string | null>(null)
  const busyRef = useRef(false)
  const trusted = state === 'live' || state === 'paused'
  const health = assessSubsystems(latestSample, alerts, trusted, trust?.latest_accepted?.final_verdict)
  const blocks = rocketBlocks(latestSample, health, trusted, trust?.latest_accepted?.final_verdict)

  const performAction = async (action: DeviceAction) => {
    if (busyRef.current || !canOperate || !snapshot || state === 'connecting' || state === 'disconnected' || state === 'stale') return
    busyRef.current = true
    setPending(action)
    setActionError(null)
    try {
      await command(action, action === 'start' ? selectedScenario : undefined)
    } catch (error) {
      if (error instanceof ApiRequestError && error.status === 409) {
        setActionError(error.message)
      } else {
        setActionError(error instanceof Error ? error.message : 'Əməliyyat yerinə yetirilmədi.')
      }
    } finally {
      busyRef.current = false
      setPending(null)
    }
  }

  return (
    <main id="main-content" className="main-content device-page">
      <div className="page-crumb">ORBITRA <span>/</span> VİRTUAL RAKET SİSTEMİ</div>
      <div className="device-heading">
        <div>
          <p className="eyebrow">İŞ SAHƏSİ <span>01 / 01 · DEVICE</span></p>
          <h1>Virtual Raket Sistemi</h1>
          <p className="page-description">Raketin bort elektronikasının və sensorlarının virtual sınaq modeli</p>
        </div>
      </div>

      {snapshot && <ScenarioPicker value={selectedScenario} onChange={setSelectedScenario}
        locked={!canOperate || snapshot.status === 'RUNNING' || snapshot.status === 'PAUSED'} current={snapshot.scenario}
        status={snapshot.status} onStart={() => void performAction('start')} startBusy={pending === 'start'}
        disabledReason={!canOperate ? 'Bu hesab ssenari seçə bilmir.' : undefined} />}

      {state === 'connecting' && <div className="device-notice" role="status">Canlı telemetriya bağlantısı qurulur…</div>}
      {state === 'disconnected' && (
        <div className="device-notice device-notice-error" role="alert">
          <strong>Virtual raket modeli ilə əlaqə yoxdur.</strong>
          <span>Son göstəricilər gizlədilib. Backend serverini yoxlayın. Bağlantı avtomatik bərpa olunacaq.</span>
        </div>
      )}

      {snapshot && state !== 'connecting' && state !== 'disconnected' && (
        <>
          <div className={`device-live-strip live-${state}`} role="status">
            <span className="live-dot" />
            <strong>{state === 'paused' ? 'Simulyasiya istifadəçi tərəfindən dayandırılıb' : state === 'ended' ? 'Missiya bitirilib' : state === 'stale' ? 'Məlumat köhnəlib' : state === 'no_data' ? 'Məlumat hələ yoxdur' : 'Canlı bağlantı var'}</strong>
            {state === 'stale' && <span>Son nümunə {sampleAgeSeconds} saniyə əvvəl alınıb.</span>}
            {latestSample && <span className="live-sequence">NÜMUNƏ #{latestSample.sequence_number} · {new Date(latestSample.sample_time).toLocaleTimeString('az-AZ')}</span>}
          </div>
          <div className="device-summary" aria-label="Simulyasiya vəziyyəti">
            <div className="summary-item"><span>VƏZİYYƏT</span><strong className={`summary-status ${stateClass(snapshot.subsystem_statuses.power)}`}><i />{statusText[snapshot.status]}</strong></div>
            <div className="summary-item"><span>SİSTEM REJİMİ</span><strong>{modeText[snapshot.system_mode]}</strong></div>
            <div className="summary-item"><span>SINAQ VAXTI</span><strong className="summary-time" data-testid="simulation-time">{formatElapsed(snapshot.simulation_elapsed_seconds)}</strong></div>
            <div className="summary-item summary-run"><span>SESSİYA ID</span><strong title={snapshot.run_id ?? undefined}>{snapshot.run_id ?? 'Sessiya yoxdur'}</strong></div>
          </div>

          <section className="device-control-panel" aria-label="Virtual raket sistemi əməliyyatları">
            <div className="control-description"><span>İDARƏETMƏ</span><p>{canOperate ? 'Əməliyyatlar backend vəziyyətinə tətbiq olunur.' : 'Bu rol idarəetmə əməliyyatları edə bilməz.'}</p></div>
            <div className="device-controls">
              {controls.map(({ action, label, description, icon: Icon, allowed }) => (
                <button
                  key={action}
                  type="button"
                  className={`device-button ${action === 'start' || action === 'resume' ? 'device-button-primary' : ''}`}
                  disabled={!canOperate || pending !== null || state === 'stale' || !allowed.includes(snapshot.status)}
                  onClick={() => void performAction(action)}
                  aria-label={`${label} — ${description}`}
                >
                  <Icon size={17} strokeWidth={1.7} aria-hidden="true" />
                  <span><strong>{pending === action ? 'İcra edilir…' : label}</strong><small>{description}</small></span>
                </button>
              ))}
            </div>
          </section>

          {actionError && <div className="device-action-error" role="alert">{actionError}</div>}

          {state === 'stale' && <div className="device-notice device-notice-error" role="alert">Son alt-sistem və sensor vəziyyəti köhnəlib. Yeni saxlanmış nümunə gözlənilir.</div>}
          <div className="device-top-grid">
            <section className="craft-panel" aria-labelledby="craft-title">
              <div className="device-panel-header"><h2 id="craft-title">Virtual raket sxemi</h2><span>2D TEXNİKİ GÖRÜNÜŞ</span></div>
              <RocketSystemDiagram blocks={blocks} />
              <p>Rənglər cihazın yaratdığı lokal sensor oxunuşlarına əsaslanır; Main qəbulunu aşağıdakı göndəriş tarixçəsində yoxlayın.</p>
            </section>
            <section className="subsystems-panel" aria-labelledby="subsystems-title">
              <div className="device-panel-header"><h2 id="subsystems-title">Bort sistemləri</h2><span>06 VİRTUAL BLOK</span></div>
              <div className="subsystem-grid">
                {blocks.map(block => <div className="subsystem-card" key={block.id}>
                  <div><h3>{block.name}</h3><span className={`subsystem-state state-${block.status.toLowerCase()}`}><i />{stateName(block.status)}</span><p>{block.reading}</p></div>
                </div>)}
              </div>
            </section>
          </div>

          {state !== 'stale' && latestSample && <section className="sensor-section" aria-labelledby="sensors-title">
            <div className="sensor-section-heading"><div><p className="eyebrow">BACKEND MODELİ</p><h2 id="sensors-title">Sensor oxunuşları</h2></div><span>11 SİNTETİK GÖSTƏRİCİ</span></div>
            <div className="sensor-grid">
              {sensorGroups.map(({ name, icon: Icon, items }) => <div className="sensor-card" key={name}>
                <h3><Icon size={17} strokeWidth={1.6} aria-hidden="true" />{name}</h3>
                {items.map(({ key, label, unit }) => <div className="sensor-row" key={key}>
                  <span>{label}</span><strong data-sensor={key}>{latestSample.sensors[key].toFixed(2)} <small>{unit}</small></strong>
                </div>)}
              </div>)}
            </div>
            <p className="sensor-note"><Activity size={15} aria-hidden="true" /> Dəyərlər yalnız tədris modeli üçündür. Təsdiqlənmiş mühəndislik hədləri kimi istifadə edilməməlidir.</p>
          </section>}
          <section className="device-about" aria-label="Telemetriya yoxlaması">
            <h2>Telemetriya yoxlaması</h2>
            <p>Buradakı sensor dəyəri cihazda yaranır. Sistem yalnız yoxlamadan keçən paketləri qrafikə əlavə edir.</p>
            <p>Monitorinq ekranı administrator hesabı ilə eyni sistemdə açılır.</p>
            <ul>{deliveries.slice(0, 8).map(item => <li key={item.id}>
              {item.kind === 'packet' ? 'Paket' : 'Əmr'} #{item.sequence_number ?? '—'} · {item.result}
              {item.reason_code ? ' · ' + item.reason_code : ''}
            </li>)}</ul>
            <h3>Son rədd edilmiş cəhdlər</h3>
            <ul>{deliveries.filter(item => item.result === 'REJECTED').slice(0, 3).map(item => <li key={'rejected-' + item.id}>
              Paket #{item.sequence_number ?? '—'} · {item.reason_code ?? 'RƏDD EDİLDİ'}
            </li>)}</ul>
          </section>
          <section className="device-about" aria-labelledby="about-title"><h2 id="about-title">Layihə haqqında</h2><p>{projectDescription}</p><strong>{projectTagline}</strong>
            <p>ORBITRA-nın tədris dizaynı NASA-nın <a href="https://nasa.github.io/openmct/documentation/" target="_blank" rel="noopener noreferrer">Open MCT</a>, <a href="https://github.com/nasa/cFS" target="_blank" rel="noopener noreferrer">cFS</a>, <a href="https://fprime.jpl.nasa.gov/latest/docs/getting-started/" target="_blank" rel="noopener noreferrer">F´</a> və <a href="https://www.nasa.gov/goddard/gmsec/" target="_blank" rel="noopener noreferrer">GMSEC</a> açıq yanaşmalarından, həmçinin ESA-nın <a href="https://technology.esa.int/page/virtual-shaker" target="_blank" rel="noopener noreferrer">virtual sınaq yanaşmasından</a> ilhamlanır. ORBITRA həmin qurumların məhsulu və ya təsdiqlədiyi sistem deyil.</p>
            <small>Heç bir real raketə qoşulmayıb. Virtual faydalı yük CPU göstəricisi ilə təmsil olunur.</small></section>
          <p className="device-footer">{latestSample ? `Yaradılmış nümunə: ${new Date(latestSample.sample_time).toLocaleString('az-AZ')}` : 'Saxlanmış nümunə yoxdur'} <span>Simulyasiya vaxtı yalnız serverdə hesablanır.</span></p>
        </>
      )}
    </main>
  )
}

import type { DeviceStatus, ScenarioName } from '../lib/api'
import { deviceStatusNames, scenarioName } from '../lib/labels'
import './scenario-picker.css'

export const scenarioDescriptions: Record<ScenarioName, { purpose: string; change: string; response: string }> = {
  NORMAL_MISSION: { purpose: 'Normal telemetriya axınını göstərmək', change: 'Sensorlar kiçik addımlarla dəyişir.', response: 'Sistemlər normal, Sentinel qərarı etibarlı qalır.' },
  TEMPERATURE_ANOMALY: { purpose: 'Əlaqəli istilik artımını yoxlamaq', change: 'Virtual yük, cərəyan və üç temperatur artır.', response: 'Sentinel sistem anomaliyasını, AI qeyri-adi davranışı göstərir.' },
  INVALID_TELEMETRY: { purpose: 'Format qapısını yoxlamaq', change: 'Onuncu paket yanlış sxem versiyası daşıyır.', response: 'Paket karantinə düşür, qrafik və AI-yə daxil olmur.' },
  SINGLE_SENSOR_FAULT: { purpose: 'Tək sensor xətasını ayırmaq', change: 'Yalnız temperatur sensoru 1 kəskin yüksəlir.', response: 'Sentinel sensor nasazlığı göstərir, bütün istilik bloku kritik olmur.' },
  INVALID_SIGNATURE: { purpose: 'İmza bütövlüyünü yoxlamaq', change: 'Onuncu paket imzalandıqdan sonra temperatur dəyəri dəyişdirilir.', response: 'Paket karantinə alınır və təhlükəsizlik hadisəsi açılır.' },
  REPLAYED_TELEMETRY: { purpose: 'Təkrar paketi aşkarlamaq', change: 'Əvvəlki imzalı paket yenidən göndərilir.', response: 'Sentinel təkrar paketi rədd edir və hadisə qeydə alınır.' },
  SPOOFED_TELEMETRY: { purpose: 'İcazəsiz virtual mənbəni yoxlamaq', change: 'Onuncu paket qeydiyyatsız virtual mənbə adı ilə göndərilir.', response: 'Mənbə yoxlaması paketi rədd edir və hadisə qeydə alınır.' },
}

const cyberScenarios: ScenarioName[] = ['REPLAYED_TELEMETRY', 'SPOOFED_TELEMETRY', 'INVALID_SIGNATURE']
const regularScenarios: ScenarioName[] = ['NORMAL_MISSION', 'TEMPERATURE_ANOMALY', 'INVALID_TELEMETRY', 'SINGLE_SENSOR_FAULT']

export function ScenarioPicker({ value, onChange, locked, current, status, onStart, startBusy, disabledReason }: {
  value: ScenarioName; onChange: (scenario: ScenarioName) => void; locked: boolean
  current: ScenarioName | null; status: DeviceStatus; onStart: () => void; startBusy: boolean
  disabledReason?: string
}) {
  const shown = locked ? current ?? value : value
  const details = scenarioDescriptions[shown]
  const cyberSelected = cyberScenarios.includes(shown)
  const canStart = !locked && (status === 'IDLE' || status === 'ENDED') && !startBusy
  return <section className="scenario-picker" aria-label="Sınaq ssenarisi">
    <div className="scenario-summary"><span className="scenario-kicker">SINAQ SSENARİSİ</span>
      <strong>{cyberSelected ? 'Kiberhücum simulyasiyası' : scenarioName(shown)}</strong><p>{cyberSelected ? `${scenarioName(shown)} · ` : ''}{details.purpose}</p>
      <div className="scenario-evidence"><span><b>Gözlənilən dəyişiklik</b>{details.change}</span><span><b>Sistemin reaksiyası</b>{details.response}</span></div>
    </div>
    <div className="scenario-actions"><label>Ssenari seç
      <select aria-label="Ssenari seç" value={cyberSelected ? 'CYBER_SIMULATION' : shown} disabled={locked}
        onChange={event => onChange(event.target.value === 'CYBER_SIMULATION' ? 'REPLAYED_TELEMETRY' : event.target.value as ScenarioName)}>
        {regularScenarios.map(name => <option key={name} value={name}>{scenarioName(name)}</option>)}
        <option value="CYBER_SIMULATION">Kiberhücum simulyasiyası</option>
      </select></label>
      {cyberSelected && <label>Virtual test növü
        <select aria-label="Virtual test növü" value={shown} disabled={locked}
          onChange={event => onChange(event.target.value as ScenarioName)}>
          {cyberScenarios.map(name => <option key={name} value={name}>{scenarioName(name)}</option>)}
        </select>
      </label>}
      <button type="button" disabled={!canStart} onClick={onStart}>{startBusy ? 'Başladılır…' : 'Ssenarini başlat'}</button>
      <small>Hazırkı vəziyyət: {deviceStatusNames[status]}</small>
    </div>
    {locked && <small className="scenario-lock-note">{disabledReason ?? 'Cari sınaq bitdikdən və ya sıfırlandıqdan sonra yeni ssenari seçin.'}</small>}
    {!locked && current && <small className="scenario-lock-note">Son sınaq: {scenarioName(current)}. Yeni başlatma ayrıca sessiya yaradacaq.</small>}
  </section>
}

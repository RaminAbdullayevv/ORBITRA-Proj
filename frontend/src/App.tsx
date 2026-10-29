import { Navigate, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import { ConnectionStatus } from './components/ConnectionStatus'
import { pages } from './pages/pageData'
import { MissionControlPage } from './pages/MissionControlPage'
import { SecurityOperationsPage } from './pages/SecurityOperationsPage'
import { AIAlertsPage } from './pages/AIAlertsPage'
import { AuthProvider, useAuth } from './lib/AuthContext'
import { LoginPage } from './pages/LoginPage'
import { DigitalTwinPage } from './pages/DigitalTwinPage'
import { MissionReportPage } from './pages/MissionReportPage'
import { TelemetryTrustPage } from './pages/TelemetryTrustPage'
import { VirtualDevicePage } from './pages/VirtualDevicePage'
import { Radio } from 'lucide-react'

function BrandMark() {
  return <span className="brand-mark" aria-hidden="true"><span /></span>
}

function Sidebar({ virtual }: { virtual: boolean }) {
  const visible = virtual ? [{ path: '/virtual-device', title: 'Virtual Device', index: '01', icon: Radio }] : pages
  return <aside className="sidebar">
    <div className="sidebar-brand"><BrandMark /><div><strong>ORBITRA</strong><span>RAKET SİSTEMLƏRİ</span></div></div>
    <nav className="sidebar-nav" aria-label="Əsas menyu">
      <p className="nav-heading">İŞ SAHƏLƏRİ <span>01 — {String(visible.length).padStart(2, '0')}</span></p>
      {visible.map(({ path, title, icon: Icon, index }) =>
        <NavLink key={path} to={path} className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
          <Icon size={18} strokeWidth={1.7} aria-hidden="true" /><span>{title}</span><small>{index}</small>
        </NavLink>)}
    </nav>
    <div className="sidebar-foot"><div className="sidebar-foot-line"><span className="foot-indicator" /> SENTINEL</div>
      <p>{virtual ? 'Virtual sınaq cihazı' : 'Telemetriya etibarlılığı və səbəb təhlili'}</p></div>
  </aside>
}

const roleLabels = { ADMIN: 'Administrator', VIRTUAL: 'Virtual cihaz', OPERATOR: 'Operator', SECURITY_ANALYST: 'Təhlükəsizlik analitiki', OBSERVER: 'Müşahidəçi' }

function Forbidden() {
  return <main id="main-content" className="main-content"><h1>Girişə icazə yoxdur</h1>
    <p>Bu səhifə cari hesabınız üçün açıq deyil.</p></main>
}

function AppContent() {
  const { state, identity, signOut } = useAuth()
  const location = useLocation()
  if (state === 'loading') return <LoginPage />
  if (state !== 'authenticated' || !identity) return <>{location.pathname !== '/login' &&
    <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />}<LoginPage /></>
  const virtual = identity.role === 'VIRTUAL'
  const home = virtual ? '/virtual-device' : '/mission-control'
  return <div className="app-shell antialiased">
    <a className="skip-link" href="#main-content">Əsas məzmuna keç</a>
    <Sidebar virtual={virtual} />
    <div className="content-shell min-w-0">
      <header className="topbar">
        <div className="topbar-identity"><span className="topbar-name">{virtual ? 'VİRTUAL RAKET SİSTEMİ · CİHAZ' : 'RAKET SİSTEMLƏRİ · TELEMETRİYA MƏRKƏZİ'}</span>
          <span className="topbar-separator" aria-hidden="true" /><span className="simulation-badge">Virtual sınaq</span></div>
        <div className="topbar-user"><div><strong>{identity.username}</strong><span>{roleLabels[identity.role]}</span></div>
          <button type="button" onClick={() => void signOut()}>Çıxış</button><ConnectionStatus /></div>
      </header>
      <Routes>
        <Route path="/" element={<Navigate to={home} replace />} />
        <Route path="/login" element={<Navigate to={home} replace />} />
        <Route path="/virtual-device" element={virtual ? <VirtualDevicePage /> : <Forbidden />} />
        <Route path="/mission-control" element={virtual ? <Forbidden /> : <MissionControlPage />} />
        <Route path="/security" element={virtual ? <Forbidden /> : <SecurityOperationsPage />} />
        <Route path="/ai-alerts" element={virtual ? <Forbidden /> : <AIAlertsPage />} />
        <Route path="/digital-twin" element={virtual ? <Forbidden /> : <DigitalTwinPage />} />
        <Route path="/mission-report" element={virtual ? <Forbidden /> : <MissionReportPage />} />
        <Route path="/telemetry-trust" element={virtual ? <Forbidden /> : <TelemetryTrustPage />} />
        <Route path="*" element={<Navigate to={home} replace />} />
      </Routes>
    </div>
  </div>
}

export default function App() { return <AuthProvider><AppContent /></AuthProvider> }

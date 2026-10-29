import { Activity, BrainCircuit, FileText, RadioTower, Shield, ShieldCheck, type LucideIcon } from 'lucide-react'

export type PageData = { path: string; title: string; index: string; icon: LucideIcon }

export const pages: PageData[] = [
  { path: '/mission-control', title: 'Missiya İdarəetmə', index: '01', icon: Activity },
  { path: '/ai-alerts', title: 'AI Analizi və Xəbərdarlıqlar', index: '02', icon: BrainCircuit },
  { path: '/security', title: 'Təhlükəsizlik Mərkəzi', index: '03', icon: Shield },
  { path: '/digital-twin', title: 'Rəqəmsal Model', index: '04', icon: RadioTower },
  { path: '/mission-report', title: 'Missiya Hesabatı', index: '05', icon: FileText },
  { path: '/telemetry-trust', title: 'Telemetriya Etibarlılığı', index: '06', icon: ShieldCheck },
]

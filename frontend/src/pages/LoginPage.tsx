import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { LockKeyhole, ShieldCheck } from 'lucide-react'
import { ApiRequestError } from '../lib/api'
import { useAuth } from '../lib/AuthContext'
import { projectDescription, projectTagline } from '../lib/labels'
import './login.css'

export function LoginPage() {
  const { state, identity, signIn, retry } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  if (state === 'authenticated') return <Navigate to={identity?.role === 'VIRTUAL' ? '/virtual-device' : '/mission-control'} replace />

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setPending(true)
    setError(null)
    try {
      const identity = await signIn(username, password)
      setPassword('')
      navigate(identity.role === 'VIRTUAL' ? '/virtual-device' : '/mission-control', { replace: true })
    } catch (cause) {
      setError(cause instanceof ApiRequestError && cause.status === 401 ? 'İstifadəçi adı və ya şifrə yanlışdır' : cause instanceof ApiRequestError ? cause.message : 'Serverlə əlaqə qurulmadı. Bir qədər sonra yenidən yoxlayın.')
    } finally { setPending(false) }
  }

  return <main id="main-content" className="login-screen">
    <div className="login-brand"><span className="brand-mark" aria-hidden="true"><span /></span><div><strong>ORBITRA</strong><small>RAKET SİSTEMLƏRİ</small></div></div>
    <section className="login-card" aria-labelledby="login-title">
      <div className="login-icon"><LockKeyhole size={27} aria-hidden="true" /></div>
      <p className="eyebrow">ORBITRA · VİRTUAL SINAQ VƏ MONİTORİNQ</p>
      <h1 id="login-title">ORBITRA sisteminə giriş</h1>
      <p>Raket sistemləri üçün ağıllı telemetriya və virtual sınaq platforması</p>
      <p className="login-description">{projectDescription}</p>
      <p className="login-tagline">{projectTagline}</p>
      <form onSubmit={event => void submit(event)}>
        <label>İstifadəçi adı<input autoComplete="username" value={username} onChange={event => setUsername(event.target.value)} required /></label>
        <label>Şifrə<input type="password" autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)} required /></label>
        <button type="submit" disabled={pending || state === 'loading'}>{pending ? 'Yoxlanılır…' : 'Daxil ol'}</button>
      </form>
      {error && <p className="login-error" role="alert">{error}</p>}
      {state === 'unreachable' && <div className="login-offline" role="alert">Backend ilə əlaqə yoxdur. <button type="button" onClick={() => void retry()}>Yenidən yoxla</button></div>}
      {state === 'loading' && <p role="status">Sessiya yoxlanılır…</p>}
    </section>
    <div className="login-foot"><ShieldCheck size={15} aria-hidden="true" /> ORBITRA Sentinel <span>Virtual sınaq mühiti</span></div>
  </main>
}

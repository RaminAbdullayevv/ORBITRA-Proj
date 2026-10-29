import { useEffect, useState } from 'react'
import { checkBackend } from '../lib/api'

type ConnectionState = 'checking' | 'connected' | 'disconnected'

export function ConnectionStatus() {
  const [state, setState] = useState<ConnectionState>('checking')

  useEffect(() => {
    let mounted = true
    const check = async () => {
      try {
        const connected = await checkBackend()
        if (mounted) setState(connected ? 'connected' : 'disconnected')
      } catch {
        if (mounted) setState('disconnected')
      }
    }
    void check()
    const interval = window.setInterval(() => void check(), 5000)
    return () => {
      mounted = false
      window.clearInterval(interval)
    }
  }, [])

  const label = state === 'checking' ? 'Bağlantı yoxlanılır' : state === 'connected' ? 'Serverə qoşulub' : 'Serverlə əlaqə kəsilib'

  return (
    <div className="connection-wrap" role="status" aria-live="polite">
      <div className={`connection connection--${state}`}>
        <span className="connection-dot" aria-hidden="true" />
        <span>{label}</span>
      </div>
      {state === 'disconnected' && (
        <p className="connection-help">Lokal serveri işə salın: <code>uvicorn app.main:app --reload</code></p>
      )}
    </div>
  )
}

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { ApiRequestError, getIdentity, login as loginRequest, logout as logoutRequest, setCsrfToken, type Identity } from './api'

type AuthState = 'loading' | 'authenticated' | 'unauthenticated' | 'unreachable'
type AuthValue = {
  state: AuthState
  identity: Identity | null
  signIn: (username: string, password: string) => Promise<Identity>
  signOut: () => Promise<void>
  retry: () => Promise<void>
}

const AuthContext = createContext<AuthValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>('loading')
  const [identity, setIdentity] = useState<Identity | null>(null)

  const clear = () => { setCsrfToken(null); setIdentity(null); setState('unauthenticated') }
  const retry = async () => {
    setState('loading')
    try {
      const current = await getIdentity()
      setCsrfToken(current.csrf_token)
      setIdentity(current)
      setState('authenticated')
    } catch (error) {
      if (error instanceof ApiRequestError && error.status === 401) clear()
      else setState('unreachable')
    }
  }

  useEffect(() => {
    void retry()
    const onExpired = () => clear()
    const onFocus = () => { void retry() }
    window.addEventListener('orbitra-auth-expired', onExpired)
    window.addEventListener('focus', onFocus)
    return () => {
      window.removeEventListener('orbitra-auth-expired', onExpired)
      window.removeEventListener('focus', onFocus)
    }
  }, [])

  const signIn = async (username: string, password: string) => {
    const current = await loginRequest(username, password)
    setCsrfToken(current.csrf_token)
    setIdentity(current)
    setState('authenticated')
    return current
  }
  const signOut = async () => {
    await logoutRequest()
    clear()
  }

  return <AuthContext.Provider value={{ state, identity, signIn, signOut, retry }}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthValue {
  const context = useContext(AuthContext)
  if (!context) throw new Error('AuthProvider is missing')
  return context
}

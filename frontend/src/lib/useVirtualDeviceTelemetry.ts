import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  performVirtualDeviceAction, type DeviceAction, type RuleAlert, type ScenarioName,
  type TelemetrySample, type TrustOverview, type VirtualDeviceSnapshot,
} from './api'

export type LiveState = 'connecting' | 'live' | 'paused' | 'ended' | 'disconnected' | 'stale' | 'no_data'
export type Delivery = {
  id: number; kind: string; run_id: string | null; sequence_number: number | null;
  packet_id: string | null; sent_at: string; result: string;
  reason_code: string | null; detail: string | null
}
type DeviceState = { device: VirtualDeviceSnapshot; deliveries: Delivery[] }
const base = (import.meta.env.VITE_API_BASE_URL || '').replace(new RegExp('/$'), '')

function sample(snapshot: VirtualDeviceSnapshot | null): TelemetrySample | null {
  if (!snapshot?.run_id || snapshot.simulation_elapsed_seconds < 1) return null
  return {
    run_id: snapshot.run_id,
    sequence_number: snapshot.simulation_elapsed_seconds,
    simulation_elapsed_seconds: snapshot.simulation_elapsed_seconds,
    sample_time: snapshot.updated_at,
    status: snapshot.status,
    sensors: snapshot.sensors,
  }
}

export function useLiveTelemetry() {
  const [device, setDevice] = useState<VirtualDeviceSnapshot | null>(null)
  const [deliveries, setDeliveries] = useState<Delivery[]>([])
  const [transport, setTransport] = useState<'connecting' | 'live' | 'disconnected'>('connecting')
  const [clock, setClock] = useState(Date.now())
  const [lastFrame, setLastFrame] = useState(Date.now())
  const refresh = useCallback(async () => {
    const response = await fetch(base + '/api/v1/virtual-device/state', { credentials: 'include', cache: 'no-store' })
    if (response.status === 401) window.dispatchEvent(new Event('orbitra-auth-expired'))
    if (!response.ok) throw new Error('Device vəziyyəti oxunmadı.')
    const state = await response.json() as DeviceState
    setDevice(state.device)
    setDeliveries(state.deliveries)
    setLastFrame(Date.now())
  }, [])

  useEffect(() => {
    let active = true
    let socket: WebSocket | null = null
    let retry: number | undefined
    const clockTimer = window.setInterval(() => setClock(Date.now()), 1000)
    const connect = () => {
      if (!active) return
      const endpoint = new URL(base || window.location.origin, window.location.origin)
      endpoint.protocol = endpoint.protocol === 'https:' ? 'wss:' : 'ws:'
      const url = endpoint.origin + endpoint.pathname.replace(new RegExp('/$'), '') + '/api/v1/virtual-device/ws'
      socket = new WebSocket(url)
      socket.onopen = () => { if (active) setTransport('live') }
      socket.onmessage = event => {
        if (!active) return
        try {
          const state = JSON.parse(event.data) as { type: string } & DeviceState
          if (state.type === 'device_state') {
            setDevice(state.device)
            setDeliveries(state.deliveries)
            setLastFrame(Date.now())
          }
        } catch { /* Reconnect restores state. */ }
      }
      socket.onclose = event => {
        if (!active) return
        if (event.code === 1008) {
          window.dispatchEvent(new Event('orbitra-auth-expired'))
          return
        }
        setTransport('disconnected')
        retry = window.setTimeout(connect, 1500)
      }
      socket.onerror = () => socket?.close()
    }
    void refresh().finally(() => { if (active) connect() })
    return () => {
      active = false
      window.clearInterval(clockTimer)
      if (retry !== undefined) window.clearTimeout(retry)
      socket?.close()
    }
  }, [refresh])

  const latestSample = useMemo(() => sample(device), [device])
  const sampleAgeSeconds = latestSample ? Math.max(0, Math.floor((clock - Date.parse(latestSample.sample_time)) / 1000)) : null
  const state: LiveState = transport !== 'live' ? transport
    : clock - lastFrame > 7000 ? 'stale'
      : device?.status === 'PAUSED' ? 'paused'
        : device?.status === 'ENDED' ? 'ended'
          : !latestSample ? 'no_data' : 'live'
  const command = useCallback(async (action: DeviceAction, scenario?: ScenarioName) => {
    const result = await performVirtualDeviceAction(action, scenario)
    setDevice(result)
    await refresh()
    return result
  }, [refresh])
  return {
    device, latestSample, alerts: [] as RuleAlert[], trust: null as TrustOverview | null,
    state, sampleAgeSeconds, command, deliveries,
  }
}


import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  getOperatorEvents, getTelemetryHistory, getTelemetryState, performVirtualDeviceAction, telemetrySocketUrl,
  type AIEvent, type AIStatus, type DeviceAction, type OperatorEvent, type RejectedTelemetry, type RuleAlert, type RunSummary, type ScenarioName, type TelemetryEvent, type TelemetrySample, type TrustOverview, type VirtualDeviceSnapshot,
} from './api'

export type LiveState = 'connecting' | 'live' | 'paused' | 'ended' | 'disconnected' | 'stale' | 'no_data'

const HISTORY_SECONDS = 300
const STALE_AFTER_MS = 4500
const SOCKET_TIMEOUT_MS = 7500

function keepRecent(samples: TelemetrySample[]): TelemetrySample[] {
  const newest = samples[samples.length - 1]?.simulation_elapsed_seconds ?? 0
  return samples.filter(sample => sample.simulation_elapsed_seconds >= newest - HISTORY_SECONDS).slice(-HISTORY_SECONDS)
}

export function useLiveTelemetry() {
  const [device, setDevice] = useState<VirtualDeviceSnapshot | null>(null)
  const [run, setRun] = useState<RunSummary | null>(null)
  const [alerts, setAlerts] = useState<RuleAlert[]>([])
  const [rejections, setRejections] = useState<RejectedTelemetry[]>([])
  const [aiStatus, setAiStatus] = useState<AIStatus | null>(null)
  const [aiEvents, setAiEvents] = useState<AIEvent[]>([])
  const [trust, setTrust] = useState<TrustOverview | null>(null)
  const [samples, setSamples] = useState<TelemetrySample[]>([])
  const [events, setEvents] = useState<OperatorEvent[]>([])
  const [deviceLastSeenAt, setDeviceLastSeenAt] = useState<string | null>(null)
  const [transport, setTransport] = useState<'connecting' | 'live' | 'disconnected'>('connecting')
  const [clock, setClock] = useState(Date.now())
  const samplesRef = useRef<TelemetrySample[]>([])
  const eventsRef = useRef<OperatorEvent[]>([])
  const runRef = useRef<string | null>(null)
  const deviceRef = useRef<VirtualDeviceSnapshot | null>(null)
  const socketRef = useRef<WebSocket | null>(null)
  const trustIdRef = useRef(0)

  const acceptTrust = useCallback((incoming: TrustOverview) => {
    const id = incoming.latest?.id ?? 0
    if (id < trustIdRef.current) return
    trustIdRef.current = id
    setTrust(incoming)
  }, [])

  const replaceSamples = useCallback((next: TelemetrySample[]) => {
    samplesRef.current = next
    setSamples(next)
  }, [])

  const replaceEvents = useCallback((next: OperatorEvent[]) => {
    eventsRef.current = next
    setEvents(next)
  }, [])

  const ingestEvents = useCallback((incoming: OperatorEvent[]) => {
    const matching = incoming.filter(event => event.run_id === runRef.current)
    if (matching.length === 0) return
    const byId = new Map(eventsRef.current.map(event => [event.event_id, event]))
    for (const event of matching) byId.set(event.event_id, event)
    replaceEvents([...byId.values()].sort((a, b) => a.event_number - b.event_number))
  }, [replaceEvents])

  const ingest = useCallback((incoming: TelemetrySample[]) => {
    const matching = incoming.filter(sample => sample.run_id === runRef.current)
    if (matching.length === 0) return
    const bySequence = new Map(samplesRef.current.map(sample => [sample.sequence_number, sample]))
    for (const sample of matching) bySequence.set(sample.sequence_number, sample)
    const next = keepRecent([...bySequence.values()].sort((a, b) => a.sequence_number - b.sequence_number))
    replaceSamples(next)
    const latest = next[next.length - 1]
    const current = deviceRef.current
    if (latest && current?.run_id === latest.run_id && current.status === 'RUNNING') {
      const updated: VirtualDeviceSnapshot = { ...current, sensors: latest.sensors,
        simulation_elapsed_seconds: latest.simulation_elapsed_seconds, updated_at: latest.sample_time }
      deviceRef.current = updated
      setDevice(updated)
    }
  }, [replaceSamples])

  useEffect(() => {
    let active = true
    let retryTimer: number | undefined
    let retry = 0
    let lastMessage = Date.now()
    let syncQueue = Promise.resolve()
    let eventSyncQueue = Promise.resolve()
    const clockTimer = window.setInterval(() => {
      setClock(Date.now())
      if (socketRef.current?.readyState === WebSocket.OPEN && Date.now() - lastMessage > SOCKET_TIMEOUT_MS) {
        socketRef.current.close()
      }
    }, 1000)

    const catchUp = async (runId: string, from?: number) => {
      let after = from
      while (active && runRef.current === runId) {
        const history = await getTelemetryHistory(runId, after)
        if (!active || runRef.current !== runId) return
        ingest(history.samples)
        if (!history.has_more || history.samples.length === 0) return
        after = history.samples[history.samples.length - 1].sequence_number
      }
    }

    const catchUpEvents = async (runId: string, from: number) => {
      let after = from
      while (active && runRef.current === runId) {
        const history = await getOperatorEvents(runId, after)
        if (!active || runRef.current !== runId) return
        ingestEvents(history.events)
        if (!history.has_more || history.events.length === 0) return
        after = history.events[history.events.length - 1].event_number
      }
    }

    const acceptStatus = (snapshot: VirtualDeviceSnapshot, summary: RunSummary | null, latest: TelemetrySample | null,
      ruleAlerts: RuleAlert[], rejectedPackets: RejectedTelemetry[], modelStatus: AIStatus, modelEvents: AIEvent[], trustOverview: TrustOverview) => {
      const changedRun = runRef.current !== snapshot.run_id
      if (changedRun) {
        runRef.current = snapshot.run_id
        replaceSamples([])
        replaceEvents([])
        setAlerts([])
        setRejections([])
        setAiEvents([])
        trustIdRef.current = 0
        setTrust(null)
      }
      deviceRef.current = snapshot
      setDevice(snapshot)
      setRun(summary)
      setAlerts(ruleAlerts ?? [])
      setRejections(rejectedPackets ?? [])
      setAiStatus(modelStatus)
      setAiEvents(modelEvents ?? [])
      acceptTrust(trustOverview)
      if (snapshot.run_id) {
        const runId = snapshot.run_id
        const from = changedRun ? undefined : samplesRef.current[samplesRef.current.length - 1]?.sequence_number
        syncQueue = syncQueue.then(async () => {
          try {
            await catchUp(runId, from)
            if (active && latest && runRef.current === runId) ingest([latest])
          } catch {
            // A later reconnect retries from the last committed sequence.
          }
        })
        const eventFrom = changedRun ? 0 : eventsRef.current[eventsRef.current.length - 1]?.event_number ?? 0
        eventSyncQueue = eventSyncQueue.then(() => catchUpEvents(runId, eventFrom)).catch(() => {})
      }
    }

    const connect = () => {
      if (!active) return
      if (retry === 0) setTransport('connecting')
      lastMessage = Date.now()
      const socket = new WebSocket(telemetrySocketUrl())
      socketRef.current = socket
      socket.onmessage = event => {
        if (!active || socketRef.current !== socket) return
        lastMessage = Date.now()
        retry = 0
        setTransport('live')
        try {
          const message = JSON.parse(event.data) as TelemetryEvent
          if (message.type === 'simulation_status') { acceptStatus(message.device, message.run, message.latest_sample, message.rule_alerts, message.rejections, message.ai_status, message.ai_events, message.trust); setDeviceLastSeenAt(message.device_last_seen_at ?? null) }
          else if (message.type === 'telemetry_sample') { ingest([message]); setDeviceLastSeenAt(new Date().toISOString()) }
          else if (message.type === 'ai_assessment' && message.run_id === runRef.current) setAiStatus(message.ai_status)
          else if (message.type === 'ai_event' && message.run_id === runRef.current) {
            setAiEvents(current => [...current.filter(item => item.event_id !== message.event_id), message]
              .sort((a, b) => a.start_sequence_number - b.start_sequence_number))
          }
          else if (message.type === 'rule_alert' && message.run_id === runRef.current) {
            setAlerts(current => [...current.filter(alert => alert.alert_id !== message.alert_id), message])
          }
          else if (message.type === 'telemetry_rejected' && message.run_id === runRef.current) {
            setRejections(current => [...current.filter(item => item.rejection_id !== message.rejection_id), message])
          }
          else if (message.type === 'trust_assessment' && message.run_id === runRef.current) acceptTrust(message.trust)
          else if (message.type === 'operator_event' && message.run_id && message.run_id === runRef.current) {
            const runId = message.run_id
            const from = eventsRef.current[eventsRef.current.length - 1]?.event_number ?? 0
            eventSyncQueue = eventSyncQueue.then(async () => {
              try {
                await catchUpEvents(runId, from)
                if (active) ingestEvents([message])
              } catch { if (active) ingestEvents([message]) }
            })
          }
          else if (message.type === 'heartbeat') {
            setDeviceLastSeenAt(message.device_last_seen_at ?? null)
            if (message.run_id !== runRef.current || message.status !== deviceRef.current?.status) {
            void getTelemetryState().then(state => {
              if (active && state.device) { acceptStatus(state.device, state.run, state.latest_sample, state.rule_alerts, state.rejections, state.ai_status, state.ai_events, state.trust); setDeviceLastSeenAt(state.device_last_seen_at ?? null) }
            }).catch(() => {})
            }
          }
        } catch {
          // Ignore a malformed frame; a later status or reconnect restores state.
        }
      }
      socket.onclose = event => {
        if (!active || socketRef.current !== socket) return
        if (event.code === 1008) {
          window.dispatchEvent(new Event('orbitra-auth-expired'))
          return
        }
        socketRef.current = null
        setTransport('disconnected')
        retry += 1
        retryTimer = window.setTimeout(connect, Math.min(5000, 1000 * 2 ** (retry - 1)))
      }
      socket.onerror = () => socket.close()
    }

    void getTelemetryState().then(state => {
      if (!active) return
      if (state.device) { acceptStatus(state.device, state.run, state.latest_sample, state.rule_alerts, state.rejections, state.ai_status, state.ai_events, state.trust); setDeviceLastSeenAt(state.device_last_seen_at ?? null) }
      else setAiStatus(state.ai_status)
      connect()
    }).catch(() => {
      if (active) connect()
    })

    return () => {
      active = false
      window.clearInterval(clockTimer)
      if (retryTimer !== undefined) window.clearTimeout(retryTimer)
      socketRef.current?.close()
      socketRef.current = null
    }
  }, [acceptTrust, ingest, ingestEvents, replaceEvents, replaceSamples])

  const latestSample = samples[samples.length - 1] ?? null
  const sampleAgeSeconds = latestSample ? Math.max(0, Math.floor((clock - Date.parse(latestSample.sample_time)) / 1000)) : null
  const state: LiveState = useMemo(() => {
    if (transport === 'connecting') return 'connecting'
    if (transport === 'disconnected') return 'disconnected'
    if (device?.run_id && (!deviceLastSeenAt || clock - Date.parse(deviceLastSeenAt) > 7000)) return 'stale'
    if (device?.status === 'PAUSED') return 'paused'
    if (device?.status === 'ENDED') return 'ended'
    if (!device?.run_id || !latestSample) return 'no_data'
    if (device.status === 'RUNNING' && sampleAgeSeconds !== null && sampleAgeSeconds * 1000 > STALE_AFTER_MS) return 'stale'
    return 'live'
  }, [clock, device, deviceLastSeenAt, latestSample, sampleAgeSeconds, transport])

  const command = useCallback(async (action: DeviceAction, scenario?: ScenarioName) => {
    if (socketRef.current?.readyState !== WebSocket.OPEN) throw new Error('Canlı bağlantı yoxdur.')
    const result = await performVirtualDeviceAction(action, scenario)
    if (result.run_id !== runRef.current) {
      runRef.current = result.run_id
      replaceSamples([])
      replaceEvents([])
      setRun(null)
      setAlerts([])
      setRejections([])
      setAiEvents([])
      setAiStatus(null)
      trustIdRef.current = 0
      setTrust(null)
    }
    deviceRef.current = result
    setDevice(result)
    if (result.run_id) {
      const current = eventsRef.current[eventsRef.current.length - 1]?.event_number ?? 0
      try {
        const history = await getOperatorEvents(result.run_id, current)
        ingestEvents(history.events)
      } catch { /* WebSocket reconnect will recover the event. */ }
    }
    return result
  }, [ingestEvents, replaceEvents, replaceSamples])

  return { device, run, samples, events, alerts, rejections, aiStatus, aiEvents, trust, latestSample, state, sampleAgeSeconds, command }
}

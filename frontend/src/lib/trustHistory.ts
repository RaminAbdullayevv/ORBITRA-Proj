import type { TrustDecision } from './api'

/** Merge HTTP catch-up and WebSocket deliveries by persisted assessment ID. */
export function mergeTrustHistory(current: TrustDecision[], incoming: TrustDecision[], limit = 100): TrustDecision[] {
  const byId = new Map(current.map(item => [item.id, item]))
  for (const item of incoming) byId.set(item.id, item)
  return [...byId.values()].sort((a, b) => b.id - a.id).slice(0, limit)
}

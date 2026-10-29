import assert from 'node:assert/strict'
import test from 'node:test'
import { mergeTrustHistory } from '../src/lib/trustHistory.ts'

test('replayed WebSocket and HTTP decisions appear once and stay newest first', () => {
  const first = { id: 10, mission_id: 'run-a' }
  const newer = { id: 11, mission_id: 'run-a' }
  const history = mergeTrustHistory([first], [first, newer, newer])
  assert.deepEqual(history.map(item => item.id), [11, 10])
  assert.deepEqual(mergeTrustHistory(history, [newer]).map(item => item.id), [11, 10])
})

test('long histories remain bounded', () => {
  const rows = Array.from({ length: 150 }, (_, id) => ({ id, mission_id: 'run-a' }))
  const history = mergeTrustHistory([], rows)
  assert.equal(history.length, 100)
  assert.equal(history[0].id, 149)
  assert.equal(history.at(-1).id, 50)
})

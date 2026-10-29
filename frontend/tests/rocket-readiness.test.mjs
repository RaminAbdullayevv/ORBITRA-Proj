import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'

async function loadPureModule(name) {
  const path = fileURLToPath(new URL(`../src/lib/${name}.ts`, import.meta.url))
  const source = await readFile(path, 'utf8')
  const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } })
  return import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)
}

const { assessSubsystems } = await loadPureModule('subsystems')
const { rocketBlocks } = await loadPureModule('rocketSystem')
const { assessReadiness } = await loadPureModule('readiness')

const sensors = {
  battery_level_percent: 90, voltage_v: 28, current_a: 2,
  temperature_1_c: 20, temperature_2_c: 20, temperature_3_c: 20,
  cpu_load_percent: 20, memory_usage_percent: 30,
  signal_strength_percent: 95, communication_latency_ms: 20, packet_loss_percent: 0,
}
const sample = { sensors }
const base = {
  missionStarted: true, hasTrustedSample: true, connectionLost: false, paused: false,
  health: ['NORMAL', 'NORMAL', 'NORMAL', 'NORMAL'], activeCriticalAlert: false,
  integrityIncident: false, quarantinedCritical: false, sentinelDegraded: false,
}

test('readiness uses accepted-data and incident gates', () => {
  assert.equal(assessReadiness({ ...base, missionStarted: false }).level, 'MƏLUMAT YOXDUR')
  assert.equal(assessReadiness({ ...base, missionStarted: false }).reason, 'Aktiv sınaq yoxdur.')
  assert.equal(assessReadiness({ ...base, hasTrustedSample: false }).level, 'MƏLUMAT YOXDUR')
  assert.equal(assessReadiness(base).level, 'HAZIR')
  assert.equal(assessReadiness({ ...base, health: ['NORMAL', 'WARNING'] }).level, 'DİQQƏT')
  assert.equal(assessReadiness({ ...base, paused: true }).level, 'DİQQƏT')
  assert.equal(assessReadiness({ ...base, connectionLost: true }).level, 'HAZIR DEYİL')
  assert.equal(assessReadiness({ ...base, quarantinedCritical: true }).level, 'HAZIR DEYİL')
  assert.equal(assessReadiness({ ...base, health: ['CRITICAL'] }).level, 'HAZIR DEYİL')
})

test('untrusted telemetry cannot color rocket blocks', () => {
  const health = assessSubsystems(sample, [], false)
  const blocks = rocketBlocks(sample, health, false)
  assert.equal(blocks.length, 6)
  assert.ok(blocks.every(block => block.status === 'UNKNOWN' && block.reading === 'Etibarlı məlumat yoxdur'))
})

test('isolated temperature sensor fault does not make entire thermal system critical', () => {
  const faulty = { sensors: { ...sensors, temperature_1_c: 35 } }
  const health = assessSubsystems(faulty, [], true, 'PROBABLE SENSOR FAULT')
  const blocks = rocketBlocks(faulty, health, true, 'PROBABLE SENSOR FAULT')
  assert.equal(health.find(item => item.key === 'thermal').status, 'NORMAL')
  assert.equal(blocks.find(item => item.id === 'sensors').status, 'WARNING')
  assert.equal(blocks.find(item => item.id === 'thermal').status, 'NORMAL')
  assert.ok(blocks.filter(block => block.status === 'WARNING').length === 1)
})

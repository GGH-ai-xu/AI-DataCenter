import test from 'node:test'
import assert from 'node:assert/strict'
import {
  buildDashboardSummary,
  normalizeProcesses,
  buildTaskSummary,
  filterProcesses,
  selectVisibleProcesses,
} from './realtimeSummaries.js'

test('buildDashboardSummary counts priorities, users, hot gpus, and critical alerts', () => {
  const summary = buildDashboardSummary({
    gpus: [{ index: 0, temperature: 82 }, { index: 1, temperature: 61 }],
    processes: [
      { pid: 1, username: 'alice', priority: 'urgent' },
      { pid: 2, username: 'bob', priority: 'deferrable' },
      { pid: 3, username: 'alice' },
    ],
    alerts: [
      { id: 1, severity: 'critical' },
      { id: 2, severity: 'warning' },
      { id: 3, severity: 'critical' },
    ],
  })

  assert.equal(summary.activeUsers, 2)
  assert.equal(summary.urgentTasks, 1)
  assert.equal(summary.deferrableTasks, 1)
  assert.equal(summary.normalTasks, 1)
  assert.equal(summary.hotGpuCount, 1)
  assert.equal(summary.criticalAlerts.length, 2)
})

test('normalizeProcesses sorts manageable tasks first and adds haystack text', () => {
  const normalized = normalizeProcesses([
    { pid: 2, username: 'bob', manageable: false, gpu_memory_used: 1024, command: 'python b.py' },
    { pid: 1, username: 'alice', gpu_memory_used: 4096, command: 'python a.py' },
  ])

  assert.equal(normalized[0].pid, 1)
  assert.match(normalized[0].haystack, /alice/)
  assert.equal(normalized[1].manageable, false)
})

test('buildTaskSummary and filterProcesses share one normalized list', () => {
  const normalized = normalizeProcesses([
    { pid: 1, username: 'alice', priority: 'urgent', gpu_memory_used: 4096, command: 'train.py' },
    { pid: 2, username: 'bob', priority: 'deferrable', gpu_memory_used: 2048, command: 'idle.py' },
    { pid: 3, username: 'sys', manageable: false, gpu_memory_used: 0, command: 'dwm.exe' },
  ])
  const summary = buildTaskSummary(normalized)
  const filtered = filterProcesses(normalized, {
    keyword: 'train',
    priority: 'all',
    includeAll: false,
  })

  assert.equal(summary.manageableCount, 2)
  assert.equal(summary.backgroundCount, 1)
  assert.equal(summary.userCount, 2)
  assert.equal(summary.totalGpuMemory, 6144)
  assert.deepEqual(filtered.map((process) => process.pid), [1])
})

test('selectVisibleProcesses preserves manageable-only and include-all views', () => {
  const normalized = normalizeProcesses([
    { pid: 1, username: 'alice', priority: 'urgent', gpu_memory_used: 4096, command: 'train.py' },
    { pid: 2, username: 'bob', manageable: false, gpu_memory_used: 128, command: 'helper.exe' },
  ])

  assert.deepEqual(
    selectVisibleProcesses(normalized, false).map((process) => process.pid),
    [1],
  )
  assert.deepEqual(
    selectVisibleProcesses(normalized, true).map((process) => process.pid),
    [1, 2],
  )
})

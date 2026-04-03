import test from 'node:test'
import assert from 'node:assert/strict'
import { createPinia, setActivePinia } from 'pinia'
import { useAppStore } from './app.js'

test('applyRealtimePayload updates raw data, summaries, and capped alerts', () => {
  setActivePinia(createPinia())
  const store = useAppStore()

  store.applyRealtimePayload({
    gpus: [{ index: 0, temperature: 83, power_usage: 200 }],
    processes: [
      { pid: 1, username: 'alice', priority: 'urgent', gpu_memory_used: 4096 },
    ],
    alerts: Array.from({ length: 120 }, (_, index) => ({
      id: index + 1,
      severity: 'critical',
    })),
  })

  assert.equal(store.gpus.length, 1)
  assert.equal(store.normalizedProcesses.length, 1)
  assert.equal(store.dashboardSummary.hotGpuCount, 1)
  assert.equal(store.alerts.length, 100)
})

test('applyRealtimePayload keeps workspace ready and records reconnecting runtime state', () => {
  setActivePinia(createPinia())
  const store = useAppStore()

  store.applyRealtimePayload({
    import_context: {
      valid: true,
      imported_gpu_indexes: [0],
      provider_type: 'ssh_linux',
    },
    runtime: {
      status: 'reconnecting',
      connected: false,
      provider_type: 'ssh_linux',
    },
  })

  assert.equal(store.workspaceReady, true)
  assert.equal(store.runtimeStatus.status, 'reconnecting')
  assert.equal(store.runtimeStatus.providerType, 'ssh_linux')
})

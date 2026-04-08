import test from 'node:test'
import assert from 'node:assert/strict'

import { createDashboardLoaders } from './dashboardLoaders.js'

test('overview loader only requests overview dependencies', async () => {
  const calls = []
  const api = {
    getSchedulerStatus: async () => {
      calls.push('scheduler')
      return { data: { budget: { enabled: true } } }
    },
    healthCheck: async () => {
      calls.push('health')
      return { data: { workspace_ready: true } }
    },
    getFairnessGovernance: async () => {
      calls.push('fairness')
      return { data: { overview: { fairness_index: 91 } } }
    },
    getSystemSelfCheck: async () => {
      calls.push('self-check')
      return { data: { summary: { title: 'unused' } } }
    },
  }

  const loaders = createDashboardLoaders(api)
  const payload = await loaders.loadOverviewBundle()

  assert.deepEqual(calls, ['scheduler', 'health', 'fairness'])
  assert.equal(payload.selfCheck, undefined)
})

test('health loader only requests health dependencies', async () => {
  const calls = []
  const api = {
    getSchedulerStatus: async () => {
      calls.push('scheduler')
      return { data: {} }
    },
    healthCheck: async () => {
      calls.push('health')
      return { data: { workspace_ready: true } }
    },
    getFairnessGovernance: async () => {
      calls.push('fairness')
      return { data: {} }
    },
    getSystemSelfCheck: async () => {
      calls.push('self-check')
      return { data: { summary: { title: '2 项异常' } } }
    },
  }

  const loaders = createDashboardLoaders(api)
  const payload = await loaders.loadHealthBundle()

  assert.deepEqual(calls, ['health', 'self-check'])
  assert.equal(payload.health.workspace_ready, true)
  assert.equal(payload.selfCheck.summary.title, '2 项异常')
})

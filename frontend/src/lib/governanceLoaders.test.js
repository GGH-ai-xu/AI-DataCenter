import test from 'node:test'
import assert from 'node:assert/strict'

import { createGovernanceLoaders } from './governanceLoaders.js'

test('actions loader only requests task ledger and fairness summary', async () => {
  const calls = []
  const api = {
    getTasks: async () => {
      calls.push('tasks')
      return { data: { processes: [{ pid: 11 }] } }
    },
    getFairnessGovernance: async () => {
      calls.push('fairness')
      return { data: { overview: { fairness_index: 91 }, yield_candidates: [{ pid: 11 }] } }
    },
    getSchedulerStatus: async () => {
      calls.push('scheduler')
      return { data: {} }
    },
    getCarbonBudget: async () => {
      calls.push('carbon')
      return { data: {} }
    },
    getGovernanceRules: async () => {
      calls.push('rules')
      return { data: { rules: [] } }
    },
    getAuditLogs: async () => {
      calls.push('audit')
      return { data: { logs: [] } }
    },
    getScheduleEvaluation: async () => {
      calls.push('evaluation')
      return { data: null }
    },
  }

  const loaders = createGovernanceLoaders(api)
  const payload = await loaders.loadActionsBundle()

  assert.deepEqual(calls, ['tasks', 'fairness'])
  assert.equal(payload.processes.length, 1)
  assert.equal(payload.fairness.overview.fairness_index, 91)
})

test('policies loader only requests policy dependencies', async () => {
  const calls = []
  const api = {
    getTasks: async () => {
      calls.push('tasks')
      return { data: { processes: [] } }
    },
    getFairnessGovernance: async () => {
      calls.push('fairness')
      return { data: { users: [{ username: 'alice' }] } }
    },
    getSchedulerStatus: async () => {
      calls.push('scheduler')
      return { data: { budget: { total_power_budget: 1200 } } }
    },
    getCarbonBudget: async () => {
      calls.push('carbon')
      return { data: { daily_budget_kg: 55 } }
    },
    getGovernanceRules: async () => {
      calls.push('rules')
      return { data: { rules: [{ username: 'alice', role: 'protected' }] } }
    },
    getAuditLogs: async () => {
      calls.push('audit')
      return { data: { logs: [] } }
    },
    getScheduleEvaluation: async () => {
      calls.push('evaluation')
      return { data: null }
    },
  }

  const loaders = createGovernanceLoaders(api)
  const payload = await loaders.loadPoliciesBundle()

  assert.deepEqual(calls, ['scheduler', 'carbon', 'fairness', 'rules'])
  assert.equal(payload.scheduler.budget.total_power_budget, 1200)
  assert.equal(payload.rules[0].role, 'protected')
})

test('review loader only requests audit and evaluation data', async () => {
  const calls = []
  const api = {
    getTasks: async () => {
      calls.push('tasks')
      return { data: { processes: [] } }
    },
    getFairnessGovernance: async () => {
      calls.push('fairness')
      return { data: {} }
    },
    getSchedulerStatus: async () => {
      calls.push('scheduler')
      return { data: {} }
    },
    getCarbonBudget: async () => {
      calls.push('carbon')
      return { data: {} }
    },
    getGovernanceRules: async () => {
      calls.push('rules')
      return { data: { rules: [] } }
    },
    getAuditLogs: async (limit, hours) => {
      calls.push(`audit:${limit}:${hours}`)
      return { data: { logs: [{ action: 'run_schedule_once' }] } }
    },
    getScheduleEvaluation: async () => {
      calls.push('evaluation')
      return { data: { summary: 'ok' } }
    },
  }

  const loaders = createGovernanceLoaders(api)
  const payload = await loaders.loadReviewBundle()

  assert.deepEqual(calls, ['audit:100:72', 'evaluation'])
  assert.equal(payload.auditLogs.length, 1)
  assert.equal(payload.evaluation.summary, 'ok')
})

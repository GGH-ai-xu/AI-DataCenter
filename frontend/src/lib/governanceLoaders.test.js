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

test('review loader requests command records and evaluation data', async () => {
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
    getScheduleEvaluation: async () => {
      calls.push('evaluation')
      return { data: { summary: 'ok' } }
    },
    listControlCommands: async (limit) => {
      calls.push(`commands:${limit}`)
      return { data: { commands: [{ command_id: 'cmd-1' }] } }
    },
  }

  const loaders = createGovernanceLoaders(api)
  const payload = await loaders.loadReviewBundle()

  assert.deepEqual(calls, ['commands:100', 'evaluation'])
  assert.equal(payload.commandRecords.length, 1)
  assert.equal(payload.evaluation.summary, 'ok')
})

import test from 'node:test'
import assert from 'node:assert/strict'

import {
  GOVERNANCE_TABS,
  buildGovernanceHeaderModel,
  buildGovernanceReviewModel,
  buildGovernanceRulesModel,
} from './governancePageModels.js'

test('governance tabs keep the four-section workflow order', () => {
  assert.deepEqual(
    GOVERNANCE_TABS.map((item) => item.key),
    ['actions', 'policies', 'cluster', 'review'],
  )
})

test('header model returns action workspace summary', () => {
  const model = buildGovernanceHeaderModel('actions', {
    taskSummary: {
      manageableCount: 6,
      urgentCount: 2,
    },
    fairnessOverview: {
      level: 'tilted',
      reclaimable_candidates: 3,
    },
  })

  assert.equal(model.title, '即时处置')
  assert.deepEqual(model.quickStats.map((item) => item.label), ['可治理任务', '紧急任务', '让路候选'])
  assert.equal(model.quickStats[2].value, '3')
})

test('rules model merges fairness users with stored rules', () => {
  const model = buildGovernanceRulesModel({
    users: [
      { username: 'alice', task_count: 2, gpu_count: 1, violation_count: 1, governance_rule: null },
    ],
    rules: [
      { username: 'alice', role: 'protected', max_tasks: 8, max_gpu_count: 2, max_memory_gb: 24, allow_preempt: false, note: 'vip' },
    ],
  })

  assert.equal(model.users[0].governance_rule.role, 'protected')
  assert.equal(model.summary.coveragePct, 100)
})

test('review model counts failed actions and builds timeline items', () => {
  const model = buildGovernanceReviewModel({
    commandRecords: [
      { command_id: 'cmd-1', capability_name: 'scheduler.run_once', risk_level: 'observe', created_at: 1712560000, execution_state: 'succeeded' },
      { command_id: 'cmd-2', capability_name: 'scheduler.power_limit.set', risk_level: 'dangerous', created_at: 1712560300, execution_state: 'failed' },
    ],
    evaluation: {
      fairness_delta: 6,
      budget_relieved: true,
    },
  })

  assert.equal(model.summary.failedActions, 1)
  assert.equal(model.timeline.length, 2)
  assert.equal(model.timeline[1].tone, 'dangerous')
})

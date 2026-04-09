import test from 'node:test'
import assert from 'node:assert/strict'

import {
  applyBudgetState,
  applyCarbonState,
  formatActionLabel,
  formatActionTarget,
} from './governancePolicyState.js'

test('applyBudgetState fills missing fields with safe defaults', () => {
  const budget = applyBudgetState({ total_power_budget: 1400, usage_pct: 66 })

  assert.equal(budget.total_power_budget, 1400)
  assert.equal(budget.remaining_power, 1200)
  assert.equal(Array.isArray(budget.last_actions), true)
})

test('applyCarbonState merges over existing values', () => {
  const current = { enabled: false, daily_budget_kg: 50, usage_pct: 0 }
  const next = applyCarbonState(current, { enabled: true, usage_pct: 40 })

  assert.equal(next.enabled, true)
  assert.equal(next.daily_budget_kg, 50)
  assert.equal(next.usage_pct, 40)
})

test('format helpers map scheduler actions to readable labels', () => {
  assert.equal(formatActionLabel({ action: 'set_power_limit' }), '压缩功耗')
  assert.equal(formatActionTarget({ target: { gpu_index: 3 } }), 'GPU 3')
})

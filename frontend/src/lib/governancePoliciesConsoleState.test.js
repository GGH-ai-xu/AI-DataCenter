import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildDraftCardState,
  buildExecutionBannerModel,
} from './governancePoliciesConsoleState.js'

test('buildDraftCardState marks budget edits as pending', () => {
  const state = buildDraftCardState({
    kind: 'budget',
    current: { enabled: true, total_power_budget: 1200 },
    draft: { enabled: false, total_power_budget: 1400 },
  })

  assert.equal(state.pending, true)
  assert.equal(state.badgeLabel, '待应用')
  assert.equal(state.actionLabel, '应用预算修改')
})

test('buildDraftCardState keeps untouched carbon card synced', () => {
  const state = buildDraftCardState({
    kind: 'carbon',
    current: { enabled: false, daily_budget_kg: 50 },
    draft: { enabled: false, daily_budget_kg: 50 },
  })

  assert.equal(state.pending, false)
  assert.equal(state.badgeLabel, '已同步')
  assert.equal(state.actionTone, 'quiet')
})

test('buildExecutionBannerModel exposes inline warning for real execution without risk ack', () => {
  const banner = buildExecutionBannerModel({
    actionLabel: '执行一次调度',
    isReal: true,
    riskAcknowledged: false,
    reversible: true,
  })

  assert.equal(banner.tone, 'warning')
  assert.match(banner.detail, /执行一次调度/)
})

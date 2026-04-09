import test from 'node:test'
import assert from 'node:assert/strict'

import {
  getActionHint,
  getCategoryLabel,
  getManageableReason,
  isManageable,
} from './governanceTaskLedger.js'

test('system process is marked as non-manageable with explicit reason', () => {
  const proc = { manageable: false, process_category: 'system' }

  assert.equal(isManageable(proc), false)
  assert.equal(getCategoryLabel(proc), '系统进程')
  assert.equal(getManageableReason(proc), '该进程不建议执行治理动作。')
})

test('manageable process shows real execution warning when risk is not acknowledged', () => {
  const proc = { manageable: true }

  assert.equal(
    getActionHint(proc, { isDryRun: false, isReal: true, riskAcknowledged: false }),
    '确认风险后才会真实执行',
  )
})

test('non-real execution state prompts to switch back to real execution', () => {
  const proc = { manageable: true }

  assert.equal(
    getActionHint(proc, { isDryRun: true, isReal: false, riskAcknowledged: false }),
    '当前治理台仅支持真实执行',
  )
})

import test from 'node:test'
import assert from 'node:assert/strict'

import { useExecutionMode } from './useExecutionMode.js'

test('useExecutionMode defaults governance workspace to real execution with risk confirmation pending', () => {
  const execution = useExecutionMode()

  assert.equal(execution.executionMode.value, 'real')
  assert.equal(execution.isDryRun.value, false)
  assert.equal(execution.isReal.value, true)
  assert.equal(execution.canExecute.value, false)
  assert.equal(execution.modeLabel.value, '真实执行')
  assert.deepEqual(execution.buildExecutionParams(), { acknowledge_risk: false })
})

test('useExecutionMode only enables execution after risk acknowledgement', () => {
  const execution = useExecutionMode()

  execution.riskAcknowledged.value = true

  assert.equal(execution.canExecute.value, true)
  assert.deepEqual(execution.buildExecutionParams(), { acknowledge_risk: true })
})

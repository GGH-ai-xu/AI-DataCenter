import test from 'node:test'
import assert from 'node:assert/strict'

import { availableJobActions } from './clusterConsoleActions.js'

test('availableJobActions prefers restore for preempted jobs with a ready checkpoint', () => {
  const actions = availableJobActions({
    status: 'preempted',
    lifecycleKind: 'batch',
    canRequeue: true,
    checkpointStatus: 'checkpoint_ready',
  })

  assert.deepEqual(actions, ['restore', 'requeue'])
})

test('availableJobActions keeps preempted jobs requeue-only without a ready checkpoint', () => {
  const actions = availableJobActions({
    status: 'preempted',
    lifecycleKind: 'batch',
    canRequeue: true,
    checkpointStatus: 'checkpoint_requested',
  })

  assert.deepEqual(actions, ['requeue'])
})

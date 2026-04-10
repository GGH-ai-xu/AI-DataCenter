import test from 'node:test'
import assert from 'node:assert/strict'

import { buildClusterConsoleModel } from './clusterConsoleModels.js'

test('buildClusterConsoleModel groups queues jobs and allocations', () => {
  const model = buildClusterConsoleModel({
    queues: [{ queue_id: 'default', queued_jobs: 2 }],
    jobs: [{ job_id: 'job-1', status: 'running', queue_id: 'default' }],
    allocations: [{ allocation_id: 'alloc-1', node_id: 'node-a', job_id: 'job-1' }],
  })

  assert.equal(model.queues[0].id, 'default')
  assert.equal(model.jobs[0].id, 'job-1')
  assert.equal(model.allocationsByNode[0].nodeId, 'node-a')
})

import test from 'node:test'
import assert from 'node:assert/strict'

import { buildClusterConsoleModel } from './clusterConsoleModels.js'

test('buildClusterConsoleModel groups queues jobs and allocations', () => {
  const model = buildClusterConsoleModel({
    queues: [{ queue_id: 'default', queued_jobs: 2 }],
    jobs: [{ job_id: 'job-1', status: 'running', queue_id: 'default' }],
    allocations: [{ allocation_id: 'alloc-1', node_id: 'node-a', job_id: 'job-1' }],
    nodes: [{ node_id: 'node-a', drain_state: 'drained', label: 'Node A' }],
  })

  assert.equal(model.queues[0].id, 'default')
  assert.equal(model.jobs[0].id, 'job-1')
  assert.equal(model.allocationsByNode[0].nodeId, 'node-a')
  assert.equal(model.nodes[0].drainState, 'drained')
})

test('buildClusterConsoleModel maps unified task metadata and readiness state', () => {
  const model = buildClusterConsoleModel({
    jobs: [
      {
        job_id: 'job-service',
        queue_id: 'default',
        status: 'ready',
        task_kind: 'inference_service',
        lifecycle_kind: 'service',
        service_ports: [8080],
        readiness_state: 'ready',
        runtime_profile: { latency_sensitive: true, exclusive_gpu: true },
      },
    ],
  })

  assert.equal(model.jobs[0].taskKind, 'inference_service')
  assert.equal(model.jobs[0].lifecycleKind, 'service')
  assert.deepEqual(model.jobs[0].servicePorts, [8080])
  assert.equal(model.jobs[0].readinessState, 'ready')
  assert.equal(model.jobs[0].runtimeProfile.latency_sensitive, true)
})

test('buildClusterConsoleModel summarizes queue admission limits and blocked reasons', () => {
  const model = buildClusterConsoleModel({
    queues: [
      {
        queue_id: 'default',
        name: 'Default',
        state: 'active',
        default_priority: 50,
        max_concurrency: 1,
      },
    ],
    jobs: [
      {
        job_id: 'job-wait',
        queue_id: 'default',
        status: 'pending',
        last_plan_type: 'wait',
        last_plan_reason: 'queue default reached max_concurrency 1',
      },
      {
        job_id: 'job-rejected',
        queue_id: 'default',
        status: 'rejected',
        last_plan_type: 'reject',
        last_plan_reason: 'queue default is paused',
      },
    ],
  })

  assert.equal(model.jobs[0].planType, 'wait')
  assert.equal(model.queues[0].maxConcurrency, 1)
  assert.equal(model.queues[0].concurrencyLabel, '并发上限 1')
  assert.equal(model.queues[0].blockedJobs, 2)
  assert.equal(model.queues[0].waitReasonSummary, '最近阻塞：queue default reached max_concurrency 1')
})

test('buildClusterConsoleModel exposes dispatching and failed execution states', () => {
  const model = buildClusterConsoleModel({
    queues: [
      {
        queue_id: 'default',
        name: 'Default',
        state: 'active',
        default_priority: 50,
      },
    ],
    jobs: [
      {
        job_id: 'job-dispatching',
        queue_id: 'default',
        status: 'dispatching',
        runtime_job_handle: '',
        last_error: '',
      },
      {
        job_id: 'job-failed',
        queue_id: 'default',
        status: 'failed',
        runtime_job_handle: '',
        last_error: 'launch failed',
      },
      {
        job_id: 'job-running',
        queue_id: 'default',
        status: 'running',
        runtime_job_handle: 'handle-job-running',
        last_error: '',
      },
    ],
  })

  assert.equal(model.jobs[0].dispatchState, 'dispatching')
  assert.equal(model.jobs[1].lastError, 'launch failed')
  assert.equal(model.jobs[2].runtimeJobHandle, 'handle-job-running')
  assert.equal(model.queues[0].dispatchingJobs, 1)
  assert.equal(model.queues[0].failedJobs, 1)
})

test('buildClusterConsoleModel projects reclaim progress for preempted jobs', () => {
  const model = buildClusterConsoleModel({
    jobs: [
      {
        job_id: 'job-low',
        queue_id: 'default',
        status: 'preempted',
        has_releasing_allocation: true,
      },
    ],
    allocations: [
      {
        allocation_id: 'alloc-low',
        job_id: 'job-low',
        node_id: 'node-a',
        status: 'releasing',
      },
    ],
  })

  assert.equal(model.jobs[0].canRequeue, true)
  assert.equal(model.jobs[0].awaitingRelease, true)
  assert.equal(model.allocationsByNode[0].allocations[0].status, 'releasing')
})

test('buildClusterConsoleModel projects compact checkpoint metadata', () => {
  const model = buildClusterConsoleModel({
    jobs: [
      {
        job_id: 'job-ckpt',
        queue_id: 'default',
        status: 'checkpoint_ready',
        checkpoint_id: 'ckpt-1',
        checkpoint_status: 'checkpoint_ready',
        checkpoint_manifest_path: '/tmp/ckpt-1.json',
      },
    ],
  })

  assert.equal(model.jobs[0].checkpointId, 'ckpt-1')
  assert.equal(model.jobs[0].checkpointStatus, 'checkpoint_ready')
  assert.equal(model.jobs[0].checkpointManifestPath, '/tmp/ckpt-1.json')
})

test('buildClusterConsoleModel maps reconcile controller status for toolbar display', () => {
  const model = buildClusterConsoleModel({
    controller: {
      enabled: true,
      running: false,
      interval_seconds: 12,
      last_trigger: 'background',
      last_error: '',
      last_skip_reason: '',
      last_finished_at: 1712560300,
      last_summary: {
        dispatched: 2,
        completed: 1,
        released: 1,
      },
    },
  })

  assert.equal(model.controller.enabled, true)
  assert.equal(model.controller.intervalLabel, '每 12s')
  assert.match(model.controller.summaryLabel, /分发 2/)
  assert.match(model.controller.summaryLabel, /完成 1/)
})

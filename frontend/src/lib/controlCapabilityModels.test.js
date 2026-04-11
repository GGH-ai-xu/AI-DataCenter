import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildCapabilityDrawerModel,
  buildCapabilityFormArguments,
  buildCapabilityFormDraft,
  buildControlCommandTimeline,
} from './controlCapabilityModels.js'

test('buildCapabilityDrawerModel filters capabilities by governance section', () => {
  const model = buildCapabilityDrawerModel([
    { name: 'tasks.pause', domain: 'tasks', label: '暂停任务' },
    { name: 'scheduler.run_once', domain: 'scheduler', label: '执行一次调度' },
    { name: 'job.submit', domain: 'jobs', label: '提交作业' },
    { name: 'node.drain', domain: 'nodes', label: '排空节点' },
  ], 'actions')

  assert.deepEqual(
    model.items.map((item) => item.name),
    ['tasks.pause', 'scheduler.run_once'],
  )
})

test('buildCapabilityDrawerModel keeps cluster object capabilities in cluster section', () => {
  const model = buildCapabilityDrawerModel([
    { name: 'job.submit', domain: 'jobs', label: '提交作业' },
    { name: 'allocation.release', domain: 'allocations', label: '释放 allocation' },
    { name: 'node.drain', domain: 'nodes', label: '排空节点' },
  ], 'cluster')

  assert.deepEqual(
    model.items.map((item) => item.name),
    ['allocation.release', 'job.submit', 'node.drain'],
  )
})

test('buildControlCommandTimeline sorts newest commands first', () => {
  const items = buildControlCommandTimeline([
    { command_id: 'cmd-1', created_at: 10, execution_state: 'queued' },
    { command_id: 'cmd-2', created_at: 20, execution_state: 'succeeded' },
  ])

  assert.equal(items[0].id, 'cmd-2')
  assert.equal(items[0].stateLabel, '已完成')
})

test('buildControlCommandTimeline keeps approval-pending rows visible', () => {
  const items = buildControlCommandTimeline([
    { command_id: 'cmd-3', created_at: 30, execution_state: 'queued', approval_state: 'pending' },
  ])

  assert.equal(items[0].approvalLabel, '待审批')
})

test('buildCapabilityDrawerModel attaches typed form definitions for known capabilities', () => {
  const model = buildCapabilityDrawerModel([
    { name: 'scheduler.carbon_budget.configure', domain: 'scheduler', label: '配置碳预算' },
  ], 'policies')

  assert.equal(model.items[0].formDefinition.kind, 'scheduler.carbon_budget.configure')
  assert.equal(model.items[0].formDefinition.fields[0].key, 'enabled')
})

test('buildCapabilityFormDraft and arguments support compact job submit form', () => {
  const draft = buildCapabilityFormDraft('job.submit')
  draft.job_id = 'job-1'
  draft.entrypoint = 'python train.py'
  draft.queue_id = 'default'
  draft.tenant_id = 'tenant-a'
  draft.project_id = 'project-a'
  draft.submitter_id = 'alice'
  draft.gpu = 1
  draft.cpu = 4
  draft.priority = 60

  const argumentsPayload = buildCapabilityFormArguments('job.submit', draft)

  assert.deepEqual(argumentsPayload.resource_request, { gpu: 1, cpu: 4 })
  assert.equal(argumentsPayload.priority, 60)
  assert.equal(argumentsPayload.job_type, 'batch')
})

test('buildCapabilityDrawerModel exposes task-kind-aware job submit form fields', () => {
  const model = buildCapabilityDrawerModel([
    { name: 'job.submit', domain: 'jobs', label: '提交作业' },
  ], 'cluster')

  const fieldKeys = model.items[0].formDefinition.fields.map((item) => item.key)

  assert.ok(fieldKeys.includes('task_kind'))
  assert.ok(fieldKeys.includes('lifecycle_kind'))
  assert.ok(fieldKeys.includes('service_ports'))
})

test('buildCapabilityFormArguments serializes unified service job submit payload', () => {
  const draft = buildCapabilityFormDraft('job.submit')
  draft.job_id = 'job-svc-1'
  draft.task_kind = 'inference_service'
  draft.lifecycle_kind = 'service'
  draft.entrypoint = 'python serve.py'
  draft.queue_id = 'default'
  draft.tenant_id = 'tenant-a'
  draft.project_id = 'project-a'
  draft.submitter_id = 'alice'
  draft.gpu = 1
  draft.cpu = 4
  draft.priority = 80
  draft.preemptible = false
  draft.service_ports = '8080,9090'
  draft.checkpoint_policy = 'none'
  draft.restartable = false
  draft.latency_sensitive = true
  draft.exclusive_gpu = true
  draft.expected_duration_seconds = 0

  const argumentsPayload = buildCapabilityFormArguments('job.submit', draft)

  assert.equal(argumentsPayload.task_kind, 'inference_service')
  assert.equal(argumentsPayload.lifecycle_kind, 'service')
  assert.deepEqual(argumentsPayload.service_ports, [8080, 9090])
  assert.equal(argumentsPayload.checkpoint_policy, 'none')
  assert.equal(argumentsPayload.runtime_profile.latency_sensitive, true)
  assert.equal(argumentsPayload.runtime_profile.exclusive_gpu, true)
})

test('buildCapabilityFormDraft and arguments support node and allocation control forms', () => {
  const drainDraft = buildCapabilityFormDraft('node.drain')
  drainDraft.node_id = 'node-a'
  const releaseDraft = buildCapabilityFormDraft('allocation.release')
  releaseDraft.allocation_id = 'alloc-1'

  assert.deepEqual(buildCapabilityFormArguments('node.drain', drainDraft), { node_id: 'node-a' })
  assert.deepEqual(buildCapabilityFormArguments('allocation.release', releaseDraft), { allocation_id: 'alloc-1' })
})

test('buildCapabilityFormDraft exposes job.requeue and job.preempt forms', () => {
  assert.equal(buildCapabilityFormDraft('job.requeue').job_id, '')
  assert.equal(buildCapabilityFormDraft('job.preempt').job_id, '')
})

test('buildCapabilityFormDraft exposes checkpoint and restore job forms', () => {
  assert.equal(buildCapabilityFormDraft('job.checkpoint').job_id, '')
  assert.equal(buildCapabilityFormDraft('job.restore').job_id, '')
})

test('buildControlCommandTimeline adds summaries and detail affordances', () => {
  const items = buildControlCommandTimeline([
    {
      command_id: 'cmd-4',
      capability_name: 'scheduler.carbon_budget.configure',
      created_at: 50,
      execution_state: 'failed',
      approval_state: 'pending',
      source_page: 'governance-policies',
      arguments: { enabled: true, daily_budget_kg: 42 },
      error_message: '写入失败',
    },
  ])

  assert.equal(items[0].sourceLabel, '策略治理')
  assert.match(items[0].argumentSummary, /42/)
  assert.equal(items[0].canApprove, true)
  assert.equal(items[0].hasDetails, true)
})

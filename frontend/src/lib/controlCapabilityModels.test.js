import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildCapabilityDrawerModel,
  buildControlCommandTimeline,
} from './controlCapabilityModels.js'

test('buildCapabilityDrawerModel filters capabilities by governance section', () => {
  const model = buildCapabilityDrawerModel([
    { name: 'tasks.pause', domain: 'tasks', label: '暂停任务' },
    { name: 'scheduler.run_once', domain: 'scheduler', label: '执行一次调度' },
    { name: 'job.submit', domain: 'jobs', label: '提交作业' },
  ], 'actions')

  assert.deepEqual(
    model.items.map((item) => item.name),
    ['tasks.pause', 'scheduler.run_once'],
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

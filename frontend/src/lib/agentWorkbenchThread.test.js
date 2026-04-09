import test from 'node:test'
import assert from 'node:assert/strict'

import { buildAgentWorkbenchThread } from './agentWorkbenchThread.js'

test('buildAgentWorkbenchThread maps runtime events into plan approval tool result and error cards', () => {
  const view = buildAgentWorkbenchThread({
    chatMessages: [
      { id: 'm1', role: 'user', content: '把 GPU 0 的功耗上限调到 220W' },
    ],
    runtimeSession: {
      status: 'awaiting_approval',
      awaiting_approval: true,
      pending_approval: {
        actions: [{ capability_name: 'scheduler.power_limit.set' }],
      },
    },
    runtimeEvents: [
      {
        event_type: 'PlanCreated',
        payload: { summary: '限制 GPU 0 功耗', steps: [] },
        sequence: 1,
        timestamp: 1,
      },
      {
        event_type: 'AwaitingApproval',
        payload: {
          actions: [{ capability_name: 'scheduler.power_limit.set' }],
        },
        sequence: 2,
        timestamp: 2,
      },
      {
        event_type: 'StepStarted',
        payload: {
          step_id: 'step-1',
          capability_name: 'runtime.snapshot.read',
        },
        sequence: 3,
        timestamp: 3,
      },
      {
        event_type: 'SessionCompleted',
        payload: { summary: 'GPU 0 功耗已更新' },
        sequence: 4,
        timestamp: 4,
      },
      {
        event_type: 'LLMCallFailed',
        payload: { error: '模型返回了非 JSON 内容' },
        sequence: 5,
        timestamp: 5,
      },
    ],
  })

  assert.equal(view.topbar.statusLabel, '等待审批')
  assert.equal(view.topbar.approvalLabel, '待审批 1')
  assert.equal(view.items[0].kind, 'user_message')
  assert.equal(view.items[0].source, 'chat')
  assert.equal(view.items[1].kind, 'plan_card')
  assert.equal(view.items[2].kind, 'approval_card')
  assert.equal(view.items[3].kind, 'tool_event')
  assert.equal(view.items[3].collapsed, true)
  assert.equal(view.items[4].kind, 'result_card')
  assert.equal(view.items[5].kind, 'error_card')
  assert.equal(view.items[5].source, 'runtime')
})

test('buildAgentWorkbenchThread appends route confirm card for ambiguous inputs', () => {
  const view = buildAgentWorkbenchThread({
    chatMessages: [],
    runtimeSession: null,
    runtimeEvents: [],
    pendingRouteConfirm: {
      id: 'confirm-1',
      message: '帮我处理一下',
    },
  })

  assert.equal(view.items[0].kind, 'route_confirm_card')
  assert.equal(view.items[0].source, 'system')
})

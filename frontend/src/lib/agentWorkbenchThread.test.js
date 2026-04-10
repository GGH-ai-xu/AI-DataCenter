import test from 'node:test'
import assert from 'node:assert/strict'

import { buildAgentWorkbenchThread } from './agentWorkbenchThread.js'

test('buildAgentWorkbenchThread groups one user message and one assistant reply into one interaction', () => {
  const view = buildAgentWorkbenchThread({
    chatMessages: [
      { id: 'intro', role: 'assistant', content: '你好，我是 AI 治理助手。' },
      { id: 'u1', role: 'user', content: 'GPU 0 为什么不可用？' },
      { id: 'a1', role: 'assistant', content: 'GPU 0 当前被驱动标记为异常。' },
    ],
    runtimeSession: null,
    runtimeEvents: [],
  })

  assert.equal(view.leadMessage?.id, 'intro')
  assert.equal(view.interactions.length, 1)
  assert.equal(view.interactions[0].userMessage.content, 'GPU 0 为什么不可用？')
  assert.equal(view.interactions[0].assistantReply, 'GPU 0 当前被驱动标记为异常。')
  assert.equal(view.interactions[0].runtimeCards.length, 0)
  assert.equal(view.interactions[0].status, 'completed')
})

test('buildAgentWorkbenchThread attaches runtime cards to the latest user interaction', () => {
  const view = buildAgentWorkbenchThread({
    chatMessages: [
      { id: 'u1', role: 'user', content: '把 GPU 0 功耗限制到 220W' },
      { id: 'a1', role: 'assistant', content: '已进入执行链，正在生成计划。' },
    ],
    runtimeSession: {
      session_id: 's1',
      status: 'awaiting_approval',
      live_phase: 'awaiting_approval',
      goal_json: { raw_message: '把 GPU 0 功耗限制到 220W' },
    },
    runtimeEvents: [
      {
        event_type: 'PlanCreated',
        payload: { steps: [] },
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
    ],
  })

  assert.equal(view.interactions.length, 1)
  assert.equal(view.interactions[0].runtimeCards.length, 2)
  assert.equal(view.interactions[0].runtimeCards[0].kind, 'plan_card')
  assert.equal(view.interactions[0].runtimeCards[1].kind, 'approval_card')
  assert.equal(view.interactions[0].status, 'awaiting_approval')
})

test('buildAgentWorkbenchThread surfaces llm planning as an explicit interaction step', () => {
  const view = buildAgentWorkbenchThread({
    chatMessages: [
      { id: 'u1', role: 'user', content: '总结当前导入范围的 GPU 可用性、异常卡和风险，不执行操作。' },
    ],
    runtimeSession: {
      session_id: 's-llm',
      status: 'completed',
      live_phase: 'completed',
      goal_json: { raw_message: '总结当前导入范围的 GPU 可用性、异常卡和风险，不执行操作。' },
    },
    runtimeEvents: [
      {
        event_type: 'LLMRequestPrepared',
        payload: { summary: '已准备 LLM 结构化规划请求' },
        sequence: 1,
        timestamp: 1,
      },
      {
        event_type: 'LLMResponseReceived',
        payload: { summary: 'LLM 已返回结构化计划' },
        sequence: 2,
        timestamp: 2,
      },
      {
        event_type: 'PlanCreated',
        payload: { steps: [] },
        sequence: 3,
        timestamp: 3,
      },
    ],
  })

  assert.equal(view.interactions[0].runtimeCards[0].eventType, 'LLMRequestPrepared')
  assert.equal(view.interactions[0].runtimeCards[1].eventType, 'LLMResponseReceived')
  assert.deepEqual(
    view.interactions[0].steps.map((item) => item.key),
    ['llm', 'plan'],
  )
})

test('buildAgentWorkbenchThread splits consecutive user turns into separate interactions', () => {
  const view = buildAgentWorkbenchThread({
    chatMessages: [
      { id: 'u1', role: 'user', content: '先解释一下当前 GPU 状态' },
      { id: 'a1', role: 'assistant', content: '当前共有 3 张可用卡。' },
      { id: 'u2', role: 'user', content: '把 GPU 1 功耗限制到 240W' },
      { id: 'a2', role: 'assistant', content: '已进入执行链。' },
    ],
    runtimeSession: {
      session_id: 's2',
      status: 'running',
      live_phase: 'executing',
      goal_json: { raw_message: '把 GPU 1 功耗限制到 240W' },
    },
    runtimeEvents: [
      {
        event_type: 'PlanCreated',
        payload: { steps: [] },
        sequence: 1,
        timestamp: 1,
      },
    ],
  })

  assert.equal(view.interactions.length, 2)
  assert.equal(view.interactions[0].runtimeCards.length, 0)
  assert.equal(view.interactions[1].userMessage.content, '把 GPU 1 功耗限制到 240W')
  assert.equal(view.interactions[1].runtimeCards.length, 1)
})

test('buildAgentWorkbenchThread builds an interaction from runtime session message when chat history is empty', () => {
  const view = buildAgentWorkbenchThread({
    chatMessages: [
      { id: 'intro', role: 'assistant', content: '你好，我是 AI 治理助手。' },
    ],
    runtimeSession: {
      session_id: 's3',
      status: 'completed',
      live_phase: 'completed',
      goal_json: { raw_message: '执行一次公平性巡检' },
      summary: '执行一次公平性巡检',
    },
    runtimeEvents: [
      {
        event_type: 'SessionCompleted',
        payload: { summary: '巡检已完成' },
        sequence: 1,
        timestamp: 1,
      },
    ],
  })

  assert.equal(view.interactions.length, 1)
  assert.equal(view.interactions[0].userMessage.content, '执行一次公平性巡检')
  assert.equal(view.interactions[0].runtimeCards[0].kind, 'result_card')
})

test('buildAgentWorkbenchThread prefers the stored original request when runtime session summary has changed', () => {
  const view = buildAgentWorkbenchThread({
    chatMessages: [{ id: 'intro', role: 'assistant', content: '你好，我是 AI 治理助手。' }],
    runtimeSession: {
      session_id: 's4',
      status: 'completed',
      live_phase: 'completed',
      goal_json: { message: '把 GPU 0 的功耗上限调到 220W' },
      summary: 'GPU 0 功耗已更新',
    },
    runtimeEvents: [],
  })

  assert.equal(view.interactions.length, 1)
  assert.equal(view.interactions[0].userMessage.content, '把 GPU 0 的功耗上限调到 220W')
})

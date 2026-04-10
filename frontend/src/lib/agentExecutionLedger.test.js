import test from 'node:test'
import assert from 'node:assert/strict'

import { buildExecutionLedgerView } from './agentExecutionLedger.js'

test('buildExecutionLedgerView groups events by round and highlights critical cards', () => {
  const view = buildExecutionLedgerView({
    session: { session_id: 'sess-1', status: 'awaiting_approval' },
    events: [
      {
        event_type: 'LLMRequestPrepared',
        round_index: 1,
        sequence: 1,
        timestamp: 1,
        source: 'llm',
        payload: { summary: '准备请求' },
      },
      {
        event_type: 'LLMResponseReceived',
        round_index: 1,
        sequence: 2,
        timestamp: 2,
        source: 'llm',
        payload: { summary: '给出计划', response_preview: '...' },
      },
      {
        event_type: 'AwaitingApproval',
        round_index: 1,
        sequence: 3,
        timestamp: 3,
        source: 'approval',
        payload: { actions: [{ capability_name: 'scheduler.power_limit.set' }] },
      },
    ],
  })

  assert.equal(view.overview.llmCallCount, 1)
  assert.equal(view.rounds.length, 1)
  assert.equal(view.rounds[0].events[1].tone, 'llm')
  assert.equal(view.highlightedEvents[0].eventType, 'AwaitingApproval')
})

test('buildExecutionLedgerView counts llm attempts and surfaces llm failure highlights', () => {
  const view = buildExecutionLedgerView({
    session: { session_id: 'sess-2', status: 'completed' },
    events: [
      {
        event_type: 'LLMRequestPrepared',
        round_index: 1,
        sequence: 1,
        timestamp: 1,
        source: 'llm',
        payload: { summary: '准备请求' },
      },
      {
        event_type: 'LLMCallFailed',
        round_index: 1,
        sequence: 2,
        timestamp: 2,
        source: 'llm',
        payload: {
          summary: 'LLM 未返回有效结构化计划，切换到规则解析',
          error: 'LLM 返回的控制计划不是合法 JSON',
        },
      },
      {
        event_type: 'RuleFallbackUsed',
        round_index: 1,
        sequence: 3,
        timestamp: 3,
        source: 'planner',
        payload: { summary: '已切换到规则解析' },
      },
    ],
  })

  assert.equal(view.overview.llmCallCount, 1)
  assert.equal(
    view.highlightedEvents.some((event) => event.eventType === 'LLMCallFailed'),
    true,
  )
})

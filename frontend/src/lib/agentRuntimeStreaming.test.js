import test from 'node:test'
import assert from 'node:assert/strict'

import { reduceRuntimeStreamEvent } from './agentRuntimeStreaming.js'

test('reduceRuntimeStreamEvent appends runtime events and updates planner snapshot', () => {
  let state = {
    plannerLiveText: '',
    plannerLiveRevision: 0,
    runtimeEvents: [],
    runtimeSession: { status: 'running' },
  }

  state = reduceRuntimeStreamEvent(state, {
    event: 'planner_snapshot',
    data: { latest_text: '正在生成计划', revision: 1 },
  })
  state = reduceRuntimeStreamEvent(state, {
    event: 'runtime_event',
    data: { event_type: 'LLMRequestPrepared', payload: { summary: '准备请求' } },
  })

  assert.equal(state.plannerLiveText, '正在生成计划')
  assert.equal(state.runtimeEvents.length, 1)
})

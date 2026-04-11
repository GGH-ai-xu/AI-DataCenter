import test from 'node:test'
import assert from 'node:assert/strict'

import { buildTranscriptFromAgentEvents } from './agentWorkbenchEventTranscript.js'

test('buildTranscriptFromAgentEvents rebuilds chat transcript from backend events', () => {
  const transcript = buildTranscriptFromAgentEvents([
    {
      id: 1,
      event_type: 'UserMessageSubmitted',
      payload: { content: '你能查看当前任务吗' },
      round_index: 1,
      sequence: 0,
    },
    {
      id: 2,
      event_type: 'AssistantMessageGenerated',
      payload: {
        content: '可以，我能查看当前导入范围内的 GPU 进程。',
        suggestions: ['查看当前任务列表'],
      },
      round_index: 1,
      sequence: 1,
    },
  ])

  assert.deepEqual(transcript, [
    {
      id: 'event-1',
      role: 'user',
      content: '你能查看当前任务吗',
      suggestions: [],
      roundIndex: 1,
    },
    {
      id: 'event-2',
      role: 'assistant',
      content: '可以，我能查看当前导入范围内的 GPU 进程。',
      suggestions: ['查看当前任务列表'],
      roundIndex: 1,
    },
  ])
})

test('buildTranscriptFromAgentEvents ignores runtime-only events', () => {
  const transcript = buildTranscriptFromAgentEvents([
    {
      id: 1,
      event_type: 'LLMRequestPrepared',
      payload: { summary: '准备调用 LLM' },
      round_index: 1,
      sequence: 1,
    },
    {
      id: 2,
      event_type: 'SessionCompleted',
      payload: { summary: '执行完成' },
      round_index: 1,
      sequence: 2,
    },
  ])

  assert.deepEqual(transcript, [])
})

import test from 'node:test'
import assert from 'node:assert/strict'

import { buildAgentSessionHistory } from './agentSessionHistory.js'

test('buildAgentSessionHistory keeps compact title status and timestamp only', () => {
  const items = buildAgentSessionHistory([
    {
      session_id: 'sess-1',
      status: 'awaiting_approval',
      summary: '把 GPU 0 的功耗上限调到 220W',
      updated_at: 1700000000,
    },
  ])

  assert.equal(items[0].id, 'sess-1')
  assert.equal(items[0].title, '把 GPU 0 的功耗上限调到 220W')
  assert.equal(items[0].status, 'awaiting_approval')
  assert.equal(items[0].canDelete, true)
  assert.match(items[0].timeLabel, /\d{2}:\d{2}/)
})

test('buildAgentSessionHistory prefers the original user request over mutable session summary', () => {
  const items = buildAgentSessionHistory([
    {
      session_id: 'sess-2',
      status: 'completed',
      goal_json: { message: '把 GPU 0 的功耗上限调到 220W' },
      summary: 'GPU 0 功耗已更新',
      updated_at: 1700000000,
    },
  ])

  assert.equal(items[0].title, '把 GPU 0 的功耗上限调到 220W')
})

test('buildAgentSessionHistory marks running sessions as non-deletable', () => {
  const items = buildAgentSessionHistory([
    {
      session_id: 'sess-3',
      status: 'running',
      summary: '执行一次调度',
      updated_at: 1700000000,
    },
  ])

  assert.equal(items[0].canDelete, false)
})

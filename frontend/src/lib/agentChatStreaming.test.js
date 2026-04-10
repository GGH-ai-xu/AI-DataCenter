import test from 'node:test'
import assert from 'node:assert/strict'

import { reduceChatStreamEvent } from './agentChatStreaming.js'

test('reduceChatStreamEvent appends delta and overwrites snapshot', () => {
  let state = { text: '', suggestions: [] }
  state = reduceChatStreamEvent(state, { event: 'delta', data: { text: '你' } })
  state = reduceChatStreamEvent(state, { event: 'delta', data: { text: '好' } })
  state = reduceChatStreamEvent(state, {
    event: 'snapshot',
    data: { text: '你好，世界' },
  })

  assert.equal(state.text, '你好，世界')
})

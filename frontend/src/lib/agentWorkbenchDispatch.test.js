import test from 'node:test'
import assert from 'node:assert/strict'

import { resolveWorkbenchDispatchResult } from './agentWorkbenchDispatch.js'

test('resolveWorkbenchDispatchResult maps chat inline reply', () => {
  assert.deepEqual(
    resolveWorkbenchDispatchResult({
      route_kind: 'chat',
      reply_mode: 'inline',
      reply: '请先说明你要解释还是执行。',
    }),
    { kind: 'chat_inline', reply: '请先说明你要解释还是执行。' },
  )
})

test('resolveWorkbenchDispatchResult maps chat stream reply', () => {
  assert.deepEqual(
    resolveWorkbenchDispatchResult({
      route_kind: 'chat',
      reply_mode: 'stream',
    }),
    { kind: 'chat_stream' },
  )
})

test('resolveWorkbenchDispatchResult maps runtime reply', () => {
  assert.deepEqual(
    resolveWorkbenchDispatchResult({
      route_kind: 'runtime',
      message: '把 GPU 0 功耗限制到 220W',
    }),
    { kind: 'runtime', message: '把 GPU 0 功耗限制到 220W' },
  )
})

test('resolveWorkbenchDispatchResult rejects invalid payload', () => {
  assert.throws(
    () => resolveWorkbenchDispatchResult({ route_kind: 'chat' }),
    /AI 工作台判路结果无效/,
  )
})

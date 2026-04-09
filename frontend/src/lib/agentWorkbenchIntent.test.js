import test from 'node:test'
import assert from 'node:assert/strict'

import { resolveWorkbenchIntent } from './agentWorkbenchIntent.js'

test('resolveWorkbenchIntent routes clear runtime control requests to runtime', () => {
  assert.equal(resolveWorkbenchIntent('把 GPU 0 的功耗上限调到 220W').kind, 'runtime')
})

test('resolveWorkbenchIntent routes explanatory questions to chat', () => {
  assert.equal(resolveWorkbenchIntent('为什么当前有一张卡不可用？').kind, 'chat')
})

test('resolveWorkbenchIntent returns confirm for ambiguous inputs', () => {
  assert.equal(resolveWorkbenchIntent('帮我处理一下').kind, 'confirm')
})

import test from 'node:test'
import assert from 'node:assert/strict'

import { createAgentRuntimeSessionPolling } from './agentRuntimeSessionPolling.js'

test('polling stops when session reaches terminal state', async () => {
  let active = 0
  const calls = []
  const scheduler = {
    setInterval(fn) {
      active += 1
      calls.push(fn)
      return 'timer-1'
    },
    clearInterval(id) {
      active -= 1
      assert.equal(id, 'timer-1')
    },
  }
  const polling = createAgentRuntimeSessionPolling({ scheduler, intervalMs: 2000 })

  polling.start(() => Promise.resolve({ status: 'completed' }))
  await calls[0]()

  assert.equal(active, 0)
})

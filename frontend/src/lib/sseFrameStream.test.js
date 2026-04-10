import test from 'node:test'
import assert from 'node:assert/strict'

import { parseSseFrames } from './sseFrameStream.js'

test('parseSseFrames reconstructs split frames across chunks', async () => {
  const frames = []
  for await (const item of parseSseFrames([
    'event: delta\ndata: {"text":"你',
    '好"}\n\nevent: completed\ndata: {"ok":true}\n\n',
  ])) {
    frames.push(item)
  }

  assert.deepEqual(frames, [
    { event: 'delta', data: { text: '你好' } },
    { event: 'completed', data: { ok: true } },
  ])
})

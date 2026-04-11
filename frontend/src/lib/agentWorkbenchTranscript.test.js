import test from 'node:test'
import assert from 'node:assert/strict'

import {
  DRAFT_TRANSCRIPT_KEY,
  deleteSessionTranscript,
  loadSessionTranscript,
  moveTranscript,
  saveSessionTranscript,
} from './agentWorkbenchTranscript.js'

function createStorage() {
  const values = new Map()
  return {
    getItem(key) {
      return values.has(key) ? values.get(key) : null
    },
    setItem(key, value) {
      values.set(key, String(value))
    },
    removeItem(key) {
      values.delete(key)
    },
  }
}

test('agentWorkbenchTranscript saves and loads a session transcript', () => {
  const storage = createStorage()
  const transcript = [{ id: 'u1', role: 'user', content: '分析当前状态', suggestions: [], roundIndex: 1 }]

  saveSessionTranscript('sess-1', transcript, storage)

  assert.deepEqual(loadSessionTranscript('sess-1', storage), transcript)
})

test('agentWorkbenchTranscript moves draft transcript into a created session', () => {
  const storage = createStorage()
  const transcript = [{ id: 'u1', role: 'user', content: '把 GPU 0 限到 220W', suggestions: [], roundIndex: 1 }]
  saveSessionTranscript(DRAFT_TRANSCRIPT_KEY, transcript, storage)

  moveTranscript(DRAFT_TRANSCRIPT_KEY, 'sess-2', storage)

  assert.deepEqual(loadSessionTranscript('sess-2', storage), transcript)
  assert.deepEqual(loadSessionTranscript(DRAFT_TRANSCRIPT_KEY, storage), [])
})

test('agentWorkbenchTranscript deletes stored session transcript', () => {
  const storage = createStorage()
  saveSessionTranscript('sess-3', [{ id: 'a1', role: 'assistant', content: '已完成', roundIndex: 1 }], storage)

  deleteSessionTranscript('sess-3', storage)

  assert.deepEqual(loadSessionTranscript('sess-3', storage), [])
})

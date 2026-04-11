export const DRAFT_TRANSCRIPT_KEY = '__draft__'
const STORAGE_KEY = 'ai-workbench-transcripts'

function normalizeTranscript(messages = []) {
  return (messages || []).map((message) => ({
    id: String(message.id || ''),
    role: String(message.role || 'assistant'),
    content: String(message.content || ''),
    suggestions: [...(message.suggestions || [])],
    roundIndex: Number(message.roundIndex || 0),
  }))
}

function parseStore(storage) {
  const raw = storage?.getItem?.(STORAGE_KEY)
  if (!raw) return {}
  try {
    const parsed = JSON.parse(raw)
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
}

function writeStore(store, storage) {
  storage?.setItem?.(STORAGE_KEY, JSON.stringify(store))
}

function defaultStorage() {
  try {
    return window.localStorage || null
  } catch {
    return null
  }
}

export function loadSessionTranscript(sessionId, storage = defaultStorage()) {
  const key = String(sessionId || '').trim()
  if (!key) return []
  const store = parseStore(storage)
  return normalizeTranscript(store[key] || [])
}

export function saveSessionTranscript(sessionId, messages, storage = defaultStorage()) {
  const key = String(sessionId || '').trim()
  if (!key) return
  const store = parseStore(storage)
  store[key] = normalizeTranscript(messages)
  writeStore(store, storage)
}

export function moveTranscript(fromSessionId, toSessionId, storage = defaultStorage()) {
  const fromKey = String(fromSessionId || '').trim()
  const toKey = String(toSessionId || '').trim()
  if (!fromKey || !toKey || fromKey === toKey) return
  const store = parseStore(storage)
  store[toKey] = normalizeTranscript(store[fromKey] || [])
  delete store[fromKey]
  writeStore(store, storage)
}

export function deleteSessionTranscript(sessionId, storage = defaultStorage()) {
  const key = String(sessionId || '').trim()
  if (!key) return
  const store = parseStore(storage)
  delete store[key]
  writeStore(store, storage)
}

import test from 'node:test'
import assert from 'node:assert/strict'

import {
  clearSessionToken,
  readSessionToken,
  writeSessionToken,
} from './authSession.js'


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


test('session helpers persist and clear platform session token', () => {
  const storage = createStorage()

  assert.equal(readSessionToken(storage), '')
  writeSessionToken('session-token', storage)
  assert.equal(readSessionToken(storage), 'session-token')
  clearSessionToken(storage)
  assert.equal(readSessionToken(storage), '')
})

test('writeSessionToken removes empty values instead of storing blanks', () => {
  const storage = createStorage()

  writeSessionToken('   ', storage)

  assert.equal(readSessionToken(storage), '')
})

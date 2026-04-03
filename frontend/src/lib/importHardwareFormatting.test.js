import test from 'node:test'
import assert from 'node:assert/strict'

import { formatSystemMemoryBytes } from './importHardwareFormatting.js'

test('formatSystemMemoryBytes formats Linux system memory bytes as human-readable units', () => {
  assert.equal(formatSystemMemoryBytes(0), '未知')
  assert.equal(formatSystemMemoryBytes(134588776448), '125.3 GB')
  assert.equal(formatSystemMemoryBytes(2147483648), '2.0 GB')
})

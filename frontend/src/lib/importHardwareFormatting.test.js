import test from 'node:test'
import assert from 'node:assert/strict'

import {
  formatGpuMemoryBytes,
  formatGpuMemoryGiB,
  gpuMemoryUsagePercent,
  formatSystemMemoryBytes,
} from './importHardwareFormatting.js'

test('formatSystemMemoryBytes formats Linux system memory bytes as human-readable units', () => {
  assert.equal(formatSystemMemoryBytes(0), '未知')
  assert.equal(formatSystemMemoryBytes(134588776448), '125.3 GB')
  assert.equal(formatSystemMemoryBytes(2147483648), '2.0 GB')
})

test('formatGpuMemoryBytes supports SSH Linux MiB values and Agent byte values', () => {
  assert.equal(formatGpuMemoryBytes(0), '0 GB')
  assert.equal(formatGpuMemoryBytes(8192), '8.0 GB')
  assert.equal(formatGpuMemoryBytes(24564), '24.0 GB')
  assert.equal(formatGpuMemoryBytes(8192 * 1024 * 1024), '8.0 GB')
  assert.equal(formatGpuMemoryBytes(24564 * 1024 * 1024), '24.0 GB')
})

test('formatGpuMemoryGiB and gpuMemoryUsagePercent normalize MiB and byte payloads for dashboard cards', () => {
  assert.equal(formatGpuMemoryGiB(0), '0.0')
  assert.equal(formatGpuMemoryGiB(8192), '8.0')
  assert.equal(formatGpuMemoryGiB(24564), '24.0')
  assert.equal(formatGpuMemoryGiB(8192 * 1024 * 1024), '8.0')
  assert.equal(formatGpuMemoryGiB(24564 * 1024 * 1024), '24.0')
  assert.equal(gpuMemoryUsagePercent(4096, 24564), 17)
  assert.equal(gpuMemoryUsagePercent(4096 * 1024 * 1024, 24564 * 1024 * 1024), 17)
})

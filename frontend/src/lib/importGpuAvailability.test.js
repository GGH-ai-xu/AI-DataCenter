import test from 'node:test'
import assert from 'node:assert/strict'

import { isImportableGpu, selectableGpuIndexes } from './importGpuAvailability.js'


test('isImportableGpu treats explicit false as unavailable', () => {
  assert.equal(isImportableGpu({ index: 0, available: true }), true)
  assert.equal(isImportableGpu({ index: 1, available: false }), false)
  assert.equal(isImportableGpu({ index: 2 }), true)
})

test('selectableGpuIndexes keeps only available gpu indexes', () => {
  assert.deepEqual(
    selectableGpuIndexes([
      { index: 0, available: true },
      { index: 1, available: false },
      { index: 2 },
    ]),
    [0, 2],
  )
})

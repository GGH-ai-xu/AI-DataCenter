import test from 'node:test'
import assert from 'node:assert/strict'

import { syncExpandedPid, toggleExpandedPid } from './governanceTaskLedgerUi.js'

test('toggleExpandedPid keeps only one row open and collapses the active row', () => {
  assert.equal(toggleExpandedPid(null, 41), 41)
  assert.equal(toggleExpandedPid(41, 41), null)
  assert.equal(toggleExpandedPid(41, 52), 52)
})

test('syncExpandedPid closes detail when the expanded row is no longer visible', () => {
  assert.equal(syncExpandedPid(41, [{ pid: 41 }, { pid: 52 }]), 41)
  assert.equal(syncExpandedPid(41, [{ pid: 52 }]), null)
  assert.equal(syncExpandedPid(null, [{ pid: 52 }]), null)
})

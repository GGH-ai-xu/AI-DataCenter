import test from 'node:test'
import assert from 'node:assert/strict'

import { buildGovernanceReviewTimeline, formatAuditTime } from './governanceReviewModel.js'

test('buildGovernanceReviewTimeline maps logs into newest-first entries', () => {
  const timeline = buildGovernanceReviewTimeline([
    { action: 'pause_task', created_at: 1712560000, risk_level: 'medium', source: 'manual' },
    { action: 'run_schedule_once', created_at: 1712560300, risk_level: 'low', source: 'auto_schedule' },
  ])

  assert.equal(timeline[0].action, 'run_schedule_once')
  assert.equal(timeline[1].riskLabel, '中')
})

test('formatAuditTime returns hyphen for empty timestamps', () => {
  assert.equal(formatAuditTime(null), '-')
})

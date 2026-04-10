import test from 'node:test'
import assert from 'node:assert/strict'

import { buildGovernanceReviewTimeline, formatAuditTime } from './governanceReviewModel.js'

test('buildGovernanceReviewTimeline maps logs into newest-first entries', () => {
  const timeline = buildGovernanceReviewTimeline([
    { command_id: 'cmd-1', capability_name: 'tasks.pause', created_at: 1712560000, risk_level: 'control', source_page: 'governance-actions' },
    { command_id: 'cmd-2', capability_name: 'scheduler.run_once', created_at: 1712560300, risk_level: 'observe', source_page: 'governance-policies' },
  ])

  assert.equal(timeline[0].action, 'scheduler.run_once')
  assert.equal(timeline[1].riskLabel, '控制')
})

test('formatAuditTime returns hyphen for empty timestamps', () => {
  assert.equal(formatAuditTime(null), '-')
})

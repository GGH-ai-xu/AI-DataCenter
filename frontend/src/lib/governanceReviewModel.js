import { buildControlCommandTimeline } from './controlCapabilityModels.js'

function pad(value) {
  return String(value).padStart(2, '0')
}

export function formatAuditTime(ts) {
  if (!ts) return '-'
  const date = new Date(Number(ts) * 1000)
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

export function buildGovernanceReviewTimeline(commandRecords = []) {
  return buildControlCommandTimeline(commandRecords).map((item) => ({
    id: item.id,
    action: item.capabilityName,
    actionLabel: item.capabilityName || 'control-command',
    createdAtLabel: formatAuditTime(item.createdAt),
    riskLabel: item.riskLabel,
    sourceLabel: item.sourcePage || 'manual',
    result: item.state,
    approvalLabel: item.approvalLabel,
    resultSummary: item.resultSummary,
  }))
}

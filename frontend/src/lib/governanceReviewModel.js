const ACTION_LABELS = Object.freeze({
  pause_task: '暂停任务',
  resume_task: '恢复任务',
  terminate_task: '终止任务',
  set_power_limit: '压缩功耗',
  run_schedule_once: '综合调度',
})

const RISK_LABELS = Object.freeze({
  low: '低',
  medium: '中',
  high: '高',
})

const SOURCE_LABELS = Object.freeze({
  manual: '手动操作',
  ai_control: 'AI 助手工作台',
  auto_schedule: '自动调度',
})

function pad(value) {
  return String(value).padStart(2, '0')
}

export function formatAuditTime(ts) {
  if (!ts) return '-'
  const date = new Date(Number(ts) * 1000)
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

export function buildGovernanceReviewTimeline(logs = []) {
  return [...logs]
    .sort((left, right) => Number(right.created_at || right.ts || 0) - Number(left.created_at || left.ts || 0))
    .map((item) => ({
      id: `${item.created_at || item.ts}-${item.action}`,
      action: item.action,
      actionLabel: ACTION_LABELS[item.action] || item.action || '治理动作',
      createdAtLabel: formatAuditTime(item.created_at || item.ts),
      riskLabel: RISK_LABELS[item.risk_level] || '低',
      sourceLabel: SOURCE_LABELS[item.source] || item.source || 'manual',
      result: item.result || 'ok',
    }))
}

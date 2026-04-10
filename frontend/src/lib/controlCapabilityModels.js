const SECTION_DOMAINS = Object.freeze({
  actions: ['tasks', 'scheduler', 'runtime'],
  policies: ['scheduler', 'policy', 'queues'],
  cluster: ['jobs', 'queues'],
  review: null,
})

const COMMAND_STATE_LABELS = Object.freeze({
  queued: '排队中',
  awaiting_approval: '待审批',
  succeeded: '已完成',
  failed: '执行失败',
  rejected: '已拒绝',
})

const APPROVAL_STATE_LABELS = Object.freeze({
  not_required: '无需审批',
  approved: '已批准',
  pending: '待审批',
  rejected: '已拒绝',
})

const RISK_LEVEL_LABELS = Object.freeze({
  observe: '观察',
  operate: '操作',
  control: '控制',
  dangerous: '危险',
})

function pad(value) {
  return String(value).padStart(2, '0')
}

export function formatCommandTime(timestamp) {
  if (!timestamp) return '-'
  const date = new Date(Number(timestamp) * 1000)
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export function buildCapabilityDrawerModel(capabilities = [], section = 'actions') {
  const allowedDomains = SECTION_DOMAINS[section] || null
  const domainOrder = allowedDomains ? [...allowedDomains] : []
  const items = [...capabilities]
    .filter((item) => !allowedDomains || allowedDomains.includes(item.domain))
    .sort((left, right) => {
      const leftIndex = domainOrder.indexOf(left.domain)
      const rightIndex = domainOrder.indexOf(right.domain)
      if (leftIndex !== rightIndex) return leftIndex - rightIndex
      return String(left.label || left.name).localeCompare(String(right.label || right.name), 'zh-CN')
    })
    .map((item) => ({
      ...item,
      id: item.name,
      label: item.label || item.name,
      description: item.description || '',
    }))
  return { section, items }
}

export function buildControlCommandTimeline(commands = []) {
  return [...commands]
    .sort((left, right) => Number(right.created_at || 0) - Number(left.created_at || 0))
    .map((item) => ({
      id: item.command_id,
      commandId: item.command_id,
      capabilityName: item.capability_name || '',
      domain: item.domain || '',
      sourcePage: item.source_page || '',
      createdAt: Number(item.created_at || 0),
      createdAtLabel: formatCommandTime(item.created_at),
      state: item.execution_state || 'queued',
      stateLabel: COMMAND_STATE_LABELS[item.execution_state] || '处理中',
      approvalState: item.approval_state || 'not_required',
      approvalLabel: APPROVAL_STATE_LABELS[item.approval_state] || '未知',
      riskLevel: item.risk_level || 'observe',
      riskLabel: RISK_LEVEL_LABELS[item.risk_level] || '观察',
      resultSummary: item.result_summary || '',
      errorMessage: item.error_message || '',
      arguments: item.arguments || {},
    }))
}

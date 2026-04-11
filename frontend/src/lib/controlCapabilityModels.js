import {
  buildCapabilityFormArguments,
  buildCapabilityFormDraft,
  getCapabilityFormDefinition,
} from './controlCapabilityForms.js'

const SECTION_DOMAINS = Object.freeze({
  actions: ['tasks', 'scheduler', 'runtime'],
  policies: ['scheduler', 'policy', 'queues'],
  cluster: ['allocations', 'jobs', 'nodes', 'queues'],
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

const SOURCE_PAGE_LABELS = Object.freeze({
  'governance-actions': '即时处置',
  'governance-policies': '策略治理',
  'governance-cluster': '集群作业',
  'governance-review': '治理复盘',
})

function pad(value) {
  return String(value).padStart(2, '0')
}

function jsonPreview(value) {
  const normalized = value && typeof value === 'object' ? value : {}
  return JSON.stringify(normalized, null, 2)
}

function summarizeArguments(capabilityName, argumentsPayload = {}) {
  if (capabilityName === 'scheduler.power_limit.set') {
    return `GPU ${argumentsPayload.gpu_index} -> ${argumentsPayload.power_limit}W`
  }
  if (capabilityName === 'scheduler.auto.configure') {
    return argumentsPayload.enabled ? '启用自动调度' : '关闭自动调度'
  }
  if (capabilityName === 'scheduler.carbon_budget.configure') {
    return `${argumentsPayload.enabled ? '启用' : '关闭'} · ${argumentsPayload.daily_budget_kg}kg/日`
  }
  if (capabilityName === 'scheduler.budget.configure') {
    return `${argumentsPayload.enabled ? '启用' : '关闭'} · ${argumentsPayload.total_power_budget}W`
  }
  if (capabilityName.startsWith('job.')) {
    return argumentsPayload.job_id || capabilityName
  }
  if (capabilityName === 'allocation.release') {
    return argumentsPayload.allocation_id || capabilityName
  }
  if (capabilityName === 'node.drain' || capabilityName === 'node.undrain') {
    return argumentsPayload.node_id || capabilityName
  }
  if (capabilityName.startsWith('tasks.')) {
    return argumentsPayload.pid ? `PID ${argumentsPayload.pid}` : capabilityName
  }
  if (capabilityName === 'policy.user_rule.upsert') {
    return `${argumentsPayload.username || 'unknown'} · ${argumentsPayload.role || 'member'}`
  }
  if (capabilityName === 'policy.user_rule.delete') {
    return argumentsPayload.username || capabilityName
  }
  if (capabilityName === 'job.submit') {
    const request = argumentsPayload.resource_request || {}
    const ports = (argumentsPayload.service_ports || []).join(',')
    const portLabel = ports ? ` · 端口 ${ports}` : ''
    return `${argumentsPayload.job_id || 'job'} · ${argumentsPayload.task_kind || 'batch_compute'} · GPU ${request.gpu || 0} / CPU ${request.cpu || 0}${portLabel}`
  }
  const keys = Object.keys(argumentsPayload || {})
  if (!keys.length) return '无需参数'
  return keys
    .slice(0, 3)
    .map((key) => `${key}=${argumentsPayload[key]}`)
    .join(' · ')
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
      formDefinition: getCapabilityFormDefinition(item.name),
    }))
  return { section, items }
}

export function buildControlCommandTimeline(commands = []) {
  return [...commands]
    .sort((left, right) => Number(right.created_at || 0) - Number(left.created_at || 0))
    .map((item) => {
      const argumentsPayload = item.arguments || {}
      const approvalState = item.approval_state || 'not_required'
      const resultSummary = item.result_summary || ''
      const errorMessage = item.error_message || ''
      return {
        id: item.command_id,
        commandId: item.command_id,
        capabilityName: item.capability_name || '',
        domain: item.domain || '',
        sourcePage: item.source_page || '',
        sourceLabel: SOURCE_PAGE_LABELS[item.source_page] || '人工控制',
        createdAt: Number(item.created_at || 0),
        createdAtLabel: formatCommandTime(item.created_at),
        state: item.execution_state || 'queued',
        stateLabel: COMMAND_STATE_LABELS[item.execution_state] || '处理中',
        approvalState,
        approvalLabel: APPROVAL_STATE_LABELS[approvalState] || '未知',
        riskLevel: item.risk_level || 'observe',
        riskLabel: RISK_LEVEL_LABELS[item.risk_level] || '观察',
        resultSummary,
        errorMessage,
        arguments: argumentsPayload,
        argumentSummary: summarizeArguments(item.capability_name || '', argumentsPayload),
        argumentsPreview: jsonPreview(argumentsPayload),
        canApprove: approvalState === 'pending',
        hasDetails: Boolean(
          Object.keys(argumentsPayload).length
          || resultSummary
          || errorMessage
          || item.related_session_id,
        ),
      }
    })
}

export {
  buildCapabilityFormArguments,
  buildCapabilityFormDraft,
}

const BYTES_PER_GIB = 1073741824
const NON_MANAGEABLE_REASON = '该进程不建议执行治理动作。'
const MANAGEABLE_REASON = '可作为治理任务处理。'
const SYSTEM_CATEGORY = 'system'
const BACKGROUND_CATEGORY = 'background'

function toNumber(value) {
  return Number(value || 0)
}

function formatGiB(bytes) {
  return `${(bytes / BYTES_PER_GIB).toFixed(1)} GB`
}

export function isManageable(proc) {
  return proc?.manageable !== false
}

export function getManageableReason(proc) {
  if (proc?.manageable_reason) return proc.manageable_reason
  return isManageable(proc) ? MANAGEABLE_REASON : NON_MANAGEABLE_REASON
}

export function getReasonSummary(proc) {
  if (proc?.manageable_summary) return proc.manageable_summary
  if (proc?.process_category === SYSTEM_CATEGORY) return '系统图形'
  if (proc?.process_category === BACKGROUND_CATEGORY) return '背景陪跑'
  return '可治理任务'
}

export function getCategoryLabel(proc) {
  if (proc?.process_category === SYSTEM_CATEGORY) return '系统进程'
  if (proc?.process_category === BACKGROUND_CATEGORY) return '背景进程'
  return '可治理任务'
}

export function getCategoryClass(proc) {
  if (proc?.process_category === SYSTEM_CATEGORY) return 'status-badge--system'
  if (proc?.process_category === BACKGROUND_CATEGORY) return 'status-badge--background'
  return 'status-badge--ok'
}

export function displayGpuMemory(proc) {
  const used = toNumber(proc?.gpu_memory_used)
  if (!isManageable(proc) && used <= 0) return '低占用'
  return formatGiB(used)
}

export function displayCpuPercent(proc) {
  const cpu = toNumber(proc?.cpu_percent)
  if (!isManageable(proc) && cpu <= 0) return '空闲'
  return `${cpu.toFixed(1)}%`
}

export function gpuMetricTitle(proc) {
  const used = toNumber(proc?.gpu_memory_used)
  if (!isManageable(proc) && used <= 0) return '该进程当前没有检测到显著显存占用'
  return formatGiB(used)
}

export function cpuMetricTitle(proc) {
  const cpu = toNumber(proc?.cpu_percent)
  if (!isManageable(proc) && cpu <= 0) return '该进程当前没有检测到显著 CPU 活动'
  return `${cpu.toFixed(1)}%`
}

export function getCommandPreview(proc) {
  return String(proc?.command || '-').trim() || '-'
}

export function getActionHint(proc, flags = {}) {
  if (!isManageable(proc)) return '仅观察，不开放治理动作'
  if (!flags.isReal) return '当前治理台仅支持真实执行'
  if (flags.isReal && !flags.riskAcknowledged) return '确认风险后才会真实执行'
  return '将直接作用于真实进程'
}

export function createGovernanceTaskLedgerHelpers(flags = {}) {
  return {
    displayGpuMemory,
    displayCpuPercent,
    gpuMetricTitle,
    cpuMetricTitle,
    isManageable,
    getManageableReason,
    getReasonSummary,
    getCategoryLabel,
    getCategoryClass,
    getCommandPreview,
    getActionHint: (proc) => getActionHint(proc, flags),
  }
}

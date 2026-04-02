const DEFAULT_PRIORITY = 'normal'
const DEFAULT_USERNAME = 'unknown'
const HOT_GPU_THRESHOLD = 80
const CRITICAL_ALERT_LIMIT = 4

function normalizePriority(priority) {
  return priority || DEFAULT_PRIORITY
}

function normalizeUsername(username) {
  return username || DEFAULT_USERNAME
}

function buildProcessHaystack(process) {
  return [
    process.pid,
    process.name || '',
    normalizeUsername(process.username),
    process.command || '',
  ].join(' ').toLowerCase()
}

function compareProcesses(left, right) {
  const manageableDelta = Number(right.manageable) - Number(left.manageable)
  if (manageableDelta) {
    return manageableDelta
  }
  return right.gpu_memory_used - left.gpu_memory_used
}

export function buildDashboardSummary(input = {}) {
  const gpus = input.gpus || []
  const processes = input.processes || []
  const alerts = input.alerts || []
  const usernames = new Set()
  let urgentTasks = 0
  let deferrableTasks = 0
  let normalTasks = 0
  let hotGpuCount = 0

  for (const gpu of gpus) {
    if (Number(gpu.temperature || 0) >= HOT_GPU_THRESHOLD) {
      hotGpuCount += 1
    }
  }

  for (const process of processes) {
    usernames.add(normalizeUsername(process.username))
    const priority = normalizePriority(process.priority)
    if (priority === 'urgent') {
      urgentTasks += 1
      continue
    }
    if (priority === 'deferrable') {
      deferrableTasks += 1
      continue
    }
    normalTasks += 1
  }

  return {
    activeUsers: usernames.size,
    urgentTasks,
    deferrableTasks,
    normalTasks,
    hotGpuCount,
    criticalAlerts: alerts
      .filter((alert) => alert.severity === 'critical')
      .slice(0, CRITICAL_ALERT_LIMIT),
  }
}

export function normalizeProcesses(processes = []) {
  return [...processes]
    .map((process) => ({
      ...process,
      username: normalizeUsername(process.username),
      manageable: process.manageable !== false,
      priority: normalizePriority(process.priority),
      gpu_memory_used: Number(process.gpu_memory_used || 0),
      haystack: buildProcessHaystack(process),
    }))
    .sort(compareProcesses)
}

export function buildTaskSummary(processes = []) {
  const usernames = new Set()
  const summary = {
    manageableCount: 0,
    backgroundCount: 0,
    userCount: 0,
    urgentCount: 0,
    deferrableCount: 0,
    totalGpuMemory: 0,
  }

  for (const process of processes) {
    if (!process.manageable) {
      summary.backgroundCount += 1
      continue
    }

    summary.manageableCount += 1
    summary.totalGpuMemory += process.gpu_memory_used
    usernames.add(process.username)

    if (process.priority === 'urgent') {
      summary.urgentCount += 1
    }
    if (process.priority === 'deferrable') {
      summary.deferrableCount += 1
    }
  }

  return {
    ...summary,
    userCount: usernames.size,
  }
}

export function filterProcesses(processes = [], options = {}) {
  const priority = options.priority || 'all'
  const keyword = String(options.keyword || '').trim().toLowerCase()
  const visibleProcesses = selectVisibleProcesses(
    processes,
    Boolean(options.includeAll),
  )

  return visibleProcesses.filter((process) => {
    const matchesPriority = priority === 'all' || process.priority === priority
    const matchesKeyword = !keyword || process.haystack.includes(keyword)
    return matchesPriority && matchesKeyword
  })
}

export function selectVisibleProcesses(processes = [], includeAll = false) {
  if (includeAll) {
    return processes
  }
  return processes.filter((process) => process.manageable)
}

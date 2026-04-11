function normalizeJob(job = {}) {
  const readinessState = job.readiness_state || (job.status === 'ready' ? 'ready' : '')
  const status = job.status || 'queued'
  return {
    id: job.job_id || '',
    queueId: job.queue_id || 'default',
    status,
    dispatchState: status,
    entrypoint: job.entrypoint || '',
    priority: Number(job.priority || 0),
    submitter: job.submitter_id || '',
    taskKind: job.task_kind || 'batch_compute',
    lifecycleKind: job.lifecycle_kind || 'batch',
    servicePorts: [...(job.service_ports || [])],
    checkpointPolicy: job.checkpoint_policy || 'none',
    checkpointId: job.checkpoint_id || '',
    checkpointStatus: job.checkpoint_status || '',
    checkpointManifestPath: job.checkpoint_manifest_path || '',
    checkpointError: job.checkpoint_error || '',
    runtimeProfile: { ...(job.runtime_profile || {}) },
    readinessState,
    planType: job.last_plan_type || '',
    planReason: job.last_plan_reason || '',
    lastError: job.last_error || '',
    runtimeJobHandle: job.runtime_job_handle || '',
    canRequeue: ['running', 'paused', 'preempted'].includes(status),
    awaitingRelease: Boolean(job.has_releasing_allocation),
  }
}

function formatTimeLabel(timestamp) {
  if (!timestamp) return '未运行'
  const date = new Date(Number(timestamp) * 1000)
  const pad = (value) => String(value).padStart(2, '0')
  return `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

function summarizeController(controller = {}) {
  const summary = controller.last_summary || {}
  const parts = []
  if (summary.skipped) return summary.skip_reason || '最近一次已跳过'
  if (Number(summary.dispatched || 0) > 0) parts.push(`分发 ${summary.dispatched}`)
  if (Number(summary.completed || 0) > 0) parts.push(`完成 ${summary.completed}`)
  if (Number(summary.released || 0) > 0) parts.push(`回收 ${summary.released}`)
  if (Number(summary.failed || 0) > 0) parts.push(`失败 ${summary.failed}`)
  return parts.join(' · ') || '暂无最近结果'
}

function normalizeController(controller = {}) {
  return {
    enabled: Boolean(controller.enabled),
    running: Boolean(controller.running),
    intervalSeconds: Number(controller.interval_seconds || 0),
    intervalLabel: controller.interval_seconds ? `每 ${Number(controller.interval_seconds)}s` : '未设置',
    lastRunLabel: formatTimeLabel(controller.last_finished_at),
    summaryLabel: summarizeController(controller),
    lastError: controller.last_error || '',
    lastSkipReason: controller.last_skip_reason || '',
    toggleLabel: controller.enabled ? '关闭自动调和' : '开启自动调和',
  }
}

function summarizeBlockedJobs(jobs = []) {
  const blocked = jobs.filter((job) => ['wait', 'hold', 'reject'].includes(job.planType))
  if (!blocked.length) {
    return {
      blockedJobs: 0,
      waitReasonSummary: '',
    }
  }
  return {
    blockedJobs: blocked.length,
    waitReasonSummary: `最近阻塞：${blocked[0].planReason}`,
  }
}

function concurrencyLabel(maxConcurrency) {
  return maxConcurrency > 0 ? `并发上限 ${maxConcurrency}` : '不限并发'
}

function normalizeQueue(queue = {}, jobs = []) {
  const queueJobs = jobs.filter((job) => job.queueId === (queue.queue_id || 'default'))
  const maxConcurrency = Number(queue.max_concurrency || 0)
  const blockedSummary = summarizeBlockedJobs(queueJobs)
  return {
    id: queue.queue_id || 'default',
    name: queue.name || queue.queue_id || 'Default',
    state: queue.state || 'active',
    defaultPriority: Number(queue.default_priority || 0),
    maxConcurrency,
    concurrencyLabel: concurrencyLabel(maxConcurrency),
    queuedJobs: queueJobs.filter((job) => ['queued', 'pending'].includes(job.status)).length,
    runningJobs: queueJobs.filter((job) => ['running', 'ready'].includes(job.status)).length,
    dispatchingJobs: queueJobs.filter((job) => job.dispatchState === 'dispatching').length,
    failedJobs: queueJobs.filter((job) => job.dispatchState === 'failed').length,
    blockedJobs: blockedSummary.blockedJobs,
    waitReasonSummary: blockedSummary.waitReasonSummary,
  }
}

function normalizeAllocation(allocation = {}) {
  return {
    id: allocation.allocation_id || '',
    nodeId: allocation.node_id || 'unknown-node',
    jobId: allocation.job_id || '',
    status: allocation.status || 'active',
    releaseable: (allocation.status || 'active') === 'active',
  }
}

function normalizeNode(node = {}) {
  return {
    id: node.node_id || '',
    label: node.label || node.node_id || 'unknown-node',
    state: node.state || 'ready',
    drainState: node.drain_state || 'active',
  }
}

function groupAllocationsByNode(allocations = []) {
  const grouped = new Map()
  allocations.forEach((allocation) => {
    const nodeId = allocation.nodeId
    const bucket = grouped.get(nodeId) || []
    bucket.push(allocation)
    grouped.set(nodeId, bucket)
  })
  return Array.from(grouped.entries()).map(([nodeId, items]) => ({
    nodeId,
    allocations: items,
  }))
}

export function buildClusterConsoleModel(payload = {}) {
  const jobs = (payload.jobs || []).map((item) => normalizeJob(item))
  const queues = (payload.queues || []).map((item) => normalizeQueue(item, jobs))
  const allocations = (payload.allocations || []).map((item) => normalizeAllocation(item))
  const nodes = (payload.nodes || []).map((item) => normalizeNode(item))
  return {
    controller: normalizeController(payload.controller || {}),
    queues,
    jobs,
    nodes,
    allocationsByNode: groupAllocationsByNode(allocations),
  }
}

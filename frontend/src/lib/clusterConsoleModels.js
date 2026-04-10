function normalizeJob(job = {}) {
  return {
    id: job.job_id || '',
    queueId: job.queue_id || 'default',
    status: job.status || 'queued',
    entrypoint: job.entrypoint || '',
    priority: Number(job.priority || 0),
    submitter: job.submitter_id || '',
  }
}

function normalizeQueue(queue = {}, jobs = []) {
  const queueJobs = jobs.filter((job) => job.queueId === (queue.queue_id || 'default'))
  return {
    id: queue.queue_id || 'default',
    name: queue.name || queue.queue_id || 'Default',
    state: queue.state || 'active',
    defaultPriority: Number(queue.default_priority || 0),
    queuedJobs: queueJobs.filter((job) => ['queued', 'pending'].includes(job.status)).length,
    runningJobs: queueJobs.filter((job) => job.status === 'running').length,
  }
}

function normalizeAllocation(allocation = {}) {
  return {
    id: allocation.allocation_id || '',
    nodeId: allocation.node_id || 'unknown-node',
    jobId: allocation.job_id || '',
    status: allocation.status || 'active',
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
  return {
    queues,
    jobs,
    allocationsByNode: groupAllocationsByNode(allocations),
  }
}

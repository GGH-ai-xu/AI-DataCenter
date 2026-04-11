const ACTION_CAPABILITIES = Object.freeze({
  pause: 'job.pause',
  resume: 'job.resume',
  checkpoint: 'job.checkpoint',
  restore: 'job.restore',
  cancel: 'job.cancel',
  requeue: 'job.requeue',
  preempt: 'job.preempt',
})

const ACTION_LABELS = Object.freeze({
  pause: '暂停',
  resume: '恢复',
  checkpoint: '检查点',
  restore: '恢复',
  cancel: '取消',
  requeue: '重新入队',
  preempt: '抢占',
})

export function actionBusyKey(jobId, action) {
  return `${jobId}:${action}`
}

export function capabilityForJobAction(action) {
  const capability = ACTION_CAPABILITIES[action]
  if (!capability) {
    throw new Error(`unknown cluster job action: ${action}`)
  }
  return capability
}

export function jobActionLabel(action) {
  const label = ACTION_LABELS[action]
  if (!label) {
    throw new Error(`unknown cluster job action: ${action}`)
  }
  return label
}

export function availableJobActions(job = {}) {
  const status = job.status
  const isBatchJob = job.lifecycleKind === 'batch'
  if ((status === 'running' || status === 'ready') && isBatchJob) {
    return ['pause', 'checkpoint', 'requeue', 'preempt', 'cancel']
  }
  if (status === 'running' || status === 'ready') return ['cancel']
  if (status === 'paused') {
    return isBatchJob ? ['resume', 'checkpoint', 'requeue', 'cancel'] : ['resume', 'cancel']
  }
  if (status === 'preempted' && job.canRequeue) {
    return job.checkpointStatus === 'checkpoint_ready' ? ['restore', 'requeue'] : ['requeue']
  }
  if (status === 'checkpoint_ready') return ['restore', 'requeue']
  if (status === 'queued' || status === 'pending') return ['cancel']
  return []
}

export function confirmJobAction(jobId, action) {
  return window.confirm(`将${jobActionLabel(action)}作业 ${jobId}，是否继续？`)
}

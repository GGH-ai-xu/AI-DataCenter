const DEFAULT_BUDGET = Object.freeze({
  enabled: false,
  total_power_budget: 1200,
  current_total_power: 0,
  remaining_power: 1200,
  usage_pct: 0,
  is_exceeded: false,
  managed_gpu_count: 0,
  last_actions: [],
})

const DEFAULT_CARBON = Object.freeze({
  enabled: false,
  daily_budget_kg: 50,
  accumulated_carbon_kg: 0,
  accumulated_kwh: 0,
  usage_pct: 0,
  is_exceeded: false,
  projected_daily_carbon_kg: 0,
  current_power_w: 0,
  hours_elapsed: 0,
})

export function applyBudgetState(nextBudget = {}) {
  return {
    ...DEFAULT_BUDGET,
    ...nextBudget,
  }
}

export function applyCarbonState(current = {}, next = {}) {
  return {
    ...DEFAULT_CARBON,
    ...current,
    ...next,
  }
}

export function formatActionTarget(action) {
  if (action?.target?.gpu_index !== undefined) return `GPU ${action.target.gpu_index}`
  if (action?.target?.pid !== undefined) return `PID ${action.target.pid}`
  return '集群'
}

export function formatActionLabel(action) {
  if (action?.action === 'set_power_limit') return '压缩功耗'
  if (action?.action === 'pause_task') return '暂停任务'
  if (action?.action === 'resume_task') return '恢复任务'
  return action?.action || '调度动作'
}

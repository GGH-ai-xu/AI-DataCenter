const KIND_CONFIG = Object.freeze({
  budget: {
    valueKey: 'total_power_budget',
    actionLabel: '应用预算修改',
  },
  carbon: {
    valueKey: 'daily_budget_kg',
    actionLabel: '应用碳预算',
  },
})

function normalizeNumber(value) {
  return Number(value || 0)
}

function isPendingChange(current = {}, draft = {}, valueKey) {
  return Boolean(current.enabled) !== Boolean(draft.enabled)
    || normalizeNumber(current[valueKey]) !== normalizeNumber(draft[valueKey])
}

export function buildDraftCardState({ kind, current = {}, draft = {} }) {
  const config = KIND_CONFIG[kind]
  const pending = isPendingChange(current, draft, config.valueKey)
  return {
    pending,
    badgeLabel: pending ? '待应用' : '已同步',
    badgeTone: pending ? 'pending' : 'ok',
    actionLabel: config.actionLabel,
    actionTone: pending ? 'primary' : 'quiet',
  }
}

export function buildExecutionBannerModel(options = {}) {
  const {
    actionLabel = '',
    isReal = false,
    riskAcknowledged = false,
    reversible = false,
  } = options

  if (!isReal || riskAcknowledged) {
    return {
      tone: 'ok',
      detail: `${actionLabel}可直接执行。`,
      confirmRequired: false,
    }
  }

  return {
    tone: reversible ? 'warning' : 'critical',
    detail: `${actionLabel}前请先确认风险。`,
    confirmRequired: !reversible,
  }
}

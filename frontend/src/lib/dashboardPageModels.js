import { formatImportedGpuLabel } from './importContext.js'

const ROUTE_CARDS = [
  { label: '进入治理台', desc: '预算、限功率与调度动作', path: '/scheduler' },
  { label: '进入任务台', desc: '暂停、恢复、终止导入范围内任务', path: '/tasks' },
  { label: '进入风险台', desc: '处理导入范围内告警', path: '/alerts' },
  { label: '进入复盘台', desc: '查看节能测算与历史效果', path: '/energy' },
]

function buildBudgetSignal(budget = {}, criticalAlertCount = 0) {
  if (budget.is_exceeded) {
    return {
      tone: 'critical',
      label: '预算超限',
      detail: `当前预算占用 ${budget.usage_pct || 0}%`,
    }
  }
  if (criticalAlertCount > 0) {
    return {
      tone: 'warning',
      label: '存在严重告警',
      detail: `当前有 ${criticalAlertCount} 条严重告警`,
    }
  }
  return {
    tone: 'ok',
    label: '预算稳定',
    detail: '当前功率预算处于可控范围内',
  }
}

function buildFairnessSignal(fairnessOverview = {}) {
  const tone = fairnessOverview.level === 'critical'
    ? 'critical'
    : fairnessOverview.level === 'watch'
      ? 'warning'
      : 'ok'
  const label = fairnessOverview.level === 'critical'
    ? '公平紧张'
    : fairnessOverview.level === 'watch'
      ? '公平观察'
      : '公平稳定'
  return {
    tone,
    label,
    detail: `活跃用户 ${fairnessOverview.active_users || 0} 人，最高占用 ${fairnessOverview.highest_share_pct || 0}%`,
  }
}

export function buildDashboardOverviewModel(input = {}) {
  const importedLabel = formatImportedGpuLabel(input.importedIndexes || [])
  const budgetSignal = buildBudgetSignal(input.budget, input.criticalAlertCount)
  return {
    summaryLine: budgetSignal.detail,
    quickStats: [
      { label: '导入范围', value: importedLabel, hint: input.sourceMode === 'remote' ? '远程导入' : '本机导入' },
      { label: '连接状态', value: input.wsConnected ? '实时在线' : '实时离线', hint: input.workspaceReady ? '控制台已绑定导入范围' : '等待重新导入' },
      { label: '预算风险', value: budgetSignal.label, hint: budgetSignal.detail },
      { label: '严重告警', value: String(input.criticalAlertCount || 0), hint: `${input.processCount || 0} 个实时任务` },
    ],
    routeCards: ROUTE_CARDS,
    signalCards: [
      budgetSignal,
      {
        tone: input.criticalAlertCount > 0 ? 'warning' : 'ok',
        label: input.criticalAlertCount > 0 ? '优先处理告警' : '告警平稳',
        detail: input.criticalAlertCount > 0 ? `当前有 ${input.criticalAlertCount} 条严重告警` : '当前没有严重告警',
      },
      buildFairnessSignal(input.fairnessOverview),
    ],
  }
}

export function buildDashboardHealthModel(input = {}) {
  const checks = input.selfCheck?.checks || []
  return {
    summary: input.selfCheck?.summary || { title: '等待巡检', message: '当前还没有巡检结果。' },
    factCards: [
      { label: '导入范围', value: input.importedLabel || '未导入 GPU' },
      { label: '实时连接', value: input.wsConnected ? '在线' : '离线' },
      { label: 'AI 助手', value: input.selfCheck?.llm_available ? '已启用' : '未启用' },
      { label: 'WebSocket', value: `${Number(input.selfCheck?.ws_connections || 0)} 条` },
    ],
    priorityChecks: checks.filter((item) => item.status === 'critical' || item.status === 'warning'),
    healthyChecks: checks.filter((item) => item.status === 'ok'),
  }
}

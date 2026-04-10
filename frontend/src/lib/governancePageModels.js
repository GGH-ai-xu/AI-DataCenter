const DEFAULT_RULE = {
  role: 'member',
  max_tasks: 4,
  max_gpu_count: 1,
  max_memory_gb: 8,
  allow_preempt: true,
  note: '',
}

function stat(label, value, hint) {
  return {
    label,
    value: String(value),
    hint,
  }
}

export const GOVERNANCE_TABS = Object.freeze([
  { key: 'actions', label: '即时处置', desc: '处理对象' },
  { key: 'policies', label: '策略治理', desc: '调整策略' },
  { key: 'cluster', label: '集群作业', desc: '队列与分配' },
  { key: 'review', label: '治理复盘', desc: '查看结果' },
])

export function buildGovernanceReviewModel(input = {}) {
  const commandRecords = input.commandRecords || []
  const evaluation = input.evaluation || {}
  return {
    summary: {
      totalActions: commandRecords.length,
      failedActions: commandRecords.filter((item) => item.execution_state === 'failed').length,
      fairnessDelta: Number(evaluation.fairness_delta || 0),
    },
    timeline: commandRecords.slice(0, 12).map((item) => ({
      id: item.command_id || `${item.created_at || 0}-${item.capability_name || 'control-command'}`,
      title: item.capability_name || 'control-command',
      tone: item.risk_level || 'observe',
      createdAt: item.created_at || 0,
    })),
  }
}

export function buildGovernanceHeaderModel(section, input = {}) {
  if (section === 'policies') {
    const budget = input.scheduler?.budget || {}
    const carbon = input.carbon || {}
    return {
      title: '策略治理',
      description: '这一页只负责预算、调度与高级治理策略。',
      quickStats: [
        stat('功率预算', budget.total_power_budget || 0, `当前占用 ${budget.usage_pct || 0}%`),
        stat('碳预算', carbon.daily_budget_kg || 0, `当前占用 ${carbon.usage_pct || 0}%`),
        stat('自动调度', input.scheduler?.auto_enabled ? '开启' : '关闭', '系统级调度动作统一在此执行'),
      ],
    }
  }

  if (section === 'review') {
    const review = buildGovernanceReviewModel(input)
    return {
      title: '治理复盘',
      description: '这一页只负责结果追溯、评估与导出。',
      quickStats: [
        stat('治理动作', review.summary.totalActions, '最近 72 小时审计记录'),
        stat('失败动作', review.summary.failedActions, '需要优先回看失败项'),
        stat('公平变化', review.summary.fairnessDelta, '调度评估摘要'),
      ],
    }
  }

  if (section === 'cluster') {
    return {
      title: '集群作业',
      description: '这一页只负责队列、作业提交与分配快照，不再混入 PID 级处置。',
      quickStats: [
        stat('默认队列', 'default', 'Phase 1 先以单默认队列打通闭环'),
        stat('调度模式', '单节点放置', '后续再扩展抢占、迁移和多队列'),
        stat('执行后端', 'Node Runtime', '通过 reservation + launch 落地作业'),
      ],
    }
  }

  const taskSummary = input.taskSummary || {}
  const fairnessOverview = input.fairnessOverview || {}
  return {
    title: '即时处置',
    description: '这一页只做筛选、分级和执行，不承担预算与审计。',
    quickStats: [
      stat('可治理任务', taskSummary.manageableCount ?? 0, '当前允许直接执行治理动作的任务'),
      stat('紧急任务', taskSummary.urgentCount ?? 0, '预算紧张时优先保障'),
      stat('让路候选', fairnessOverview.reclaimable_candidates ?? 0, fairnessOverview.level || '当前共享稳定'),
    ],
  }
}

export function buildGovernanceRulesModel(input = {}) {
  const users = input.users || []
  const rules = input.rules || []
  const ruleMap = new Map(rules.map((rule) => [rule.username, rule]))
  const mergedUsers = users.map((user) => {
    const storedRule = ruleMap.get(user.username)
    const governanceRule = storedRule || user.governance_rule || { ...DEFAULT_RULE }
    const violationCount = Number(user.violation_count || 0)
    return {
      ...user,
      governance_rule: governanceRule,
      hasStoredRule: Boolean(storedRule),
      workloadSummary: `${user.task_count || 0} 个任务 · ${user.gpu_count || 0} 张GPU`,
      violationLabel: violationCount > 0 ? `违规 ${violationCount}` : '规则内',
    }
  })

  const violatedUsers = mergedUsers.filter((user) => Number(user.violation_count || 0) > 0).length
  const coveragePct = mergedUsers.length ? Math.round((rules.length / mergedUsers.length) * 100) : 0

  return {
    users: mergedUsers,
    summary: {
      activeUsers: mergedUsers.length,
      violatedUsers,
      coveragePct,
    },
  }
}

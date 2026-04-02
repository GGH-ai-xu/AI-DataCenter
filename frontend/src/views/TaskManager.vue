<script setup>
import { computed, ref, watch } from 'vue'
import {
  deleteGovernanceRule,
  exportGovernanceReport,
  pauseTask,
  resumeTask,
  saveGovernanceRule,
  setTaskPriority,
  terminateTask,
} from '../services/api'
import { exportTextFile } from '../services/desktopExport'
import WorkspacePaneLayout from '../components/workspace/WorkspacePaneLayout.vue'
import WorkspaceSummary from '../components/workspace/WorkspaceSummary.vue'
import WorkspaceTabs from '../components/workspace/WorkspaceTabs.vue'
import { useTaskManagerData } from '../composables/useTaskManagerData.js'

const activeTab = ref('actions')
const keyword = ref('')
const selectedPriority = ref('all')
const showAllProcesses = ref(false)
const executionMode = ref('dry_run')
const riskAcknowledged = ref(false)
const exporting = ref(false)
const actionNotice = ref(null)
const actionLoading = ref({})
const ruleSaving = ref({})
const ruleDrafts = ref({})
const taskTabs = [
  { key: 'actions', label: '待处置任务', desc: '筛选与执行' },
  { key: 'fairness', label: '公平治理', desc: '占用结构与让路建议' },
  { key: 'rules', label: '规则配置', desc: '用户额度与角色' },
]
const {
  filteredProcesses,
  visibleProcesses,
  fairnessState,
  taskSummary,
  refreshTaskGovernance,
} = useTaskManagerData(keyword, selectedPriority, showAllProcesses)

const priorityColors = {
  urgent: { bg: 'rgba(196,30,58,0.12)', color: '#C41E3A', label: '紧急' },
  normal: { bg: 'rgba(58,95,75,0.12)', color: '#3A5F4B', label: '普通' },
  deferrable: { bg: 'rgba(148,163,184,0.12)', color: '#666666', label: '可延迟' },
}

const roleOptions = {
  protected: '保护用户',
  member: '普通用户',
  restricted: '受限用户',
}

const fmtMem = (bytes) => `${((bytes || 0) / 1073741824).toFixed(1)} GB`

function displayGpuMemory(proc) {
  const used = Number(proc?.gpu_memory_used || 0)
  if (!isManageable(proc) && used <= 0) return '低占用'
  return fmtMem(used)
}

function displayCpuPercent(proc) {
  const cpu = Number(proc?.cpu_percent || 0)
  if (!isManageable(proc) && cpu <= 0) return '空闲'
  return `${cpu.toFixed(1)}%`
}

function gpuMetricTitle(proc) {
  const used = Number(proc?.gpu_memory_used || 0)
  if (!isManageable(proc) && used <= 0) return '该进程当前没有检测到显著显存占用'
  return fmtMem(used)
}

function cpuMetricTitle(proc) {
  const cpu = Number(proc?.cpu_percent || 0)
  if (!isManageable(proc) && cpu <= 0) return '该进程当前没有检测到显著 CPU 活动'
  return `${cpu.toFixed(1)}%`
}

function isManageable(proc) {
  return proc?.manageable !== false
}

function getManageableReason(proc) {
  if (proc?.manageable_reason) return proc.manageable_reason
  return isManageable(proc) ? '可作为治理任务处理。' : '该进程不建议执行治理动作。'
}

function getReasonSummary(proc) {
  if (proc?.manageable_summary) return proc.manageable_summary
  if (proc?.process_category === 'system') return '系统图形'
  if (proc?.process_category === 'background') return '背景陪跑'
  return '可治理任务'
}

function getCategoryLabel(proc) {
  if (proc?.process_category === 'system') return '系统进程'
  if (proc?.process_category === 'background') return '背景进程'
  return '可治理任务'
}

function getCategoryClass(proc) {
  if (proc?.process_category === 'system') return 'status-badge--system'
  if (proc?.process_category === 'background') return 'status-badge--background'
  return 'status-badge--ok'
}

function setActionNotice(tone, title, detail) {
  actionNotice.value = { tone, title, detail }
}

const fairnessOverview = computed(() => fairnessState.value.overview || {})
const fairnessUsers = computed(() => fairnessState.value.users || [])
const yieldCandidates = computed(() => fairnessState.value.yield_candidates || [])

const fairnessGaugeColor = computed(() => {
  const idx = fairnessOverview.value.fairness_index ?? 100
  if (idx >= 70) return '#2E8B57'
  if (idx >= 40) return '#B8860B'
  return '#C41E3A'
})
const fairnessGaugeBg = computed(() => {
  const idx = fairnessOverview.value.fairness_index ?? 100
  if (idx >= 70) return 'rgba(46,139,87,0.08)'
  if (idx >= 40) return 'rgba(184,134,11,0.08)'
  return 'rgba(196,30,58,0.08)'
})
const fairnessLevelLabel = computed(() => {
  const level = fairnessOverview.value.level || 'balanced'
  return { balanced: '均衡', moderate: '轻度倾斜', skewed: '显著倾斜', critical: '严重不均' }[level] || level
})
const manageableProcessCount = computed(() => taskSummary.value.manageableCount)
const backgroundProcessCount = computed(() => taskSummary.value.backgroundCount)
const userCount = computed(() => taskSummary.value.userCount)
const urgentCount = computed(() => taskSummary.value.urgentCount)
const deferrableCount = computed(() => taskSummary.value.deferrableCount)
const totalGpuMemory = computed(() => taskSummary.value.totalGpuMemory)
const executionSummary = computed(() =>
  executionMode.value === 'real'
    ? (riskAcknowledged.value
      ? '当前为真实执行模式，操作会直接作用于可治理 GPU 任务。'
      : '当前为真实执行模式，但还未确认风险，按钮会保持禁用。')
    : '当前为演练模式，只生成预演结果，不会改动真实进程。'
)

function buildRuleDraft(user) {
  const rule = user.governance_rule || {}
  return {
    role: rule.role || 'member',
    max_tasks: rule.max_tasks ?? 4,
    max_gpu_count: rule.max_gpu_count ?? 1,
    max_memory_gb: rule.max_memory_gb ?? 8,
    allow_preempt: rule.allow_preempt ?? true,
    note: rule.note || '',
  }
}

function syncRuleDrafts(users) {
  const next = { ...ruleDrafts.value }
  for (const user of users || []) {
    next[user.username] = buildRuleDraft(user)
  }
  ruleDrafts.value = next
}

async function loadTaskGovernance() {
  try {
    await refreshTaskGovernance({ force: true })
  } catch (error) {
    console.error(error)
  }
}

watch(
  fairnessUsers,
  (users) => {
    syncRuleDrafts(users)
  },
  { immediate: true },
)

function buildActionOptions() {
  const isReal = executionMode.value === 'real'
  return {
    dry_run: !isReal,
    acknowledge_risk: isReal && riskAcknowledged.value,
  }
}

function isActionDisabled(proc, action) {
  if (!isManageable(proc)) return true
  if (executionMode.value === 'real' && !riskAcknowledged.value) return true
  return Boolean(actionLoading.value[`${proc.pid}-${action}`])
}

function getActionHint(proc) {
  if (!isManageable(proc)) return '仅观察，不开放治理动作'
  if (executionMode.value === 'dry_run') return '演练模式，不改动真实进程'
  if (!riskAcknowledged.value) return '确认风险后才会真实执行'
  return '将直接作用于真实进程'
}

function getCommandPreview(proc) {
  const command = (proc?.command || '-').trim()
  if (command.length <= 56) return command
  return `${command.slice(0, 53).trimEnd()}...`
}

async function doAction(proc, action) {
  if (!isManageable(proc)) {
    setActionNotice('warning', '当前进程不可治理', getManageableReason(proc))
    return
  }
  if (executionMode.value === 'real' && !riskAcknowledged.value) {
    setActionNotice('warning', '尚未确认风险', '真实执行前请先勾选风险确认。')
    return
  }
  if (executionMode.value === 'real' && action === 'terminate' && !window.confirm(`将终止真实进程 PID ${proc.pid}，是否继续？`)) {
    return
  }

  actionLoading.value[`${proc.pid}-${action}`] = true
  try {
    const options = buildActionOptions()
    let response = null
    if (action === 'pause') response = await pauseTask(proc.pid, options)
    else if (action === 'resume') response = await resumeTask(proc.pid, options)
    else if (action === 'terminate') response = await terminateTask(proc.pid, options)

    const data = response?.data || {}
    if (data.dry_run) {
      setActionNotice('warning', '已生成演练结果', data.message || `已完成 PID ${proc.pid} 的动作预演。`)
    } else {
      const actionLabel = action === 'pause' ? '暂停' : action === 'resume' ? '恢复' : '终止'
      const detail = data.message || `${actionLabel}指令已发送到 PID ${proc.pid}`
      const suffix = action === 'terminate' && data.forced ? '，进程对普通终止无响应，已执行强制结束。' : '。'
      setActionNotice('ok', '真实动作已执行', `${detail}${suffix}`)
    }
  } catch (error) {
    console.error(error)
    setActionNotice(
      'critical',
      '动作执行失败',
      error?.response?.data?.detail || error?.message || '任务动作执行失败',
    )
  } finally {
    actionLoading.value[`${proc.pid}-${action}`] = false
  }
  await loadTaskGovernance()
}

async function changePriority(proc, priority) {
  if (!isManageable(proc)) {
    setActionNotice('warning', '当前进程不可分级', getManageableReason(proc))
    return
  }
  try {
    await setTaskPriority(proc.pid, priority)
    await loadTaskGovernance()
  } catch (error) {
    console.error(error)
  }
}

async function saveRuleForUser(user) {
  const draft = ruleDrafts.value[user.username]
  if (!draft) return
  ruleSaving.value[user.username] = true
  try {
    await saveGovernanceRule({
      username: user.username,
      role: draft.role,
      max_tasks: Number(draft.max_tasks),
      max_gpu_count: Number(draft.max_gpu_count),
      max_memory_gb: Number(draft.max_memory_gb),
      allow_preempt: !!draft.allow_preempt,
      note: draft.note || '',
    })
    await loadTaskGovernance()
  } catch (error) {
    console.error(error)
  }
  ruleSaving.value[user.username] = false
}

async function resetRuleForUser(user) {
  if (!user?.governance_rule) return
  ruleSaving.value[user.username] = true
  try {
    await deleteGovernanceRule(user.username)
    await loadTaskGovernance()
  } catch (error) {
    console.error(error)
  }
  ruleSaving.value[user.username] = false
}

async function doExportGovernance(fmt = 'markdown') {
  exporting.value = true
  try {
    const res = await exportGovernanceReport(fmt)
    const filename = fmt === 'html' ? 'governance-report.html' : 'governance-report.md'
    const mime = fmt === 'html' ? 'text/html; charset=utf-8' : 'text/markdown; charset=utf-8'
    const saved = await exportTextFile(res.data, { filename, mime })
    setActionNotice(
      'ok',
      '治理报告已导出',
      saved.path ? `已保存到 ${saved.path}` : `已开始下载 ${saved.filename}`,
    )
  } catch (error) {
    console.error(error)
    setActionNotice(
      'critical',
      '治理报告导出失败',
      error?.message || '治理报告导出失败',
    )
  }
  exporting.value = false
}

</script>

<template>
  <div class="task-page ink-page-shell">
    <WorkspaceSummary
      eyebrow="任务治理中心"
      title="把 GPU 进程从“看到”升级到“分级、让路、干预、追踪”"
      :description="fairnessOverview.summary || '当前共享状态稳定。'"
    >
      <template #meta>
        <div class="hero-card__actions">
          <button class="btn-tech" :disabled="exporting" @click="doExportGovernance('markdown')">
            {{ exporting ? '导出中...' : '导出治理报告' }}
          </button>
          <span class="status-badge" :class="executionMode === 'real' ? 'status-badge--warning' : 'status-badge--ok'">
            {{ executionMode === 'real' ? '真实执行' : '演练模式' }}
          </span>
        </div>
      </template>
      <section class="stats-grid">
        <div class="tech-card stat-card">
          <div class="stat-card__label">可治理任务</div>
          <div class="stat-card__value stat-value">{{ manageableProcessCount }}</div>
          <div class="stat-card__hint">默认只展示可真正干预的 GPU 任务</div>
        </div>
        <div class="tech-card stat-card">
          <div class="stat-card__label">背景 / 系统进程</div>
          <div class="stat-card__value stat-value" style="color:#999">{{ backgroundProcessCount }}</div>
          <div class="stat-card__hint">浏览器 GPU 子进程、桌面渲染等会自动归到这里</div>
        </div>
        <div class="tech-card stat-card">
          <div class="stat-card__label">治理用户</div>
          <div class="stat-card__value stat-value">{{ userCount }}</div>
          <div class="stat-card__hint">真正占用治理型 GPU 任务的用户数</div>
        </div>
        <div class="tech-card stat-card">
          <div class="stat-card__label">紧急任务</div>
          <div class="stat-card__value stat-value" style="color:#C41E3A">{{ urgentCount }}</div>
          <div class="stat-card__hint">预算紧张时优先保障</div>
        </div>
        <div class="tech-card stat-card">
          <div class="stat-card__label">可延迟任务</div>
          <div class="stat-card__value stat-value" style="color:#666">{{ deferrableCount }}</div>
          <div class="stat-card__hint">高峰期优先让路</div>
        </div>
        <div class="tech-card stat-card">
          <div class="stat-card__label">治理显存占用</div>
          <div class="stat-card__value stat-value">{{ fmtMem(totalGpuMemory) }}</div>
          <div class="stat-card__hint">只统计可治理任务</div>
        </div>
      </section>
    </WorkspaceSummary>

    <div class="workspace-nav-layout">
      <aside class="workspace-nav-layout__nav">
        <WorkspaceTabs
          v-model="activeTab"
          :items="taskTabs"
          orientation="vertical"
        />
      </aside>

      <section class="workspace-nav-layout__content">
        <div v-if="actionNotice" class="tech-card notice" :class="`notice--${actionNotice.tone}`">
          <div class="notice__title">{{ actionNotice.title }}</div>
          <div class="notice__detail">{{ actionNotice.detail }}</div>
        </div>

        <section v-if="activeTab === 'fairness'" class="fairness-dashboard">
      <div class="tech-card fairness-gauge-card">
        <div class="fairness-gauge-card__head">
          <div>
            <div class="fairness-gauge-card__eyebrow">多用户资源公平度量化</div>
            <div class="panel-card__title">公平治理仪表盘</div>
          </div>
          <div class="fairness-gauge-card__seal">衡</div>
        </div>
        <div class="fairness-gauge">
          <div class="fairness-gauge__ring">
            <svg viewBox="0 0 120 120" class="fairness-gauge__svg">
              <circle cx="60" cy="60" r="52" fill="none" stroke="rgba(0,0,0,0.04)" stroke-width="8" />
              <circle cx="60" cy="60" r="52" fill="none"
                :stroke="fairnessGaugeColor"
                stroke-width="8"
                stroke-linecap="round"
                :stroke-dasharray="`${(fairnessOverview.fairness_index || 0) * 3.267} 326.7`"
                stroke-dashoffset="0"
                transform="rotate(-90 60 60)"
                style="transition: stroke-dasharray 1.2s ease"
              />
            </svg>
            <div class="fairness-gauge__value">
              <span class="fairness-gauge__number stat-value" :style="{ color: fairnessGaugeColor }">{{ fairnessOverview.fairness_index ?? 0 }}</span>
              <span class="fairness-gauge__label">公平指数</span>
            </div>
          </div>
          <div class="fairness-gauge__info">
            <div class="fairness-gauge__level" :style="{ color: fairnessGaugeColor, background: fairnessGaugeBg }">
              {{ fairnessLevelLabel }}
            </div>
            <div class="fairness-gauge__summary">{{ fairnessOverview.summary || '当前共享状态稳定。' }}</div>
          </div>
        </div>
        <div v-if="fairnessUsers.length" class="fairness-users-dist">
          <div class="fairness-users-dist__title">用户资源占比</div>
          <div class="fairness-bar-list">
            <div v-for="user in fairnessUsers.slice(0, 6)" :key="user.username" class="fairness-bar-item">
              <div class="fairness-bar-item__head">
                <span class="fairness-bar-item__name">{{ user.username }}</span>
                <span class="fairness-bar-item__pct">{{ user.memory_share_pct || 0 }}%</span>
              </div>
              <div class="fairness-bar-item__track">
                <div class="fairness-bar-item__fill" :style="{ width: Math.min(user.memory_share_pct || 0, 100) + '%', background: (user.memory_share_pct || 0) > 60 ? '#C41E3A' : (user.memory_share_pct || 0) > 35 ? '#B8860B' : '#3A5F4B' }"></div>
              </div>
              <div class="fairness-bar-item__meta">{{ user.task_count }}任务 · {{ user.gpu_count }}卡</div>
            </div>
          </div>
        </div>
      </div>

      <div class="fairness-side">
        <div class="tech-card panel-card">
          <div class="panel-card__title">治理建议</div>
          <div class="panel-card__list">
            <div v-for="(item, index) in fairnessState.recommendations || []" :key="index" class="panel-card__item">
              {{ item }}
            </div>
            <div v-if="!(fairnessState.recommendations || []).length" class="panel-card__item">
              当前没有额外治理建议。
            </div>
          </div>
        </div>

        <div class="tech-card panel-card">
          <div class="panel-card__title">建议让路任务</div>
          <div class="yield-list">
            <div v-for="candidate in yieldCandidates.slice(0, 5)" :key="candidate.pid" class="yield-item">
              <div class="yield-item__top">
                <span class="yield-item__pid">PID {{ candidate.pid }}</span>
                <span class="yield-item__priority" :style="{ color: priorityColors[candidate.priority || 'normal'].color, background: priorityColors[candidate.priority || 'normal'].bg }">
                  {{ priorityColors[candidate.priority || 'normal'].label }}
                </span>
              </div>
              <div class="yield-item__reason">{{ candidate.yield_reason }}</div>
            </div>
            <div v-if="!yieldCandidates.length" class="panel-card__item">当前没有需要优先让路的任务。</div>
          </div>
        </div>
      </div>
    </section>

    <section v-if="activeTab === 'rules' && fairnessUsers.length" class="tech-card rules-panel">
      <div class="rules-panel__head">
        <div class="panel-card__title">用户额度规则</div>
        <div class="rules-panel__hint">为活跃用户设置任务数、GPU数、显存额度与是否允许让路</div>
      </div>
      <div class="rules-grid">
        <div v-for="user in fairnessUsers" :key="user.username" class="rule-card">
          <div class="rule-card__top">
            <div>
              <div class="rule-card__name">{{ user.username }}</div>
              <div class="rule-card__meta">
                当前 {{ user.task_count }} 个任务 · {{ user.gpu_count }} 张GPU · {{ user.memory_share_pct }}%
              </div>
            </div>
            <span class="rule-card__status" :class="user.violation_count ? 'rule-card__status--warn' : 'rule-card__status--ok'">
              {{ user.violation_count ? `违规 ${user.violation_count}` : '规则内' }}
            </span>
          </div>

          <div v-if="ruleDrafts[user.username]" class="rule-card__form">
            <select v-model="ruleDrafts[user.username].role" class="task-select">
              <option value="protected">{{ roleOptions.protected }}</option>
              <option value="member">{{ roleOptions.member }}</option>
              <option value="restricted">{{ roleOptions.restricted }}</option>
            </select>
            <input v-model.number="ruleDrafts[user.username].max_tasks" class="task-input" type="number" min="1" max="64" placeholder="最多任务" />
            <input v-model.number="ruleDrafts[user.username].max_gpu_count" class="task-input" type="number" min="1" max="16" placeholder="最多GPU" />
            <input v-model.number="ruleDrafts[user.username].max_memory_gb" class="task-input" type="number" min="1" step="0.5" max="1024" placeholder="显存额度(GB)" />
            <select v-model="ruleDrafts[user.username].allow_preempt" class="task-select">
              <option :value="true">允许让路</option>
              <option :value="false">保护任务</option>
            </select>
            <input v-model="ruleDrafts[user.username].note" class="task-input" type="text" placeholder="备注" />
          </div>

          <div class="rule-card__actions">
            <button class="btn-tech" :disabled="ruleSaving[user.username]" @click="saveRuleForUser(user)">
              {{ ruleSaving[user.username] ? '保存中...' : '保存规则' }}
            </button>
            <button class="btn-tech" :disabled="ruleSaving[user.username] || !user.governance_rule" @click="resetRuleForUser(user)">
              恢复默认
            </button>
          </div>
        </div>
      </div>
    </section>

    <section v-else-if="activeTab === 'rules'" class="tech-card rules-panel rules-panel--empty">
      <div class="panel-card__title">用户额度规则</div>
      <div class="panel-card__item">当前没有活跃用户需要配置规则。</div>
    </section>

    <WorkspacePaneLayout v-if="activeTab === 'actions'">
      <template #main>
        <section class="tech-card toolbar-card">
          <div class="toolbar-card__left">
            <input v-model="keyword" class="task-input" placeholder="搜索 PID / 用户 / 进程名 / 命令" />
            <select v-model="selectedPriority" class="task-select">
              <option value="all">全部优先级</option>
              <option value="urgent">紧急</option>
              <option value="normal">普通</option>
              <option value="deferrable">可延迟</option>
            </select>
          </div>
          <div class="toolbar-card__right">
            <div class="toolbar-card__switch">
              <button class="btn-tech" :class="{ 'btn-tech--primary': !showAllProcesses }" @click="showAllProcesses = false">仅治理任务</button>
              <button class="btn-tech" :class="{ 'btn-tech--primary': showAllProcesses }" @click="showAllProcesses = true">全部 GPU 相关进程</button>
            </div>
            <span class="toolbar-card__summary">当前显示 {{ filteredProcesses.length }} / {{ visibleProcesses.length }} 条</span>
          </div>
        </section>

        <section class="tech-card table-card">
          <div class="panel-scroll">
            <table class="task-table">
              <colgroup>
                <col style="width: 82px" />
                <col style="width: 76px" />
                <col style="width: 128px" />
                <col style="width: 118px" />
                <col style="width: 96px" />
                <col style="width: 78px" />
                <col style="width: 110px" />
                <col style="width: 110px" />
                <col style="width: 240px" />
                <col style="width: 300px" />
                <col style="width: 250px" />
              </colgroup>
              <thead>
                <tr>
                  <th>PID</th>
                  <th>GPU</th>
                  <th>进程名</th>
                  <th>用户</th>
                  <th>显存</th>
                  <th>CPU</th>
                  <th>优先级</th>
                  <th>治理状态</th>
                  <th>说明</th>
                  <th>命令</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="proc in filteredProcesses" :key="proc.pid">
                  <td class="stat-value">{{ proc.pid }}</td>
                  <td>GPU {{ proc.gpu_index }}</td>
                  <td>{{ proc.name }}</td>
                  <td>{{ proc.username }}</td>
                  <td class="task-table__metric" :class="{ 'task-table__metric--muted': !isManageable(proc) && Number(proc.gpu_memory_used || 0) <= 0 }" :title="gpuMetricTitle(proc)">{{ displayGpuMemory(proc) }}</td>
                  <td class="task-table__metric" :class="{ 'task-table__metric--muted': !isManageable(proc) && Number(proc.cpu_percent || 0) <= 0 }" :title="cpuMetricTitle(proc)">{{ displayCpuPercent(proc) }}</td>
                  <td>
                    <select
                      class="priority-select"
                      :disabled="!isManageable(proc)"
                      :value="proc.priority || 'normal'"
                      :style="{ color: priorityColors[proc.priority || 'normal'].color, background: priorityColors[proc.priority || 'normal'].bg }"
                      @change="changePriority(proc, $event.target.value)"
                    >
                      <option value="urgent">紧急</option>
                      <option value="normal">普通</option>
                      <option value="deferrable">可延迟</option>
                    </select>
                  </td>
                  <td>
                    <span class="status-badge" :class="getCategoryClass(proc)">{{ getCategoryLabel(proc) }}</span>
                  </td>
                  <td>
                    <div class="task-table__reason" :title="getManageableReason(proc)">{{ getReasonSummary(proc) }}</div>
                  </td>
                  <td>
                    <div class="task-table__command" :title="proc.command || '-'">{{ getCommandPreview(proc) }}</div>
                  </td>
                  <td class="task-table__ops">
                    <div v-if="isManageable(proc)">
                      <div class="task-table__actions">
                        <button class="btn-tech" :disabled="isActionDisabled(proc, 'pause')" @click="doAction(proc, 'pause')">暂停</button>
                        <button class="btn-tech" :disabled="isActionDisabled(proc, 'resume')" @click="doAction(proc, 'resume')">恢复</button>
                        <button class="btn-tech btn-tech--danger" :disabled="isActionDisabled(proc, 'terminate')" @click="doAction(proc, 'terminate')">终止</button>
                      </div>
                      <div class="task-table__hint" :title="getActionHint(proc)">{{ getActionHint(proc) }}</div>
                    </div>
                    <div v-else class="task-table__readonly" :title="getManageableReason(proc)">
                      该类进程只做观测，不提供暂停/终止
                    </div>
                  </td>
                </tr>
                <tr v-if="!filteredProcesses.length">
                  <td colspan="11" class="task-table__empty">
                    {{ showAllProcesses ? '暂无匹配的 GPU 相关进程。' : '当前没有可治理任务，可切换到“全部 GPU 相关进程”查看背景与系统进程。' }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </template>

      <template #side>
        <section class="tech-card panel-card">
          <div class="panel-card__title">执行模式</div>
          <div class="mode-box">
            <div class="mode-box__switch">
              <button class="btn-tech" :class="{ 'btn-tech--primary': executionMode === 'dry_run' }" @click="executionMode = 'dry_run'">演练模式</button>
              <button class="btn-tech" :class="{ 'btn-tech--primary': executionMode === 'real' }" @click="executionMode = 'real'">真实执行</button>
            </div>
            <label v-if="executionMode === 'real'" class="mode-box__ack">
              <input v-model="riskAcknowledged" type="checkbox" />
              我已确认会直接作用于真实进程
            </label>
            <div class="mode-box__hint">{{ executionSummary }}</div>
          </div>
        </section>

        <section class="tech-card panel-card">
          <div class="panel-card__title">候选让路任务</div>
          <div class="yield-list">
            <div v-for="candidate in yieldCandidates.slice(0, 5)" :key="candidate.pid" class="yield-item">
              <div class="yield-item__top">
                <span class="yield-item__pid">PID {{ candidate.pid }}</span>
                <span class="yield-item__priority" :style="{ color: priorityColors[candidate.priority || 'normal'].color, background: priorityColors[candidate.priority || 'normal'].bg }">
                  {{ priorityColors[candidate.priority || 'normal'].label }}
                </span>
              </div>
              <div class="yield-item__reason">{{ candidate.yield_reason }}</div>
            </div>
            <div v-if="!yieldCandidates.length" class="panel-card__item">当前没有需要优先让路的任务。</div>
          </div>
        </section>
      </template>
    </WorkspacePaneLayout>
      </section>
    </div>
  </div>
</template>

<style scoped>
.task-page {
  max-width: 1460px;
  margin: 0 auto;
}

.hero-card,
.toolbar-card,
.rules-panel,
.table-card,
.panel-card {
  margin-bottom: 14px;
}

.hero-card {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 22px 24px;
}

.hero-card__eyebrow,
.rule-card__meta,
.rules-panel__hint,
.toolbar-card__summary,
.mode-box__ack,
.mode-box__hint {
  font-size: 0.75rem;
  color: var(--text-muted);
  line-height: 1.6;
}

.hero-card__title {
  margin: 8px 0;
  font-size: 1.5rem;
  color: var(--text-primary);
}

.hero-card__desc {
  font-size: 0.875rem;
  color: var(--text-secondary);
  line-height: 1.7;
}

.hero-card__actions,
.mode-box,
.mode-box__switch,
.toolbar-card__right,
.toolbar-card__switch,
.rules-panel__head,
.rule-card__actions,
.task-table__actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.hero-card__actions,
.mode-box {
  align-items: flex-end;
}

.mode-box {
  flex-direction: column;
}

.mode-box__hint {
  max-width: 360px;
  padding: 8px 12px;
  border-radius: 999px;
  color: #7B5D15;
  background: rgba(212, 175, 55, 0.08);
  border: 1px solid rgba(184, 134, 11, 0.16);
}

.notice {
  padding: 14px 16px;
  margin-bottom: 14px;
}

.notice--ok {
  border-color: rgba(46,139,87,0.14);
  background: rgba(46,139,87,0.05);
}

.notice--warning {
  border-color: rgba(184,134,11,0.16);
  background: rgba(212,175,55,0.08);
}

.notice--critical {
  border-color: rgba(196,30,58,0.14);
  background: rgba(196,30,58,0.06);
}

.notice__title {
  font-size: 0.82rem;
  font-weight: 700;
  color: var(--text-primary);
}

.notice__detail {
  margin-top: 6px;
  font-size: 0.78rem;
  color: var(--text-secondary);
  line-height: 1.7;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
  margin-bottom: 14px;
}

.stat-card {
  padding: 16px;
}

.stat-card__label,
.stat-card__hint {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.stat-card__value {
  margin: 6px 0 4px;
  font-size: 1.8rem;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14px;
  margin-bottom: 14px;
}

.panel-card,
.rules-panel {
  padding: 18px;
}

.panel-card__title {
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 12px;
}

.panel-card__list,
.yield-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.panel-card__item,
.yield-item {
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(58,95,75,0.04);
  border: 1px solid rgba(58,95,75,0.08);
  font-size: 0.78rem;
  line-height: 1.7;
  color: var(--text-secondary);
}

.yield-item__top {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}

.yield-item__pid {
  font-weight: 700;
  color: #C41E3A;
}

.yield-item__priority {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 0.6875rem;
  font-weight: 700;
}

.rules-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-top: 12px;
}

.rule-card {
  padding: 14px;
  border-radius: 12px;
  background: rgba(91,75,140,0.03);
  border: 1px solid rgba(91,75,140,0.08);
}

.rule-card__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}

.rule-card__name {
  font-size: 0.92rem;
  font-weight: 700;
  color: var(--text-primary);
}

.rule-card__status {
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 0.6875rem;
  font-weight: 700;
}

.rule-card__status--ok {
  color: #2E8B57;
  background: rgba(46,139,87,0.08);
}

.rule-card__status--warn {
  color: #C41E3A;
  background: rgba(196,30,58,0.08);
}

.rule-card__form {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  margin-bottom: 10px;
}

.toolbar-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
}

.toolbar-card__left {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
}

.task-input,
.task-select,
.priority-select {
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  background: rgba(255,255,255,0.55);
  color: var(--text-primary);
  font-size: 0.8125rem;
}

.task-input {
  flex: 1;
}

.priority-select:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.table-card {
  overflow-x: auto;
}

.task-table {
  width: 100%;
  min-width: 1480px;
  border-collapse: collapse;
  table-layout: fixed;
}

.task-table th {
  text-align: left;
  padding: 12px 16px;
  font-size: 0.75rem;
  color: var(--text-muted);
  border-bottom: 1px solid var(--border-color);
}

.task-table td {
  padding: 12px 16px;
  font-size: 0.8125rem;
  border-bottom: 1px solid rgba(255,255,255,0.03);
  vertical-align: middle;
}

.task-table tr:hover td {
  background: rgba(58,95,75,0.03);
}

.status-badge {
  display: inline-flex;
  align-items: center;
  padding: 3px 8px;
  border-radius: 999px;
  font-size: 0.6875rem;
  font-weight: 700;
}

.status-badge--ok {
  color: #2F6A46;
  background: rgba(46,139,87,0.08);
}

.status-badge--background {
  color: #666666;
  background: rgba(153,153,153,0.12);
}

.status-badge--system {
  color: #7A4B14;
  background: rgba(212,175,55,0.14);
}

.task-table__reason {
  white-space: normal;
  overflow-wrap: anywhere;
  word-break: break-word;
  line-height: 1.5;
  color: var(--text-secondary);
}

.task-table__command {
  white-space: normal;
  overflow-wrap: anywhere;
  word-break: break-word;
  line-height: 1.5;
  color: var(--text-secondary);
}

.task-table__metric {
  font-variant-numeric: tabular-nums;
  color: var(--text-primary);
}

.task-table__metric--muted {
  color: var(--text-muted);
}

.task-table__ops {
  vertical-align: middle;
}

.task-table__actions--disabled {
  opacity: 0.58;
}

.task-table__readonly,
.task-table__hint {
  margin-top: 8px;
  white-space: normal;
  overflow-wrap: anywhere;
  word-break: break-word;
  font-size: 0.72rem;
  line-height: 1.6;
  color: var(--text-muted);
}

.task-table__readonly {
  margin-top: 0;
}

.task-table__empty {
  padding: 40px 16px;
  text-align: center;
  color: var(--text-muted);
}

@media (max-width: 1400px) {
  .stats-grid {
    grid-template-columns: repeat(3, 1fr);
  }

  .fairness-dashboard,
  .rules-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 860px) {
  .hero-card,
  .hero-card__actions,
  .toolbar-card,
  .toolbar-card__left,
  .toolbar-card__right,
  .toolbar-card__switch,
  .rule-card__top,
  .rule-card__actions {
    flex-direction: column;
    align-items: stretch;
  }

  .stats-grid {
    grid-template-columns: 1fr;
  }

  .rule-card__form {
    grid-template-columns: 1fr;
  }
}

/* ===== 公平治理仪表盘 ===== */
.fairness-dashboard {
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  gap: 14px;
  margin-bottom: 14px;
}

.fairness-side {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.fairness-gauge-card {
  padding: 20px 22px;
}

.fairness-gauge-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
}

.fairness-gauge-card__eyebrow {
  font-size: 0.6875rem;
  color: var(--text-muted);
  letter-spacing: 0.12em;
  margin-bottom: 4px;
}

.fairness-gauge-card__seal {
  width: 36px;
  height: 36px;
  border: 2.5px solid var(--ink-vermillion, #C41E3A);
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-seal);
  font-size: 0.85rem;
  color: var(--ink-vermillion, #C41E3A);
  transform: rotate(-5deg);
  opacity: 0.6;
}

.fairness-gauge {
  display: flex;
  align-items: center;
  gap: 24px;
  margin-bottom: 20px;
}

.fairness-gauge__ring {
  position: relative;
  width: 120px;
  height: 120px;
  flex-shrink: 0;
}

.fairness-gauge__svg {
  width: 100%;
  height: 100%;
}

.fairness-gauge__value {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.fairness-gauge__number {
  font-size: 2rem;
  line-height: 1;
}

.fairness-gauge__label {
  font-size: 0.625rem;
  color: var(--text-muted);
  margin-top: 4px;
  letter-spacing: 0.1em;
}

.fairness-gauge__info {
  flex: 1;
}

.fairness-gauge__level {
  display: inline-block;
  padding: 3px 12px;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 700;
  margin-bottom: 8px;
}

.fairness-gauge__summary {
  font-size: 0.84rem;
  color: var(--text-secondary);
  line-height: 1.7;
}

.fairness-users-dist {
  padding-top: 16px;
  border-top: 1px solid var(--border-color);
}

.fairness-users-dist__title {
  font-size: 0.78rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 12px;
}

.fairness-bar-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.fairness-bar-item__head {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
}

.fairness-bar-item__name {
  font-size: 0.75rem;
  color: var(--text-primary);
  font-weight: 600;
}

.fairness-bar-item__pct {
  font-size: 0.75rem;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}

.fairness-bar-item__track {
  height: 6px;
  border-radius: 3px;
  background: rgba(0,0,0,0.04);
  overflow: hidden;
}

.fairness-bar-item__fill {
  height: 100%;
  border-radius: 3px;
  transition: width 1s ease;
}

.fairness-bar-item__meta {
  margin-top: 2px;
  font-size: 0.625rem;
  color: var(--text-muted);
}
</style>

<script setup>
import { computed, ref } from 'vue'
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
import TaskProcessLedger from '../components/tasks/TaskProcessLedger.vue'
import FairnessGaugeCard from '../components/tasks/FairnessGaugeCard.vue'
import UserRulesGrid from '../components/tasks/UserRulesGrid.vue'
import WorkspacePaneLayout from '../components/workspace/WorkspacePaneLayout.vue'
import WorkspaceSummary from '../components/workspace/WorkspaceSummary.vue'
import WorkspaceTabs from '../components/workspace/WorkspaceTabs.vue'
import { useTaskManagerData } from '../composables/useTaskManagerData.js'
import { useExecutionMode } from '../composables/useExecutionMode.js'
import { useActionFeedback } from '../composables/useActionFeedback.js'

const activeTab = ref('actions')
const keyword = ref('')
const selectedPriority = ref('all')
const showAllProcesses = ref(false)
const { executionMode, riskAcknowledged, isDryRun, isReal, canExecute, modeLabel, modeBadgeClass, buildExecutionParams } = useExecutionMode()
const { actionNotice, showNotice, clearNotice } = useActionFeedback()
const exporting = ref(false)
const actionLoading = ref({})
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
const normalizedProcesses = computed(() => visibleProcesses.value)
const processSummary = computed(() => taskSummary.value)

const priorityColors = {
  urgent: { bg: 'rgba(196,30,58,0.12)', color: '#C41E3A', label: '紧急' },
  normal: { bg: 'rgba(58,95,75,0.12)', color: '#3A5F4B', label: '普通' },
  deferrable: { bg: 'rgba(148,163,184,0.12)', color: '#666666', label: '可延迟' },
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

const fairnessOverview = computed(() => fairnessState.value.overview || {})
const fairnessUsers = computed(() => fairnessState.value.users || [])
const yieldCandidates = computed(() => fairnessState.value.yield_candidates || [])

const manageableProcessCount = computed(() => processSummary.value.manageableCount)
const urgentCount = computed(() => processSummary.value.urgentCount)
const totalGpuMemory = computed(() => processSummary.value.totalGpuMemory)
const executionSummary = computed(() =>
  isReal.value
    ? (riskAcknowledged.value
      ? '当前为真实执行模式，操作会直接作用于可治理 GPU 任务。'
      : '当前为真实执行模式，但还未确认风险，按钮会保持禁用。')
    : '当前为演练模式，只生成预演结果，不会改动真实进程。'
)

async function loadTaskGovernance() {
  try {
    await refreshTaskGovernance({ force: true })
  } catch (error) {
    console.error(error)
  }
}

function isActionDisabled(proc, action) {
  if (!isManageable(proc)) return true
  if (isReal.value && !riskAcknowledged.value) return true
  return Boolean(actionLoading.value[`${proc.pid}-${action}`])
}

function getActionHint(proc) {
  if (!isManageable(proc)) return '仅观察，不开放治理动作'
  if (isDryRun.value) return '演练模式，不改动真实进程'
  if (!riskAcknowledged.value) return '确认风险后才会真实执行'
  return '将直接作用于真实进程'
}

function getCommandPreview(proc) {
  return (proc?.command || '-').trim() || '-'
}

const ledgerHelpers = {
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
  getActionHint,
}

const ledgerHandlers = {
  changePriority,
  doAction,
  isActionDisabled,
}

async function doAction(proc, action) {
  if (!isManageable(proc)) {
    showNotice('warning', '当前进程不可治理', getManageableReason(proc))
    return
  }
  if (isReal.value && !riskAcknowledged.value) {
    showNotice('warning', '尚未确认风险', '真实执行前请先勾选风险确认。')
    return
  }
  if (isReal.value && action === 'terminate' && !window.confirm(`将终止真实进程 PID ${proc.pid}，是否继续？`)) {
    return
  }

  actionLoading.value[`${proc.pid}-${action}`] = true
  try {
    const options = buildExecutionParams()
    let response = null
    if (action === 'pause') response = await pauseTask(proc.pid, options)
    else if (action === 'resume') response = await resumeTask(proc.pid, options)
    else if (action === 'terminate') response = await terminateTask(proc.pid, options)

    const data = response?.data || {}
    if (data.dry_run) {
      showNotice('warning', '已生成演练结果', data.message || `已完成 PID ${proc.pid} 的动作预演。`)
    } else {
      const actionLabel = action === 'pause' ? '暂停' : action === 'resume' ? '恢复' : '终止'
      const detail = data.message || `${actionLabel}指令已发送到 PID ${proc.pid}`
      const suffix = action === 'terminate' && data.forced ? '，进程对普通终止无响应，已执行强制结束。' : '。'
      showNotice('ok', '真实动作已执行', `${detail}${suffix}`)
    }
  } catch (error) {
    console.error(error)
    showNotice(
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
    showNotice('warning', '当前进程不可分级', getManageableReason(proc))
    return
  }
  try {
    await setTaskPriority(proc.pid, priority)
    await loadTaskGovernance()
  } catch (error) {
    console.error(error)
  }
}

async function handleSaveRule(ruleData) {
  try {
    await saveGovernanceRule(ruleData)
    await loadTaskGovernance()
  } catch (error) {
    console.error(error)
  }
}

async function handleResetRule(username) {
  try {
    await deleteGovernanceRule(username)
    await loadTaskGovernance()
  } catch (error) {
    console.error(error)
  }
}

async function doExportGovernance(fmt = 'markdown') {
  exporting.value = true
  try {
    const res = await exportGovernanceReport(fmt)
    const filename = fmt === 'html' ? 'governance-report.html' : 'governance-report.md'
    const mime = fmt === 'html' ? 'text/html; charset=utf-8' : 'text/markdown; charset=utf-8'
    const saved = await exportTextFile(res.data, { filename, mime })
    showNotice(
      'ok',
      '治理报告已导出',
      saved.path ? `已保存到 ${saved.path}` : `已开始下载 ${saved.filename}`,
    )
  } catch (error) {
    console.error(error)
    showNotice(
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
      title="任务治理"
    >
      <template #meta>
        <div class="ink-inline-meta">
          <span class="status-badge status-badge--ok">{{ manageableProcessCount }} 可治理</span>
          <span class="status-badge status-badge--warning">{{ urgentCount }} 紧急</span>
          <span class="status-badge" :class="modeBadgeClass">
            {{ modeLabel }}
          </span>
        </div>
      </template>
    </WorkspaceSummary>

    <section class="stats-grid workspace-summary-strip">
      <div class="tech-card stat-card">
        <div class="stat-card__label">可治理任务</div>
        <div class="stat-card__value stat-value">{{ manageableProcessCount }}</div>
        <div class="stat-card__hint">当前可直接执行治理动作的任务数</div>
      </div>
      <div class="tech-card stat-card">
        <div class="stat-card__label">紧急任务</div>
        <div class="stat-card__value stat-value" style="color:#C41E3A">{{ urgentCount }}</div>
        <div class="stat-card__hint">预算紧张时优先保障</div>
      </div>
      <div class="tech-card stat-card">
        <div class="stat-card__label">治理显存占用</div>
        <div class="stat-card__value stat-value">{{ fmtMem(totalGpuMemory) }}</div>
        <div class="stat-card__hint">只统计当前可治理任务</div>
      </div>
    </section>

    <div class="workspace-nav-layout">
      <div class="workspace-nav-layout__nav">
        <WorkspaceTabs
          v-model="activeTab"
          :items="taskTabs"
        />
      </div>

      <section class="workspace-nav-layout__content">
        <div v-if="actionNotice" class="tech-card notice" :class="`notice--${actionNotice.tone}`">
          <div class="notice__title">{{ actionNotice.title }}</div>
          <div class="notice__detail">{{ actionNotice.detail }}</div>
        </div>

        <section v-if="activeTab === 'fairness'" class="fairness-dashboard">
      <FairnessGaugeCard :overview="fairnessOverview" :users="fairnessUsers" />

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

    <UserRulesGrid
      v-if="activeTab === 'rules'"
      :users="fairnessUsers"
      @save="handleSaveRule"
      @reset="handleResetRule"
    />

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
            <button class="btn-tech" :disabled="exporting" @click="doExportGovernance('markdown')">
              {{ exporting ? '导出中...' : '导出治理报告' }}
            </button>
            <span class="toolbar-card__summary">当前显示 {{ filteredProcesses.length }} / {{ normalizedProcesses.length }} 条</span>
          </div>
        </section>

        <section class="tech-card ledger-panel">
          <div class="ledger-panel__head">
            <div class="panel-card__title">任务账本</div>
            <div class="ledger-panel__hint">把身份、治理说明和动作拆成独立区块，避免某个字段变长时拖拽整张表的排布。</div>
          </div>
          <TaskProcessLedger
            :processes="filteredProcesses"
            :show-all-processes="showAllProcesses"
            :priority-colors="priorityColors"
            :helpers="ledgerHelpers"
            :handlers="ledgerHandlers"
          />
        </section>
      </template>

      <template #side>
        <section class="tech-card panel-card">
          <div class="panel-card__title">执行模式</div>
          <div class="mode-box">
            <div class="mode-box__switch">
              <button class="btn-tech" :class="{ 'btn-tech--primary': isDryRun }" @click="executionMode = 'dry_run'">演练模式</button>
              <button class="btn-tech" :class="{ 'btn-tech--primary': isReal }" @click="executionMode = 'real'">真实执行</button>
            </div>
            <label v-if="isReal" class="mode-box__ack">
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
.ledger-panel,
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
.rule-card__actions {
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
  grid-template-columns: repeat(3, minmax(0, 1fr));
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

.ledger-panel {
  padding: 18px 20px;
}

.ledger-panel__head {
  display: grid;
  gap: 6px;
  margin-bottom: 14px;
}

.ledger-panel__hint {
  font-size: 0.75rem;
  color: var(--text-muted);
  line-height: 1.7;
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

@media (max-width: 1400px) {
  .stats-grid {
    grid-template-columns: repeat(3, 1fr);
  }

  .fairness-dashboard {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 860px) {
  .hero-card,
  .hero-card__actions,
  .toolbar-card,
  .toolbar-card__left,
  .toolbar-card__right,
  .toolbar-card__switch {
    flex-direction: column;
    align-items: stretch;
  }

  .stats-grid {
    grid-template-columns: 1fr;
  }
}

</style>

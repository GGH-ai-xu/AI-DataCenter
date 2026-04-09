<script setup>
import { computed, ref } from 'vue'

import TaskProcessLedger from '../components/tasks/TaskProcessLedger.vue'
import GovernanceActionsMainPane from '../components/governance/GovernanceActionsMainPane.vue'
import GovernanceActionsSidePane from '../components/governance/GovernanceActionsSidePane.vue'
import WorkspacePaneLayout from '../components/workspace/WorkspacePaneLayout.vue'
import {
  createGovernanceTaskLedgerHelpers,
  getManageableReason,
  isManageable,
} from '../lib/governanceTaskLedger.js'
import {
  filterProcesses,
  normalizeProcesses,
  selectVisibleProcesses,
} from '../lib/realtimeSummaries.js'
import {
  exportGovernanceReport,
  pauseTask,
  resumeTask,
  setTaskPriority,
  terminateTask,
} from '../services/api.js'
import { exportTextFile } from '../services/desktopExport.js'

const REPORT_FILENAME = 'governance-report.md'
const REPORT_MIME = 'text/markdown; charset=utf-8'
const REPORT_FORMAT = 'markdown'
const YIELD_CANDIDATE_LIMIT = 5
const FAIRNESS_SECTION_TITLE = '公平摘要'
const YIELD_SECTION_TITLE = '候选让路任务'
const EMPTY_FAIRNESS = Object.freeze({
  overview: {},
  users: [],
  yield_candidates: [],
  recommendations: [],
})
const PRIORITY_COLORS = Object.freeze({
  urgent: { bg: 'rgba(239, 68, 68, 0.12)', color: '#EF4444', label: '紧急' },
  normal: { bg: 'rgba(0, 212, 170, 0.12)', color: '#00D4AA', label: '普通' },
  deferrable: { bg: 'rgba(160, 170, 190, 0.14)', color: '#A0AABE', label: '可延迟' },
})

const props = defineProps({
  execution: {
    type: Object,
    default: () => ({}),
  },
  feedback: {
    type: Object,
    default: () => ({}),
  },
  governance: {
    type: Object,
    default: () => ({}),
  },
  reviewModel: {
    type: Object,
    default: () => ({}),
  },
})

const keyword = ref('')
const selectedPriority = ref('all')
const showAllProcesses = ref(false)
const exporting = ref(false)
const actionLoading = ref({})

const actionsState = computed(() => props.governance.actionsState || { processes: [], fairness: EMPTY_FAIRNESS })
const fairnessState = computed(() => actionsState.value.fairness || EMPTY_FAIRNESS)
const fairnessOverview = computed(() => fairnessState.value.overview || {})
const fairnessUsers = computed(() => fairnessState.value.users || [])
const fairnessRecommendations = computed(() => fairnessState.value.recommendations || [])
const yieldCandidates = computed(() => fairnessState.value.yield_candidates || [])
const normalizedProcesses = computed(() => normalizeProcesses(actionsState.value.processes || []))
const visibleProcesses = computed(() => selectVisibleProcesses(
  normalizedProcesses.value,
  showAllProcesses.value,
))
const filteredProcesses = computed(() => filterProcesses(
  normalizedProcesses.value,
  {
    keyword: keyword.value,
    priority: selectedPriority.value,
    includeAll: showAllProcesses.value,
  },
))
const executionSummary = computed(() => {
  if (props.execution.riskAcknowledged) {
    return '风险已确认，治理动作会直接作用于可治理 GPU 任务。'
  }
  return '治理工作区当前只支持真实执行；勾选风险确认后，动作按钮才会启用。'
})
const ledgerHelpers = computed(() => createGovernanceTaskLedgerHelpers({
  isDryRun: Boolean(props.execution.isDryRun),
  isReal: Boolean(props.execution.isReal),
  riskAcknowledged: Boolean(props.execution.riskAcknowledged),
}))

const ledgerHandlers = {
  changePriority,
  doAction,
  isActionDisabled,
}

function actionKey(proc, action) {
  return `${proc.pid}-${action}`
}

function setActionLoading(proc, action, loading) {
  const key = actionKey(proc, action)
  if (loading) {
    actionLoading.value = { ...actionLoading.value, [key]: true }
    return
  }
  const next = { ...actionLoading.value }
  delete next[key]
  actionLoading.value = next
}

function showNotice(tone, title, detail) {
  props.feedback.showNotice?.(tone, title, detail)
}

function updateRiskAcknowledged(value) {
  props.execution.riskAcknowledged = value
}

function isActionDisabled(proc, action) {
  if (!isManageable(proc)) return true
  if (!props.execution.canExecute) return true
  return Boolean(actionLoading.value[actionKey(proc, action)])
}

async function refreshActions(force = false) {
  try {
    await props.governance.refreshActions?.({ force })
  } catch (error) {
    console.error(error)
    showNotice('critical', '刷新任务账本失败', error?.message || '请稍后重试。')
  }
}

function actionLabel(action) {
  if (action === 'pause') return '暂停'
  if (action === 'resume') return '恢复'
  return '终止'
}

function shouldConfirmTerminate(proc, action) {
  if (action !== 'terminate' || !props.execution.isReal) return false
  return window.confirm(`将终止真实进程 PID ${proc.pid}，是否继续？`)
}

async function requestTaskAction(proc, action) {
  const options = props.execution.buildExecutionParams?.() || {}
  if (action === 'pause') return pauseTask(proc.pid, options)
  if (action === 'resume') return resumeTask(proc.pid, options)
  return terminateTask(proc.pid, options)
}

function handleActionResponse(proc, action, data) {
  const detail = data.message || `${actionLabel(action)}指令已发送到 PID ${proc.pid}`
  const suffix = action === 'terminate' && data.forced
    ? '，进程对普通终止无响应，已执行强制结束。'
    : '。'
  showNotice('ok', '真实动作已执行', `${detail}${suffix}`)
}

async function doAction(proc, action) {
  if (!isManageable(proc)) {
    showNotice('warning', '当前进程不可治理', getManageableReason(proc))
    return
  }
  if (!props.execution.isReal) {
    showNotice('warning', '当前仅支持真实执行', '治理工作区当前只支持真实执行，请先确认风险。')
    return
  }
  if (!props.execution.riskAcknowledged) {
    showNotice('warning', '尚未确认风险', '真实执行前请先勾选风险确认。')
    return
  }
  if (action === 'terminate' && !shouldConfirmTerminate(proc, action)) {
    return
  }

  setActionLoading(proc, action, true)
  try {
    const response = await requestTaskAction(proc, action)
    handleActionResponse(proc, action, response?.data || {})
  } catch (error) {
    console.error(error)
    showNotice(
      'critical',
      '动作执行失败',
      error?.response?.data?.detail || error?.message || '任务动作执行失败',
    )
  } finally {
    setActionLoading(proc, action, false)
  }
  await refreshActions(true)
}

async function changePriority(proc, priority) {
  if (!isManageable(proc)) {
    showNotice('warning', '当前进程不可分级', getManageableReason(proc))
    return
  }
  try {
    await setTaskPriority(proc.pid, priority)
    await refreshActions(true)
  } catch (error) {
    console.error(error)
    showNotice('critical', '优先级更新失败', error?.response?.data?.detail || error?.message || '请稍后重试。')
  }
}

async function doExportGovernance() {
  exporting.value = true
  try {
    const response = await exportGovernanceReport(REPORT_FORMAT)
    const saved = await exportTextFile(response.data, {
      filename: REPORT_FILENAME,
      mime: REPORT_MIME,
    })
    showNotice(
      'ok',
      '治理报告已导出',
      saved.path ? `已保存到 ${saved.path}` : `已开始下载 ${saved.filename}`,
    )
  } catch (error) {
    console.error(error)
    showNotice('critical', '治理报告导出失败', error?.message || '请稍后重试。')
  } finally {
    exporting.value = false
  }
}
</script>

<template>
  <WorkspacePaneLayout>
    <template #main>
      <GovernanceActionsMainPane
        :keyword="keyword"
        :selected-priority="selectedPriority"
        :show-all-processes="showAllProcesses"
        :exporting="exporting"
        :filtered-processes="filteredProcesses"
        :visible-count="visibleProcesses.length"
        :priority-colors="PRIORITY_COLORS"
        :ledger-component="TaskProcessLedger"
        :ledger-helpers="ledgerHelpers"
        :ledger-handlers="ledgerHandlers"
        @update:keyword="keyword = $event"
        @update:selected-priority="selectedPriority = $event"
        @update:show-all-processes="showAllProcesses = $event"
        @export="doExportGovernance"
      />
    </template>

    <template #side>
      <GovernanceActionsSidePane
        :execution="execution"
        :execution-summary="executionSummary"
        :fairness-title="FAIRNESS_SECTION_TITLE"
        :yield-title="YIELD_SECTION_TITLE"
        :fairness-overview="fairnessOverview"
        :fairness-users="fairnessUsers"
        :yield-candidates="yieldCandidates"
        :fairness-recommendations="fairnessRecommendations"
        :priority-colors="PRIORITY_COLORS"
        :yield-limit="YIELD_CANDIDATE_LIMIT"
        @update:risk-acknowledged="updateRiskAcknowledged"
      />
    </template>
  </WorkspacePaneLayout>
</template>

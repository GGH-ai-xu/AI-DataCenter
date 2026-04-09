<script setup>
import { computed, ref, watch } from 'vue'
import DashboardHealthTab from '../components/dashboard/DashboardHealthTab.vue'
import DashboardLiveWorkspace from '../components/dashboard/DashboardLiveWorkspace.vue'
import DashboardOverviewTab from '../components/dashboard/DashboardOverviewTab.vue'
import WorkspaceSummary from '../components/workspace/WorkspaceSummary.vue'
import WorkspaceTabs from '../components/workspace/WorkspaceTabs.vue'
import { useDashboardData } from '../composables/useDashboardData.js'
import {
  buildDashboardHealthModel,
  buildDashboardOverviewModel,
} from '../lib/dashboardPageModels.js'
import { formatImportedGpuLabel } from '../lib/importContext.js'
import { useAppStore } from '../stores/app.js'
const DEFAULT_SCHEDULER_STATE = {
  time_period_label: '平峰时段',
  budget: {
    enabled: false,
    total_power_budget: 1200,
    current_total_power: 0,
    remaining_power: 1200,
    usage_pct: 0,
    is_exceeded: false,
    managed_gpu_count: 0,
    last_actions: [],
  },
}

const DEFAULT_FAIRNESS_STATE = {
  overview: {
    fairness_index: 100,
    level: 'balanced',
    summary: '当前导入范围运行稳定。',
    active_users: 0,
    dominant_user: null,
    highest_share_pct: 0,
    reclaimable_candidates: 0,
  },
  users: [],
  recommendations: [],
  yield_candidates: [],
}

const DEFAULT_SELF_CHECK_STATE = {
  summary: {
    status: 'warning',
    title: '等待导入后的治理巡检',
    message: '当前总览只围绕本次导入范围展示治理、监控与历史能力。',
  },
  checks: [],
  ws_connections: 0,
  llm_available: false,
}
const store = useAppStore()
const activeTab = ref('overview')
const schedulerState = ref(DEFAULT_SCHEDULER_STATE)
const fairnessState = ref(DEFAULT_FAIRNESS_STATE)
const selfCheckState = ref(DEFAULT_SELF_CHECK_STATE)

const dashboardTabs = [
  { key: 'overview', label: '首页', desc: '摘要与分流' },
  { key: 'live', label: '实时', desc: 'GPU 与趋势' },
  { key: 'health', label: '巡检', desc: '异常与链路' },
]
const {
  dashboardSummary,
  refreshHealth,
  refreshOverview,
} = useDashboardData({
  activeTab,
  onOverviewData: applyOverviewPayload,
  onHealthData: applyHealthPayload,
})

const workspaceReady = computed(() => store.workspaceReady)
const importedIndexes = computed(() => store.importContext?.imported_gpu_indexes || [])
const liveSummary = computed(() => ({
  ...dashboardSummary.value,
  criticalAlertCount: (dashboardSummary.value.criticalAlerts || []).length,
}))
const overviewModel = computed(() => buildDashboardOverviewModel({
  importedIndexes: importedIndexes.value,
  sourceMode: store.importContext?.source_mode,
  workspaceReady: workspaceReady.value,
  wsConnected: store.wsConnected,
  processCount: store.processes.length,
  budget: schedulerState.value.budget,
  fairnessOverview: fairnessState.value.overview,
  criticalAlertCount: liveSummary.value.criticalAlertCount,
}))
const healthModel = computed(() => buildDashboardHealthModel({
  importedLabel: formatImportedGpuLabel(importedIndexes.value),
  wsConnected: store.wsConnected,
  selfCheck: selfCheckState.value,
}))
const summaryTone = computed(() => overviewModel.value.signalCards?.[0] || {
  tone: 'ok',
  label: '预算稳定',
  detail: '当前功率预算处于可控范围内',
})
watch(activeTab, (nextTab) => {
  if (nextTab === 'overview') {
    void refreshOverview({ force: true })
    return
  }
  if (nextTab === 'health') {
    void refreshHealth({ force: true })
  }
})

function applyWorkspaceStatus(health = {}) {
  if (health.import_context) {
    store.setImportContext(health.import_context)
  }
  if (Object.prototype.hasOwnProperty.call(health, 'workspace_ready')) {
    store.setWorkspaceReady(health.workspace_ready)
  }
}

function applyOverviewPayload(payload = {}) {
  schedulerState.value = payload.scheduler || schedulerState.value
  fairnessState.value = payload.fairness || fairnessState.value
  applyWorkspaceStatus(payload.health || {})
}

function applyHealthPayload(payload = {}) {
  selfCheckState.value = payload.selfCheck || selfCheckState.value
  applyWorkspaceStatus(payload.health || {})
}
</script>
<template>
  <div class="dashboard-view">
    <WorkspaceSummary title="总览">
      <template #meta>
        <div class="dashboard-summary__meta ink-inline-meta">
          <span class="status-badge">{{ store.importContext?.source_mode === 'remote' ? '远程导入' : '本机导入' }}</span>
          <span class="status-badge status-badge--ok">{{ formatImportedGpuLabel(importedIndexes) }}</span>
          <span class="status-badge" :class="store.wsConnected ? 'status-badge--ok' : 'status-badge--warning'">
            {{ store.wsConnected ? '实时在线' : '实时离线' }}
          </span>
        </div>
      </template>
      <div class="dashboard-summary__status" :class="`dashboard-summary__status--${summaryTone.tone}`">
        {{ summaryTone.label }} · {{ summaryTone.detail }}
      </div>
      <div class="dashboard-summary__caption">
        如需更改机器或 GPU 范围，直接使用左侧“切换服务器”返回导入层。
      </div>
    </WorkspaceSummary>
    <div class="workspace-nav-layout">
      <div class="workspace-nav-layout__nav">
        <WorkspaceTabs v-model="activeTab" :items="dashboardTabs" />
      </div>
      <div class="workspace-nav-layout__content">
        <DashboardOverviewTab
          v-if="activeTab === 'overview'"
          :model="overviewModel"
        />
        <DashboardLiveWorkspace
          v-else-if="activeTab === 'live'"
          :store="store"
          :summary="liveSummary"
        />
        <DashboardHealthTab v-else :model="healthModel" />
      </div>
    </div>
  </div>
</template>
<style scoped>
.dashboard-view {
  display: grid;
  gap: 16px;
}
.dashboard-summary__caption,
.dashboard-summary__status {
  font-size: 0.92rem;
  line-height: 1.8;
  color: var(--console-text-secondary, var(--text-secondary));
}
.dashboard-summary__meta {
  display: flex;
}
.dashboard-summary__caption {
  color: var(--console-text-muted, var(--text-muted));
}
.dashboard-summary__status {
  width: fit-content;
  padding: 8px 14px;
  border-radius: 999px;
  border: 1px solid var(--console-border, rgba(255, 255, 255, 0.08));
}
.dashboard-summary__status--ok {
  color: #dbe0ff;
  border-color: rgba(94, 106, 210, 0.3);
  background: rgba(94, 106, 210, 0.14);
}
.dashboard-summary__status--warning {
  color: #f7d79d;
  border-color: rgba(244, 185, 93, 0.22);
  background: rgba(244, 185, 93, 0.14);
}
.dashboard-summary__status--critical {
  color: #ffd2de;
  border-color: rgba(255, 120, 148, 0.22);
  background: rgba(255, 120, 148, 0.14);
}
</style>

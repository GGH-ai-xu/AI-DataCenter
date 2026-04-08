<script setup>
import { computed, ref, watch } from 'vue'
import DashboardHealthTab from '../components/dashboard/DashboardHealthTab.vue'
import DashboardLiveWorkspace from '../components/dashboard/DashboardLiveWorkspace.vue'
import DashboardOverviewTab from '../components/dashboard/DashboardOverviewTab.vue'
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
const summaryQuickStats = computed(() => overviewModel.value.quickStats || [])
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
    <section class="tech-card dashboard-summary">
      <div class="dashboard-summary__top">
        <div class="dashboard-summary__copy">
          <div class="section-title">当前导入范围</div>
          <div class="dashboard-summary__lead">
            总览页现在只做一件事：帮你先判断状态，再把你分流到真正该处理的专页。
          </div>
          <div class="dashboard-summary__status" :class="`dashboard-summary__status--${summaryTone.tone}`">
            {{ summaryTone.label }} · {{ summaryTone.detail }}
          </div>
        </div>
        <div class="dashboard-summary__meta">
          <span class="status-badge">{{ store.importContext?.source_mode === 'remote' ? '远程导入' : '本机导入' }}</span>
          <span class="status-badge status-badge--ok">{{ formatImportedGpuLabel(importedIndexes) }}</span>
          <span class="status-badge" :class="store.wsConnected ? 'status-badge--ok' : 'status-badge--warning'">
            {{ store.wsConnected ? '实时在线' : '实时离线' }}
          </span>
        </div>
      </div>
      <div class="dashboard-summary__quick-grid">
        <article
          v-for="item in summaryQuickStats"
          :key="item.label"
          class="dashboard-summary__quick-item"
        >
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
          <small>{{ item.hint }}</small>
        </article>
      </div>
      <div class="dashboard-summary__caption">
        如需更改机器或 GPU 范围，直接使用左侧“切换服务器”返回导入层。
      </div>
    </section>
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
          :governance="{
            budget: schedulerState.budget,
            boardTone: summaryTone,
            governanceTip: overviewModel.summaryLine,
            fairnessOverview: fairnessState.overview,
            fairnessTone: overviewModel.signalCards?.[2] || { tone: 'ok', label: '公平稳定' },
            recommendationList: [],
            yieldQueue: [],
            sourceState: {
              connected: workspaceReady,
              detail: workspaceReady ? `${store.gpus.length} 张已导入 GPU 正在由控制台实时监控。` : '当前还没有有效的导入范围。',
            },
          }"
        />
        <DashboardHealthTab v-else :model="healthModel" />
      </div>
    </div>
  </div>
</template>
<style scoped>
.dashboard-view,
.dashboard-summary__quick-grid {
  display: grid;
  gap: 16px;
}
.dashboard-summary {
  display: grid;
  gap: 16px;
  padding: 20px 24px;
}
.dashboard-summary__top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}
.dashboard-summary__copy {
  display: grid;
  gap: 10px;
  max-width: 72ch;
}
.dashboard-summary__meta {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}
.dashboard-summary__lead,
.dashboard-summary__caption,
.dashboard-summary__status,
.dashboard-summary__quick-item small,
.dashboard-summary__quick-item span {
  font-size: 0.92rem;
  line-height: 1.8;
  color: var(--console-text-secondary, var(--text-secondary));
}
.dashboard-summary__caption,
.dashboard-summary__quick-item span,
.dashboard-summary__quick-item small {
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
.dashboard-summary__quick-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}
.dashboard-summary__quick-item {
  display: grid;
  gap: 6px;
  padding: 16px 18px;
  border-radius: 18px;
  border: 1px solid var(--console-border, rgba(255, 255, 255, 0.08));
  background: var(--console-surface, rgba(255, 255, 255, 0.04));
}
.dashboard-summary__quick-item strong {
  font-size: 1.02rem;
  color: var(--console-text, var(--text-primary));
}
@media (max-width: 980px) {
  .dashboard-summary__top,
  .dashboard-summary__quick-grid {
    display: grid;
    grid-template-columns: 1fr;
  }
  .dashboard-summary__meta {
    justify-content: flex-start;
  }
}
</style>

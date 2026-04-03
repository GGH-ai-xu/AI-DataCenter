<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import DashboardLiveWorkspace from '../components/dashboard/DashboardLiveWorkspace.vue'
import WorkspaceSummary from '../components/workspace/WorkspaceSummary.vue'
import WorkspaceTabs from '../components/workspace/WorkspaceTabs.vue'
import { formatImportedGpuLabel } from '../lib/importContext.js'
import { useAppStore } from '../stores/app.js'
import { useDashboardData } from '../composables/useDashboardData.js'

const router = useRouter()
const store = useAppStore()
const activeTab = ref('overview')
const schedulerState = ref({
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
})
const fairnessState = ref({
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
})
const selfCheckState = ref({
  summary: {
    status: 'warning',
    title: '等待导入后的治理巡检',
    message: '当前总览只围绕本次导入范围展示治理、监控与历史能力。',
  },
  checks: [],
  ws_connections: 0,
  llm_available: false,
})

const dashboardTabs = [
  { key: 'overview', label: '概览', desc: '导入范围与分流' },
  { key: 'health', label: '巡检', desc: '链路状态与提醒' },
  { key: 'live', label: '实时态势', desc: '已导入 GPU 实况' },
]
const overviewRoutes = [
  { label: '进入治理台', desc: '预算、限功率与调度动作', path: '/scheduler', stamp: '治' },
  { label: '进入任务台', desc: '暂停、恢复、终止导入范围内任务', path: '/tasks', stamp: '令' },
  { label: '进入风险台', desc: '处理导入范围内告警', path: '/alerts', stamp: '警' },
  { label: '进入复盘台', desc: '查看节能测算与历史效果', path: '/energy', stamp: '证' },
]

const { dashboardSummary } = useDashboardData({
  onGovernanceData: applyGovernancePayload,
})

const workspaceReady = computed(() => store.workspaceReady)
const importedIndexes = computed(() => store.importContext?.imported_gpu_indexes || [])
const fairnessOverview = computed(() => fairnessState.value.overview || {})
const yieldQueue = computed(() => (fairnessState.value.yield_candidates || []).slice(0, 4))
const liveSummary = computed(() => ({
  ...dashboardSummary.value,
  criticalAlertCount: (dashboardSummary.value.criticalAlerts || []).length,
}))
const sourceState = computed(() => ({
  connected: workspaceReady.value,
  gpu_count: store.gpus.length,
  detail: workspaceReady.value
    ? `${store.gpus.length} 张已导入 GPU 正在由控制台实时监控。`
    : '当前还没有有效的导入范围。',
}))
const governanceTip = computed(() => {
  if (!workspaceReady.value) return '请先在导入层选择要进入控制台的 GPU。'
  if (schedulerState.value.budget?.is_exceeded) return '当前导入范围已超出预算，应先收口总功率。'
  if ((liveSummary.value.criticalAlertCount || 0) > 0) return '导入范围内存在严重告警，优先进入风险台处理。'
  if (yieldQueue.value.length) return `已识别 ${yieldQueue.value.length} 个候选让路任务，可直接进入任务台处置。`
  return '当前导入范围运行平稳，适合继续治理与观察。'
})
const boardTone = computed(() => {
  if (schedulerState.value.budget?.is_exceeded) {
    return {
      badge: '预算超限',
      title: '导入范围需要立即收口预算',
      color: '#9A1730',
      border: 'rgba(196, 30, 58, 0.18)',
      bg: 'rgba(196, 30, 58, 0.08)',
    }
  }
  if ((liveSummary.value.criticalAlertCount || 0) > 0) {
    return {
      badge: '风险待处理',
      title: '导入范围内存在需要优先确认的告警',
      color: '#8A6510',
      border: 'rgba(212, 175, 55, 0.18)',
      bg: 'rgba(212, 175, 55, 0.12)',
    }
  }
  return {
    badge: '治理稳定',
    title: '控制台已完全收口到本次导入范围',
    color: '#2F6A46',
    border: 'rgba(46, 139, 87, 0.18)',
    bg: 'rgba(46, 139, 87, 0.08)',
  }
})
const fairnessTone = computed(() => {
  if (fairnessOverview.value.level === 'critical') return { label: '公平紧张', color: '#9A1730', bg: 'rgba(196, 30, 58, 0.08)' }
  if (fairnessOverview.value.level === 'watch') return { label: '公平观察', color: '#8A6510', bg: 'rgba(212, 175, 55, 0.12)' }
  return { label: '公平稳定', color: '#2F6A46', bg: 'rgba(46, 139, 87, 0.08)' }
})
const recommendationList = computed(() => {
  const items = fairnessState.value.recommendations || []
  return items.length ? items : ['控制台只显示已导入 GPU；如需更改范围，请重新进入导入层扫描并提交。']
})
const healthCards = computed(() => [
  { label: '导入范围', value: formatImportedGpuLabel(importedIndexes.value) },
  { label: '实时连接', value: store.wsConnected ? '在线' : '离线' },
  { label: 'AI 助手', value: selfCheckState.value.llm_available ? '已启用' : '未启用' },
  { label: 'WebSocket', value: `${Number(selfCheckState.value.ws_connections || 0)} 条` },
])
const governanceProps = computed(() => ({
  budget: schedulerState.value.budget || {},
  boardTone: boardTone.value,
  governanceTip: governanceTip.value,
  fairnessOverview: fairnessOverview.value,
  fairnessTone: fairnessTone.value,
  recommendationList: recommendationList.value,
  yieldQueue: yieldQueue.value,
  sourceState: sourceState.value,
}))

function applyGovernancePayload(payload) {
  schedulerState.value = payload.scheduler || schedulerState.value
  fairnessState.value = payload.fairness || fairnessState.value
  selfCheckState.value = payload.selfCheck || selfCheckState.value
  if (payload.health?.import_context) {
    store.setImportContext(payload.health.import_context)
  }
  if (Object.prototype.hasOwnProperty.call(payload.health || {}, 'workspace_ready')) {
    store.setWorkspaceReady(payload.health.workspace_ready)
  }
}
</script>

<template>
  <div class="dashboard-view">
    <WorkspaceSummary title="治理总览">
      <template #meta>
        <div class="dashboard-summary__meta">
          <span class="status-badge">{{ store.importContext?.source_mode === 'remote' ? '远程导入' : '本机导入' }}</span>
          <span class="status-badge status-badge--ok">{{ formatImportedGpuLabel(importedIndexes) }}</span>
          <span class="status-badge" :class="store.wsConnected ? 'status-badge--ok' : 'status-badge--warning'">
            {{ store.wsConnected ? '实时在线' : '实时离线' }}
          </span>
        </div>
      </template>
      <div>
        当前控制台只管理本次导入选中的 GPU。接入方式、本地/远程选择和重新扫描逻辑已经全部迁到导入层。
      </div>
    </WorkspaceSummary>

    <div class="workspace-nav-layout">
      <div class="workspace-nav-layout__nav">
        <WorkspaceTabs v-model="activeTab" :items="dashboardTabs" />
      </div>

      <div class="workspace-nav-layout__content">
        <template v-if="activeTab === 'overview'">
          <div class="overview-layout">
            <section class="tech-card overview-card">
              <div class="section-title">导入范围摘要</div>
              <div class="overview-card__hero">{{ governanceTip }}</div>
              <div class="overview-card__facts">
                <div class="overview-card__fact">
                  <span>已导入 GPU</span>
                  <strong class="stat-value">{{ importedIndexes.length }}</strong>
                </div>
                <div class="overview-card__fact">
                  <span>实时任务</span>
                  <strong class="stat-value">{{ store.processes.length }}</strong>
                </div>
                <div class="overview-card__fact">
                  <span>严重告警</span>
                  <strong class="stat-value">{{ liveSummary.criticalAlertCount }}</strong>
                </div>
                <div class="overview-card__fact">
                  <span>活跃用户</span>
                  <strong class="stat-value">{{ liveSummary.activeUsers }}</strong>
                </div>
              </div>
            </section>

            <section class="tech-card overview-card">
              <div class="section-title">工作分流</div>
              <div class="overview-routes">
                <button
                  v-for="item in overviewRoutes"
                  :key="item.path"
                  type="button"
                  class="overview-route"
                  @click="router.push(item.path)"
                >
                  <span class="overview-route__stamp">{{ item.stamp }}</span>
                  <span class="overview-route__body">
                    <strong>{{ item.label }}</strong>
                    <small>{{ item.desc }}</small>
                  </span>
                </button>
              </div>
            </section>
          </div>
        </template>

        <template v-if="activeTab === 'health'">
          <section class="tech-card dashboard-health">
            <div class="section-title">主体巡检</div>
            <div class="dashboard-health__summary">{{ selfCheckState.summary?.message }}</div>
            <div class="dashboard-health__grid">
              <div v-for="item in healthCards" :key="item.label" class="dashboard-health__item">
                <span>{{ item.label }}</span>
                <strong>{{ item.value }}</strong>
              </div>
            </div>
            <div class="dashboard-health__checks">
              <div v-for="item in (selfCheckState.checks || []).slice(0, 5)" :key="item.key" class="dashboard-health__check">
                <span class="status-badge" :class="item.status === 'ok' ? 'status-badge--ok' : item.status === 'critical' ? 'status-badge--critical' : 'status-badge--warning'">
                  {{ item.label }}
                </span>
                <div>{{ item.detail }}</div>
              </div>
            </div>
          </section>
        </template>

        <template v-if="workspaceReady && activeTab === 'live'">
          <DashboardLiveWorkspace :store="store" :summary="liveSummary" :governance="governanceProps" />
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dashboard-view,
.dashboard-summary__meta,
.overview-layout,
.overview-routes,
.dashboard-health,
.dashboard-health__grid,
.dashboard-health__checks {
  display: grid;
  gap: 16px;
}

.dashboard-summary__meta {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.overview-layout {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.overview-card,
.dashboard-health {
  padding: 20px;
}

.overview-card__hero,
.dashboard-health__summary,
.dashboard-health__check div {
  font-size: 0.88rem;
  line-height: 1.8;
  color: var(--text-secondary);
}

.overview-card__facts,
.dashboard-health__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.overview-card__fact,
.dashboard-health__item,
.dashboard-health__check,
.overview-route {
  display: grid;
  gap: 6px;
  padding: 14px;
  border-radius: 18px;
  border: 1px solid rgba(26, 26, 26, 0.05);
  background: rgba(255, 252, 247, 0.76);
}

.overview-route {
  grid-template-columns: 34px minmax(0, 1fr);
  align-items: start;
  text-align: left;
}

.overview-route__stamp {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 12px;
  color: var(--ink-vermillion);
  background: rgba(196, 30, 58, 0.08);
  font-family: var(--font-seal);
}

.overview-route__body {
  display: grid;
  gap: 4px;
}

.overview-route__body small,
.overview-card__fact span,
.dashboard-health__item span {
  font-size: 0.76rem;
  color: var(--text-muted);
}

@media (max-width: 980px) {
  .overview-layout,
  .overview-card__facts,
  .dashboard-health__grid {
    grid-template-columns: 1fr;
  }
}
</style>

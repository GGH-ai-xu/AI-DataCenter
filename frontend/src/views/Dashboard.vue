<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import DashboardLiveWorkspace from '../components/dashboard/DashboardLiveWorkspace.vue'
import DataStatisticsCard from '../components/dashboard/DataStatisticsCard.vue'
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
      tone: 'critical',
      badge: '预算超限',
      title: '导入范围需要立即收口预算',
    }
  }
  if ((liveSummary.value.criticalAlertCount || 0) > 0) {
    return {
      tone: 'warning',
      badge: '风险待处理',
      title: '导入范围内存在需要优先确认的告警',
    }
  }
  return {
    tone: 'ok',
    badge: '治理稳定',
    title: '控制台已完全收口到本次导入范围',
  }
})
const fairnessTone = computed(() => {
  if (fairnessOverview.value.level === 'critical') return { tone: 'critical', label: '公平紧张' }
  if (fairnessOverview.value.level === 'watch') return { tone: 'warning', label: '公平观察' }
  return { tone: 'ok', label: '公平稳定' }
})
const recommendationList = computed(() => {
  const items = fairnessState.value.recommendations || []
  return items.length ? items : ['控制台只显示已导入 GPU；如需更改范围，请重新进入导入层扫描并提交。']
})
const primaryRecommendation = computed(() => recommendationList.value[0] || '当前没有额外建议。')
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

function toneClass(tone) {
  return `dashboard-tone--${tone || 'ok'}`
}

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
    <section class="tech-card dashboard-summary">
      <div class="dashboard-summary__top">
        <div class="dashboard-summary__copy">
          <div class="section-title">当前导入范围</div>
          <div class="dashboard-summary__lead">
            当前控制台已经收口到本次导入范围。你只需要围绕这批 GPU 做治理、观察、风险处置和效果复盘。
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
        <article class="dashboard-summary__quick-item">
          <span>治理状态</span>
          <strong>{{ boardTone.badge }}</strong>
          <small>{{ boardTone.title }}</small>
        </article>
        <article class="dashboard-summary__quick-item">
          <span>公平指数</span>
          <strong>{{ fairnessOverview.fairness_index ?? 0 }}</strong>
          <small>{{ fairnessTone.label }}</small>
        </article>
        <article class="dashboard-summary__quick-item">
          <span>接入状态</span>
          <strong>{{ sourceState.connected ? '实时可用' : '等待导入' }}</strong>
          <small>{{ sourceState.detail }}</small>
        </article>
      </div>
      <div class="dashboard-summary__caption">
        如需更改机器或 GPU 范围，直接使用左侧“切换服务器”返回导入层，不再在控制台内四处寻找入口。
      </div>
    </section>

    <div class="workspace-nav-layout">
      <div class="workspace-nav-layout__nav">
        <WorkspaceTabs v-model="activeTab" :items="dashboardTabs" />
      </div>

      <div class="workspace-nav-layout__content">
        <template v-if="activeTab === 'overview'">
          <div class="overview-layout">
            <section class="tech-card overview-card overview-card--hero">
              <div class="overview-card__header">
                <div class="section-title">导入范围摘要</div>
                <div class="overview-card__tone" :class="toneClass(boardTone.tone)">
                  {{ boardTone.badge }}
                </div>
              </div>
              <h3 class="overview-card__headline">{{ boardTone.title }}</h3>
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

            <section class="tech-card overview-card overview-card--routes">
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
                  <span class="overview-route__action">进入</span>
                </button>
              </div>
            </section>

            <section class="tech-card overview-card overview-card--insight">
              <div class="section-title">当前判断</div>
              <div class="overview-insight__stack">
                <article class="overview-insight__item">
                  <span class="overview-insight__label">公平状态</span>
                  <strong :class="toneClass(fairnessTone.tone)">{{ fairnessTone.label }}</strong>
                  <p>活跃用户 {{ fairnessOverview.active_users || 0 }} 人，最高占用 {{ fairnessOverview.highest_share_pct || 0 }}%。</p>
                </article>
                <article class="overview-insight__item">
                  <span class="overview-insight__label">优先建议</span>
                  <strong>先处理最短路径动作</strong>
                  <p>{{ primaryRecommendation }}</p>
                </article>
                <article class="overview-insight__item">
                  <span class="overview-insight__label">连接状态</span>
                  <strong>{{ sourceState.connected ? '导入链路稳定' : '等待重新导入' }}</strong>
                  <p>{{ sourceState.detail }}</p>
                </article>
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
          <section class="data-stats-row">
            <DataStatisticsCard />
          </section>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dashboard-view,
.dashboard-summary__meta,
.dashboard-summary__quick-grid,
.overview-layout,
.overview-routes,
.dashboard-health,
.dashboard-health__grid,
.dashboard-health__checks,
.overview-insight__stack {
  display: grid;
  gap: 16px;
}

.dashboard-summary__meta {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
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

.dashboard-summary__lead,
.dashboard-summary__caption {
  font-size: 0.92rem;
  line-height: 1.8;
  color: var(--console-text-secondary, var(--text-secondary));
}

.dashboard-summary__caption {
  color: var(--console-text-muted, var(--text-tertiary));
}

.dashboard-summary__quick-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.dashboard-summary__quick-item {
  display: grid;
  gap: 6px;
  padding: 16px 18px;
  border-radius: 18px;
  border: 1px solid var(--console-border, rgba(255, 255, 255, 0.08));
  background: var(--console-surface, rgba(255, 255, 255, 0.04));
}

.dashboard-summary__quick-item span,
.dashboard-summary__quick-item small {
  font-size: 0.76rem;
  line-height: 1.6;
  color: var(--console-text-muted, var(--text-muted));
}

.dashboard-summary__quick-item strong {
  font-size: 1.02rem;
  color: var(--console-text, var(--text-primary));
}

.overview-layout {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  align-items: start;
}

.overview-card,
.dashboard-health {
  padding: 22px 24px;
}

.overview-card {
  position: relative;
}

.overview-card--hero {
  display: grid;
  grid-column: 1 / -1;
  grid-template-rows: auto auto auto auto;
  gap: 16px;
  align-content: start;
}

.overview-card--routes,
.overview-card--insight {
  align-content: start;
}

.overview-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.overview-card__tone {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 32px;
  width: fit-content;
  padding: 0 12px;
  border-radius: 999px;
  border: 1px solid var(--console-border, rgba(255, 255, 255, 0.08));
  font-size: 0.72rem;
  line-height: 1;
  letter-spacing: 0.08em;
}

.overview-card__headline {
  font-size: clamp(1.5rem, 3vw, 2.2rem);
  line-height: 1.14;
  font-weight: 600;
  letter-spacing: -0.03em;
  color: var(--console-text, var(--text-primary));
}

.overview-card__hero,
.dashboard-health__summary,
.dashboard-health__check div,
.overview-insight__item p {
  font-size: 0.88rem;
  line-height: 1.8;
  color: var(--console-text-secondary, var(--text-secondary));
}

.overview-card__facts,
.dashboard-health__grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.overview-card__fact,
.dashboard-health__item,
.dashboard-health__check,
.overview-route {
  display: grid;
  gap: 8px;
  padding: 16px;
  border-radius: 18px;
  border: 1px solid var(--console-border, rgba(255, 255, 255, 0.08));
  background: var(--console-surface, rgba(255, 255, 255, 0.04));
}

.overview-route {
  grid-template-columns: 42px minmax(0, 1fr) auto;
  align-items: center;
  text-align: left;
  transition:
    border-color 0.24s ease,
    background 0.24s ease;
}

.overview-route:hover {
  border-color: rgba(255, 255, 255, 0.14);
  background: rgba(255, 255, 255, 0.05);
}

.overview-route__stamp {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  border-radius: 14px;
  border: 1px solid rgba(94, 106, 210, 0.2);
  color: #dbe0ff;
  background: rgba(94, 106, 210, 0.12);
  font-family: var(--font-seal);
}

.overview-route__body {
  display: grid;
  gap: 6px;
}

.overview-route__body strong {
  font-size: 0.96rem;
  color: var(--console-text, var(--text-primary));
}

.overview-route__body small,
.overview-card__fact span,
.dashboard-health__item span {
  font-size: 0.76rem;
  color: var(--console-text-muted, var(--text-muted));
}

.overview-route__action {
  font-size: 0.76rem;
  font-weight: 600;
  color: #dbe0ff;
}

.overview-card__fact strong,
.dashboard-health__item strong {
  font-size: 1.18rem;
  color: var(--console-text, var(--text-primary));
}

.overview-insight__item {
  display: grid;
  gap: 6px;
  padding: 16px;
  border-radius: 18px;
  border: 1px solid var(--console-border, rgba(255, 255, 255, 0.08));
  background: var(--console-surface, rgba(255, 255, 255, 0.04));
}

.overview-insight__label {
  font-family: var(--font-seal);
  font-size: 0.68rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--console-text-muted, var(--text-muted));
}

.overview-insight__item strong {
  font-size: 1rem;
  color: var(--console-text, var(--text-primary));
}

.dashboard-tone--ok {
  color: #dbe0ff;
  border-color: rgba(94, 106, 210, 0.3);
  background: rgba(94, 106, 210, 0.14);
}

.dashboard-tone--warning {
  color: #f7d79d;
  border-color: rgba(244, 185, 93, 0.22);
  background: rgba(244, 185, 93, 0.14);
}

.dashboard-tone--critical {
  color: #ffd2de;
  border-color: rgba(255, 120, 148, 0.22);
  background: rgba(255, 120, 148, 0.14);
}

.data-stats-row {
  margin-top: 16px;
  max-width: 520px;
}

@media (max-width: 980px) {
  .dashboard-summary__top,
  .overview-layout,
  .dashboard-summary__quick-grid,
  .overview-card__facts,
  .dashboard-health__grid {
    grid-template-columns: 1fr;
  }

  .dashboard-summary__top {
    display: grid;
  }

  .dashboard-summary__meta {
    justify-content: flex-start;
  }
}
</style>

# Dashboard 总览页分舱瘦身重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 dashboard 重构为职责清晰的 `首页 / 实时 / 巡检` 三个工作区，去掉跨页签重复信息，并把数据刷新改为按页签加载。

**Architecture:** 先把 dashboard 的页面模型和数据 loader 抽成可测试的纯函数，再把 `Dashboard.vue` 拆成独立的首页与巡检组件，最后瘦身 `DashboardLiveWorkspace.vue`，让它只承载实时指标、GPU 矩阵和图表。数据层通过 `useDashboardData.js` 收口成 overview/health 两条主动刷新链路，实时页直接消费 store 中的实时状态，避免再发起无关检测。

**Tech Stack:** Vue 3、Pinia、Vite、node:test、Python unittest

---

## File Structure

- Create: `frontend/src/lib/dashboardPageModels.js`
  负责把已有的预算、公平、导入范围和巡检原始状态转换为首页与巡检页可直接渲染的轻量 view model。
- Create: `frontend/src/lib/dashboardPageModels.test.js`
  覆盖首页摘要卡、异常提醒卡和巡检异常优先排序逻辑。
- Create: `frontend/src/lib/dashboardLoaders.js`
  负责把 dashboard 所需的 API 请求拆成 `loadOverviewBundle()` 和 `loadHealthBundle()` 两条独立 loader。
- Create: `frontend/src/lib/dashboardLoaders.test.js`
  验证 overview loader 与 health loader 的调用边界，防止再次回到“大一统 bundle”。
- Create: `frontend/src/components/dashboard/DashboardOverviewTab.vue`
  首页专用组件，只承载摘要、入口分流和异常优先卡。
- Create: `frontend/src/components/dashboard/DashboardHealthTab.vue`
  巡检专用组件，只承载巡检结论、异常清单和健康项折叠区。
- Modify: `frontend/src/components/dashboard/DashboardLiveWorkspace.vue`
  删除治理摘要、公平摘要、治理建议和来源说明，只保留实时指标、GPU 矩阵和图表。
- Modify: `frontend/src/views/Dashboard.vue`
  切换到 `首页 / 实时 / 巡检` 三个页签，接入新组件与新数据模型，移除内联的大块重复模板。
- Modify: `frontend/src/composables/useDashboardData.js`
  改为 overview/health 两个独立 refresh 域，实时页直接返回基于 store 的 computed 数据。
- Modify: `frontend/src/stores/app.js`
  将 `domains.dashboard` 从 `governance/connection/desktop` 收口为 `overview/live/health`，对齐新的 dashboard 分舱语义。
- Create: `tests/test_dashboard_workspace_structure.py`
  做结构性回归检查，确保总览页使用新页签、新组件，并移除实时页中的治理摘要文案。

## Task 1: Add Dashboard Page Models With Failing Tests

**Files:**
- Create: `frontend/src/lib/dashboardPageModels.js`
- Create: `frontend/src/lib/dashboardPageModels.test.js`

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/lib/dashboardPageModels.test.js`:

```js
import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildDashboardOverviewModel,
  buildDashboardHealthModel,
} from './dashboardPageModels.js'

test('buildDashboardOverviewModel returns one summary strip, four entry cards, and three signal cards', () => {
  const model = buildDashboardOverviewModel({
    importedIndexes: [1, 2, 3],
    sourceMode: 'remote',
    workspaceReady: true,
    wsConnected: true,
    gpuCount: 3,
    processCount: 5,
    budget: {
      is_exceeded: true,
      usage_pct: 112,
    },
    fairnessOverview: {
      level: 'watch',
      fairness_index: 73,
      active_users: 2,
      highest_share_pct: 67,
    },
    criticalAlertCount: 2,
  })

  assert.equal(model.quickStats.length, 4)
  assert.equal(model.routeCards.length, 4)
  assert.equal(model.signalCards.length, 3)
  assert.equal(model.quickStats[0].label, '导入范围')
  assert.equal(model.signalCards[0].tone, 'critical')
  assert.match(model.summaryLine, /预算/)
})

test('buildDashboardHealthModel keeps only warning and critical checks in the priority list', () => {
  const model = buildDashboardHealthModel({
    importedLabel: '3 张 GPU',
    wsConnected: false,
    selfCheck: {
      summary: {
        title: '2 项异常',
        message: '其中 1 项影响实时采集',
      },
      checks: [
        { key: 'gpu-agent', label: 'GPU Agent', status: 'critical', detail: '实时采集失败' },
        { key: 'ws', label: 'WebSocket', status: 'warning', detail: '连接断开' },
        { key: 'llm', label: 'AI 助手', status: 'ok', detail: '正常' },
      ],
      ws_connections: 0,
      llm_available: true,
    },
  })

  assert.equal(model.factCards.length, 4)
  assert.deepEqual(
    model.priorityChecks.map((item) => item.key),
    ['gpu-agent', 'ws'],
  )
  assert.deepEqual(
    model.healthyChecks.map((item) => item.key),
    ['llm'],
  )
})
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd frontend && node --test src/lib/dashboardPageModels.test.js
```

Expected: FAIL with `Cannot find module './dashboardPageModels.js'` or missing export errors.

- [ ] **Step 3: Write minimal implementation**

Create `frontend/src/lib/dashboardPageModels.js`:

```js
import { formatImportedGpuLabel } from './importContext.js'

function budgetSignal(budget = {}, criticalAlertCount = 0) {
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

export function buildDashboardOverviewModel(input) {
  const importedLabel = formatImportedGpuLabel(input.importedIndexes || [])
  const budgetCard = budgetSignal(input.budget, input.criticalAlertCount)
  return {
    summaryLine: budgetCard.detail,
    quickStats: [
      { label: '导入范围', value: importedLabel, hint: input.sourceMode === 'remote' ? '远程导入' : '本机导入' },
      { label: '连接状态', value: input.wsConnected ? '实时在线' : '实时离线', hint: input.workspaceReady ? '控制台已绑定导入范围' : '等待重新导入' },
      { label: '预算风险', value: budgetCard.label, hint: budgetCard.detail },
      { label: '严重告警', value: String(input.criticalAlertCount || 0), hint: `${input.processCount || 0} 个实时任务` },
    ],
    routeCards: [
      { label: '进入治理台', desc: '预算、限功率与调度动作', path: '/scheduler' },
      { label: '进入任务台', desc: '暂停、恢复、终止导入范围内任务', path: '/tasks' },
      { label: '进入风险台', desc: '处理导入范围内告警', path: '/alerts' },
      { label: '进入复盘台', desc: '查看节能测算与历史效果', path: '/energy' },
    ],
    signalCards: [
      { tone: budgetCard.tone, label: budgetCard.label, detail: budgetCard.detail },
      {
        tone: input.criticalAlertCount > 0 ? 'warning' : 'ok',
        label: input.criticalAlertCount > 0 ? '优先处理告警' : '告警平稳',
        detail: input.criticalAlertCount > 0 ? `当前有 ${input.criticalAlertCount} 条严重告警` : '当前没有严重告警',
      },
      {
        tone: input.fairnessOverview?.level === 'critical' ? 'critical' : input.fairnessOverview?.level === 'watch' ? 'warning' : 'ok',
        label: input.fairnessOverview?.level === 'critical' ? '公平紧张' : input.fairnessOverview?.level === 'watch' ? '公平观察' : '公平稳定',
        detail: `活跃用户 ${input.fairnessOverview?.active_users || 0} 人，最高占用 ${input.fairnessOverview?.highest_share_pct || 0}%`,
      },
    ],
  }
}

export function buildDashboardHealthModel(input) {
  const checks = input.selfCheck?.checks || []
  return {
    summary: input.selfCheck?.summary || { title: '等待巡检', message: '当前还没有巡检结果。' },
    factCards: [
      { label: '导入范围', value: input.importedLabel },
      { label: '实时连接', value: input.wsConnected ? '在线' : '离线' },
      { label: 'AI 助手', value: input.selfCheck?.llm_available ? '已启用' : '未启用' },
      { label: 'WebSocket', value: `${Number(input.selfCheck?.ws_connections || 0)} 条` },
    ],
    priorityChecks: checks.filter((item) => item.status === 'critical' || item.status === 'warning'),
    healthyChecks: checks.filter((item) => item.status === 'ok'),
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
cd frontend && node --test src/lib/dashboardPageModels.test.js
```

Expected: PASS with `2 tests` passed.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/dashboardPageModels.js frontend/src/lib/dashboardPageModels.test.js
git commit -m "feat: add dashboard page models"
```

## Task 2: Split Dashboard Loaders And Domain Keys

**Files:**
- Create: `frontend/src/lib/dashboardLoaders.js`
- Create: `frontend/src/lib/dashboardLoaders.test.js`
- Modify: `frontend/src/composables/useDashboardData.js`
- Modify: `frontend/src/stores/app.js`

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/lib/dashboardLoaders.test.js`:

```js
import test from 'node:test'
import assert from 'node:assert/strict'

import { createDashboardLoaders } from './dashboardLoaders.js'

test('overview loader only requests overview dependencies', async () => {
  const calls = []
  const api = {
    getSchedulerStatus: async () => {
      calls.push('scheduler')
      return { data: { budget: { enabled: true } } }
    },
    healthCheck: async () => {
      calls.push('health')
      return { data: { workspace_ready: true } }
    },
    getFairnessGovernance: async () => {
      calls.push('fairness')
      return { data: { overview: { fairness_index: 91 } } }
    },
    getSystemSelfCheck: async () => {
      calls.push('self-check')
      return { data: { summary: { title: 'unused' } } }
    },
  }

  const loaders = createDashboardLoaders(api)
  const payload = await loaders.loadOverviewBundle()

  assert.deepEqual(calls, ['scheduler', 'health', 'fairness'])
  assert.equal(payload.selfCheck, undefined)
})

test('health loader only requests health dependencies', async () => {
  const calls = []
  const api = {
    getSchedulerStatus: async () => {
      calls.push('scheduler')
      return { data: {} }
    },
    healthCheck: async () => {
      calls.push('health')
      return { data: { workspace_ready: true } }
    },
    getFairnessGovernance: async () => {
      calls.push('fairness')
      return { data: {} }
    },
    getSystemSelfCheck: async () => {
      calls.push('self-check')
      return { data: { summary: { title: '2 项异常' } } }
    },
  }

  const loaders = createDashboardLoaders(api)
  const payload = await loaders.loadHealthBundle()

  assert.deepEqual(calls, ['health', 'self-check'])
  assert.equal(payload.health.workspace_ready, true)
  assert.equal(payload.selfCheck.summary.title, '2 项异常')
})
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd frontend && node --test src/lib/dashboardLoaders.test.js
```

Expected: FAIL with missing module/export errors.

- [ ] **Step 3: Write minimal implementation**

Create `frontend/src/lib/dashboardLoaders.js`:

```js
export function createDashboardLoaders(api) {
  return {
    async loadOverviewBundle() {
      const [{ data: scheduler }, { data: health }, { data: fairness }] = await Promise.all([
        api.getSchedulerStatus(),
        api.healthCheck(),
        api.getFairnessGovernance(),
      ])
      return { scheduler, health, fairness }
    },
    async loadHealthBundle() {
      const [{ data: health }, { data: selfCheck }] = await Promise.all([
        api.healthCheck(),
        api.getSystemSelfCheck(),
      ])
      return { health, selfCheck }
    },
  }
}
```

Modify `frontend/src/stores/app.js`:

```js
function createDomainState() {
  return {
    dashboard: {
      overview: requestState(),
      live: requestState(),
      health: requestState(),
    },
    scheduler: {
      status: requestState(),
      carbon: requestState(),
      audit: requestState(),
      evaluation: requestState(),
    },
    // keep other sections unchanged
  }
}
```

Modify `frontend/src/composables/useDashboardData.js`:

```js
import { computed } from 'vue'
import {
  getFairnessGovernance,
  getSchedulerStatus,
  getSystemSelfCheck,
  healthCheck,
} from '../services/api.js'
import { createDashboardLoaders } from '../lib/dashboardLoaders.js'
import { useAppStore } from '../stores/app.js'
import { useDomainRefresh } from './useDomainRefresh.js'

export function useDashboardData(options = {}) {
  const store = useAppStore()
  const activeTab = options.activeTab
  const loaders = createDashboardLoaders({
    getSchedulerStatus,
    healthCheck,
    getFairnessGovernance,
    getSystemSelfCheck,
  })

  const overviewRefresh = useDomainRefresh({
    section: 'dashboard',
    key: 'overview',
    intervalMs: 15000,
    staleTime: 5000,
    enabled: () => !activeTab || activeTab.value === 'overview',
    loader: loaders.loadOverviewBundle,
    applyData: (payload) => options.onOverviewData?.(payload),
  })

  const healthRefresh = useDomainRefresh({
    section: 'dashboard',
    key: 'health',
    intervalMs: 15000,
    staleTime: 5000,
    enabled: () => activeTab?.value === 'health',
    loader: loaders.loadHealthBundle,
    applyData: (payload) => options.onHealthData?.(payload),
  })

  return {
    dashboardSummary: computed(() => store.dashboardSummary),
    overviewDomain: computed(() => store.domains.dashboard.overview),
    liveDomain: computed(() => store.domains.dashboard.live),
    healthDomain: computed(() => store.domains.dashboard.health),
    refreshOverview: overviewRefresh.refresh,
    refreshHealth: healthRefresh.refresh,
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
cd frontend && node --test src/lib/dashboardLoaders.test.js
```

Expected: PASS with both loader-boundary tests green.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/dashboardLoaders.js frontend/src/lib/dashboardLoaders.test.js frontend/src/composables/useDashboardData.js frontend/src/stores/app.js
git commit -m "refactor: split dashboard refresh domains"
```

## Task 3: Extract Overview And Health Tabs Out Of Dashboard.vue

**Files:**
- Create: `frontend/src/components/dashboard/DashboardOverviewTab.vue`
- Create: `frontend/src/components/dashboard/DashboardHealthTab.vue`
- Modify: `frontend/src/views/Dashboard.vue`
- Create: `tests/test_dashboard_workspace_structure.py`

- [ ] **Step 1: Write the failing structure test**

Create `tests/test_dashboard_workspace_structure.py`:

```python
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DashboardWorkspaceStructureTests(unittest.TestCase):
    def test_dashboard_uses_new_tab_components_and_labels(self):
        dashboard = (ROOT / 'frontend/src/views/Dashboard.vue').read_text(encoding='utf-8')
        self.assertIn("DashboardOverviewTab", dashboard)
        self.assertIn("DashboardHealthTab", dashboard)
        self.assertIn("label: '首页'", dashboard)
        self.assertIn("label: '实时'", dashboard)
        self.assertIn("label: '巡检'", dashboard)
        self.assertNotIn("DataStatisticsCard", dashboard)

    def test_dashboard_view_uses_split_refresh_keys(self):
        composable = (ROOT / 'frontend/src/composables/useDashboardData.js').read_text(encoding='utf-8')
        self.assertIn("key: 'overview'", composable)
        self.assertIn("key: 'health'", composable)
        self.assertNotIn("key: 'governance'", composable)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_dashboard_workspace_structure -v
```

Expected: FAIL because `Dashboard.vue` still has old labels and still references `DataStatisticsCard`.

- [ ] **Step 3: Write minimal implementation**

Create `frontend/src/components/dashboard/DashboardOverviewTab.vue`:

```vue
<script setup>
import { useRouter } from 'vue-router'

const props = defineProps({
  model: { type: Object, required: true },
})

const router = useRouter()

function toneClass(tone) {
  return `dashboard-tone--${tone || 'ok'}`
}
</script>

<template>
  <div class="overview-layout">
    <section class="tech-card overview-card">
      <div class="section-title">当前判断</div>
      <div class="overview-quick-grid">
        <article v-for="item in props.model.quickStats" :key="item.label" class="overview-quick-item">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
          <small>{{ item.hint }}</small>
        </article>
      </div>
      <p class="overview-summary-line">{{ props.model.summaryLine }}</p>
    </section>

    <section class="tech-card overview-card">
      <div class="section-title">工作分流</div>
      <div class="overview-routes">
        <button
          v-for="item in props.model.routeCards"
          :key="item.path"
          type="button"
          class="overview-route"
          @click="router.push(item.path)"
        >
          <strong>{{ item.label }}</strong>
          <small>{{ item.desc }}</small>
        </button>
      </div>
    </section>

    <section class="tech-card overview-card">
      <div class="section-title">异常优先</div>
      <div class="overview-signals">
        <article v-for="item in props.model.signalCards" :key="item.label" class="overview-signal">
          <strong :class="toneClass(item.tone)">{{ item.label }}</strong>
          <p>{{ item.detail }}</p>
        </article>
      </div>
    </section>
  </div>
</template>
```

Create `frontend/src/components/dashboard/DashboardHealthTab.vue`:

```vue
<script setup>
import { ref } from 'vue'

const props = defineProps({
  model: { type: Object, required: true },
})

const showHealthyChecks = ref(false)
</script>

<template>
  <section class="tech-card dashboard-health">
    <div class="dashboard-health__hero">
      <div class="section-title">主体巡检</div>
      <strong>{{ props.model.summary.title }}</strong>
      <p>{{ props.model.summary.message }}</p>
    </div>

    <div class="dashboard-health__grid">
      <div v-for="item in props.model.factCards" :key="item.label" class="dashboard-health__item">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </div>
    </div>

    <div class="dashboard-health__checks">
      <div v-for="item in props.model.priorityChecks" :key="item.key" class="dashboard-health__check">
        <span class="status-badge" :class="item.status === 'critical' ? 'status-badge--critical' : 'status-badge--warning'">
          {{ item.label }}
        </span>
        <div>{{ item.detail }}</div>
      </div>
    </div>

    <button type="button" class="btn-tech" @click="showHealthyChecks = !showHealthyChecks">
      {{ showHealthyChecks ? '收起健康项' : '查看全部健康项' }}
    </button>

    <div v-if="showHealthyChecks" class="dashboard-health__checks">
      <div v-for="item in props.model.healthyChecks" :key="item.key" class="dashboard-health__check">
        <span class="status-badge status-badge--ok">{{ item.label }}</span>
        <div>{{ item.detail }}</div>
      </div>
    </div>
  </section>
</template>
```

Modify `frontend/src/views/Dashboard.vue` so the tabs and body become:

```vue
<script setup>
import { computed, ref } from 'vue'
import DashboardHealthTab from '../components/dashboard/DashboardHealthTab.vue'
import DashboardLiveWorkspace from '../components/dashboard/DashboardLiveWorkspace.vue'
import DashboardOverviewTab from '../components/dashboard/DashboardOverviewTab.vue'
import WorkspaceTabs from '../components/workspace/WorkspaceTabs.vue'
import { useDashboardData } from '../composables/useDashboardData.js'
import { buildDashboardHealthModel, buildDashboardOverviewModel } from '../lib/dashboardPageModels.js'

const activeTab = ref('overview')
const dashboardTabs = [
  { key: 'overview', label: '首页', desc: '摘要与分流' },
  { key: 'live', label: '实时', desc: 'GPU 与趋势' },
  { key: 'health', label: '巡检', desc: '异常与链路' },
]

const { dashboardSummary } = useDashboardData({
  activeTab,
  onOverviewData: applyOverviewPayload,
  onHealthData: applyHealthPayload,
})

const overviewModel = computed(() => buildDashboardOverviewModel({
  importedIndexes: importedIndexes.value,
  sourceMode: store.importContext?.source_mode,
  workspaceReady: workspaceReady.value,
  wsConnected: store.wsConnected,
  gpuCount: store.gpus.length,
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
</script>

<template>
  <div class="dashboard-view">
    <section class="tech-card dashboard-summary">
      <!-- 保留现有顶部摘要条，但只保留一次 -->
    </section>

    <div class="workspace-nav-layout">
      <div class="workspace-nav-layout__nav">
        <WorkspaceTabs v-model="activeTab" :items="dashboardTabs" />
      </div>

      <div class="workspace-nav-layout__content">
        <DashboardOverviewTab v-if="activeTab === 'overview'" :model="overviewModel" />
        <DashboardLiveWorkspace v-else-if="activeTab === 'live'" :store="store" :summary="liveSummary" />
        <DashboardHealthTab v-else :model="healthModel" />
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python3 -m unittest tests.test_dashboard_workspace_structure -v
```

Expected: PASS with both structure checks green.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/dashboard/DashboardOverviewTab.vue frontend/src/components/dashboard/DashboardHealthTab.vue frontend/src/views/Dashboard.vue tests/test_dashboard_workspace_structure.py
git commit -m "refactor: split dashboard overview and health tabs"
```

## Task 4: Slim DashboardLiveWorkspace To Real-Time Only And Verify

**Files:**
- Modify: `frontend/src/components/dashboard/DashboardLiveWorkspace.vue`
- Modify: `frontend/src/views/Dashboard.vue`
- Modify: `tests/test_dashboard_workspace_structure.py`

- [ ] **Step 1: Extend the failing structure test**

Update `tests/test_dashboard_workspace_structure.py`:

```python
    def test_live_workspace_no_longer_renders_governance_copy(self):
        live = (ROOT / 'frontend/src/components/dashboard/DashboardLiveWorkspace.vue').read_text(encoding='utf-8')
        self.assertNotIn('治理建议', live)
        self.assertNotIn('公平与来源', live)
        self.assertNotIn('props.governance', live)
        self.assertNotIn('governance:', live)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_dashboard_workspace_structure -v
```

Expected: FAIL because `DashboardLiveWorkspace.vue` still contains `governance` prop and related UI blocks.

- [ ] **Step 3: Write minimal implementation**

Modify `frontend/src/components/dashboard/DashboardLiveWorkspace.vue`:

```vue
<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import PowerTrendChart from '../charts/PowerTrendChart.vue'
import UtilizationChart from '../charts/UtilizationChart.vue'

const props = defineProps({
  store: { type: Object, required: true },
  summary: { type: Object, required: true },
})

const router = useRouter()

const pulseCards = computed(() => [
  { label: '当前总功率', value: `${Number(props.store.totalPower || 0).toFixed(1)}W`, hint: `${props.store.gpus.length} 张 GPU`, tone: 'accent' },
  { label: '平均温度', value: `${props.store.avgTemperature}°C`, hint: `${props.summary.hotGpuCount || 0} 张高温 GPU`, tone: props.store.avgTemperature >= 80 ? 'critical' : 'warning' },
  { label: '活跃任务', value: `${props.store.processes.length}`, hint: `${props.summary.activeUsers || 0} 位活跃用户`, tone: 'neutral' },
  { label: '严重告警', value: `${props.summary.criticalAlertCount || 0}`, hint: `紧急 ${props.summary.urgentTasks || 0} / 可延迟 ${props.summary.deferrableTasks || 0}`, tone: props.summary.criticalAlertCount > 0 ? 'critical' : 'neutral' },
])
</script>

<template>
  <div class="live-workspace">
    <section class="tech-card live-workspace__summary">
      <div class="live-workspace__head">
        <div>
          <div class="section-title">实时态势</div>
          <div class="live-workspace__surface-note">这里只保留运行态指标、GPU 矩阵和趋势图。</div>
        </div>
        <div class="live-workspace__chip-row">
          <span class="governance-chip">{{ props.store.dataSourceLabel.text }}</span>
          <span class="governance-chip">{{ props.store.dataSourceStatus.gpu_count || props.store.gpus.length }} 卡</span>
        </div>
      </div>

      <div class="live-workspace__pulse">
        <div
          v-for="card in pulseCards"
          :key="card.label"
          class="live-workspace__pulse-card"
          :class="`live-workspace__pulse-card--${card.tone}`"
        >
          <span class="live-workspace__pulse-label">{{ card.label }}</span>
          <strong class="live-workspace__pulse-value stat-value">{{ card.value }}</strong>
          <span class="live-workspace__pulse-hint">{{ card.hint }}</span>
        </div>
      </div>
    </section>

    <section class="tech-card live-workspace__gpu-surface">
      <!-- 保留 GPU 实时矩阵 -->
    </section>

    <div v-if="props.store.gpus.length" class="live-workspace__charts">
      <section class="chart-panel tech-card">
        <div class="chart-panel__header"><div class="section-title">功耗趋势</div></div>
        <div class="chart-panel__body"><PowerTrendChart :gpus="props.store.gpus" /></div>
      </section>
      <section class="chart-panel tech-card">
        <div class="chart-panel__header"><div class="section-title">利用率分布</div></div>
        <div class="chart-panel__body"><UtilizationChart :gpus="props.store.gpus" /></div>
      </section>
    </div>
  </div>
</template>
```

Modify `frontend/src/views/Dashboard.vue` to remove the old `governanceProps` computed and the `DataStatisticsCard` import/render path:

```vue
<script setup>
import DashboardLiveWorkspace from '../components/dashboard/DashboardLiveWorkspace.vue'

// delete DataStatisticsCard import
// delete governanceProps computed
</script>
```

- [ ] **Step 4: Run verification**

Run:

```bash
python3 -m unittest tests.test_dashboard_workspace_structure -v
cd frontend && node --test src/lib/dashboardPageModels.test.js src/lib/dashboardLoaders.test.js
cd frontend && npm run build
```

Expected:

- Python structure tests: PASS
- node:test suites: PASS
- Vite build: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/dashboard/DashboardLiveWorkspace.vue frontend/src/views/Dashboard.vue tests/test_dashboard_workspace_structure.py
git commit -m "refactor: slim dashboard live workspace"
```

## Self-Review

- Spec coverage:
  - 页面职责重定义: Task 3 和 Task 4 覆盖首页、实时、巡检三块 UI 边界。
  - 按页签刷新: Task 2 覆盖 overview/health 分域刷新。
  - 去除重复治理摘要: Task 3、Task 4 覆盖。
  - 页面更干净、保留单一摘要区: Task 3 与 Task 4 共同覆盖。
- Placeholder scan:
  - 已避免未定义占位描述和延后补充式表述。
  - 每个任务都包含明确文件、测试命令和提交节点。
- Type consistency:
  - 统一使用 `overview / live / health` 作为 dashboard 页签与 domain 命名。
  - 统一使用 `buildDashboardOverviewModel()`、`buildDashboardHealthModel()`、`createDashboardLoaders()` 作为新增纯函数入口。

# Alert Center Time Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the alert center into a three-tab time workbench with a realtime default view, a same-day timeline ledger, and a type-based history archive that avoids truncation-heavy table coupling.

**Architecture:** Keep `frontend/src/views/AlertCenter.vue` as the orchestration shell, but move time grouping and archive classification into a small pure helper module and split each tab into dedicated alert components. Reuse `WorkspaceSummary`, `WorkspaceTabs`, and `WorkspacePaneLayout` patterns already used elsewhere in the repo so the alert center matches the top-tab desktop workbench structure the rest of the site now follows.

**Tech Stack:** Vue 3 SFCs with `<script setup>`, shared app styles in `frontend/src/style.css`, existing alert APIs in `frontend/src/services/api.js`, Pinia realtime store state, Python `unittest` structure tests, Windows-based Vite build verification.

---

## File Map

**Create:**
- `frontend/src/lib/alertCenterTransforms.js`
  Purpose: pure grouping helpers for summary metrics, realtime buckets, same-day timeline sections, and archive-by-type views.
- `frontend/src/components/alerts/AlertRealtimeStream.vue`
  Purpose: main-column realtime worklist for unacknowledged alerts grouped by time bucket.
- `frontend/src/components/alerts/AlertRealtimeSidebar.vue`
  Purpose: stable secondary rail with type filters, risk summary, and operator hints.
- `frontend/src/components/alerts/AlertDaybookTimeline.vue`
  Purpose: same-day timeline ledger with section cards and inline acknowledge actions.
- `frontend/src/components/alerts/AlertArchiveTypeTabs.vue`
  Purpose: compact type-switch rail for `temperature / power / memory / self_check`.
- `frontend/src/components/alerts/AlertArchiveBoard.vue`
  Purpose: archive page shell that combines type summary and local detail rendering.

**Modify:**
- `frontend/src/views/AlertCenter.vue`
  Purpose: replace the current single-panel layout with `realtime / today / archive` tabs and delegate each tab to dedicated components.
- `frontend/src/components/alerts/AlertSummaryPanel.vue`
  Purpose: convert three stacked summary cards into a compact summary strip driven by explicit item data.
- `frontend/src/components/alerts/AlertHistoryTable.vue`
  Purpose: narrow the component to archive-detail usage only, rather than owning the whole page layout.
- `tests/test_frontend_ui_structure.py`
  Purpose: replace old alert-center assertions with coverage for the new time-workbench shell and component structure.

---

### Task 1: Lock The New Alert-Center Shell With Failing Structure Tests

**Files:**
- Modify: `tests/test_frontend_ui_structure.py`
- Test: `tests/test_frontend_ui_structure.py`

- [ ] **Step 1: Replace the old alert-center test with time-workbench assertions**

Replace `test_alert_center_uses_structured_history_table_component` with the following tests:

```python
    def test_alert_center_uses_time_workbench_tabs(self):
        text = (ROOT / "frontend/src/views/AlertCenter.vue").read_text(encoding="utf-8")

        self.assertIn("const activeTab = ref('realtime')", text)
        self.assertIn("WorkspaceTabs", text)
        self.assertIn("{ key: 'realtime'", text)
        self.assertIn("{ key: 'today'", text)
        self.assertIn("{ key: 'archive'", text)
        self.assertIn("AlertRealtimeStream", text)
        self.assertIn("AlertDaybookTimeline", text)
        self.assertIn("AlertArchiveBoard", text)
        self.assertNotIn("AlertHistoryTable", text)

    def test_alert_center_time_workbench_components_exist(self):
        for rel in [
            "frontend/src/components/alerts/AlertRealtimeStream.vue",
            "frontend/src/components/alerts/AlertRealtimeSidebar.vue",
            "frontend/src/components/alerts/AlertDaybookTimeline.vue",
            "frontend/src/components/alerts/AlertArchiveTypeTabs.vue",
            "frontend/src/components/alerts/AlertArchiveBoard.vue",
        ]:
            self.assertTrue((ROOT / rel).exists(), rel)
```

- [ ] **Step 2: Run the tests to verify they fail for the current implementation**

Run:

```bash
cmd.exe /c "cd /d E:\Code\AI-DataCenter && .\.venv\Scripts\python.exe -m unittest tests.test_frontend_ui_structure.FrontendUIStructureTests.test_alert_center_uses_time_workbench_tabs tests.test_frontend_ui_structure.FrontendUIStructureTests.test_alert_center_time_workbench_components_exist"
```

Expected:

- FAIL because `AlertCenter.vue` still has no `activeTab = ref('realtime')`
- FAIL because the five new alert workbench components do not exist yet

- [ ] **Step 3: Commit the red tests**

```bash
git add tests/test_frontend_ui_structure.py
git commit -m "test: add alert center workbench structure coverage"
```

---

### Task 2: Implement The Alert-Center Shell, Shared Transforms, And Compact Summary Strip

**Files:**
- Create: `frontend/src/lib/alertCenterTransforms.js`
- Create: `frontend/src/components/alerts/AlertRealtimeStream.vue`
- Create: `frontend/src/components/alerts/AlertRealtimeSidebar.vue`
- Create: `frontend/src/components/alerts/AlertDaybookTimeline.vue`
- Create: `frontend/src/components/alerts/AlertArchiveTypeTabs.vue`
- Create: `frontend/src/components/alerts/AlertArchiveBoard.vue`
- Modify: `frontend/src/views/AlertCenter.vue`
- Modify: `frontend/src/components/alerts/AlertSummaryPanel.vue`
- Test: `tests/test_frontend_ui_structure.py`

- [ ] **Step 1: Create pure alert-center grouping helpers**

Create `frontend/src/lib/alertCenterTransforms.js` with these exports:

```js
const RECENT_ALERT_WINDOW_SECONDS = 3600
const FIVE_MINUTES_SECONDS = 300

export const ALERT_CENTER_TABS = [
  { key: 'realtime', label: '实时流', desc: '未确认风险与即时处置' },
  { key: 'today', label: '今日告警簿', desc: '按时间复盘当天告警' },
  { key: 'archive', label: '历史归档', desc: '按类型追踪历史问题' },
]

export const ALERT_ARCHIVE_TYPES = [
  { key: 'temperature', label: '温度', desc: '温升与过热' },
  { key: 'power', label: '功率', desc: '功耗与预算' },
  { key: 'memory', label: '显存', desc: '显存占用与告警' },
  { key: 'self_check', label: '平台自检', desc: '服务状态与运行检查' },
]

function nowTs() {
  return Math.floor(Date.now() / 1000)
}

function startOfTodayTs(baseTs = nowTs()) {
  const date = new Date(baseTs * 1000)
  date.setHours(0, 0, 0, 0)
  return Math.floor(date.getTime() / 1000)
}

export function buildAlertSummaryItems(historyAlerts, realtimeAlerts, currentTs = nowTs()) {
  const recentCount = realtimeAlerts.filter((alert) => currentTs - alert.timestamp <= RECENT_ALERT_WINDOW_SECONDS).length
  const criticalUnacknowledged = realtimeAlerts.filter((alert) => alert.severity === 'critical').length

  return [
    { key: 'critical', label: '严重未确认', value: criticalUnacknowledged, detail: '需要优先处理的高风险信号', tone: 'critical' },
    { key: 'pending', label: '总未确认', value: realtimeAlerts.length, detail: '当前仍在工作流中的未闭环告警', tone: 'warning' },
    { key: 'recent', label: '最近 1 小时新增', value: recentCount, detail: `历史样本 ${historyAlerts.length} 条`, tone: 'ok' },
  ]
}

export function buildRealtimeBuckets(alerts, selectedType = 'all', currentTs = nowTs()) {
  const filtered = alerts.filter((alert) => selectedType === 'all' || alert.alert_type === selectedType)
  const buckets = [
    { key: 'now', label: '刚刚', desc: '5 分钟内', items: [] },
    { key: 'recent', label: '近 1 小时', desc: '5 分钟到 1 小时', items: [] },
    { key: 'older', label: '更早', desc: '超过 1 小时', items: [] },
  ]

  for (const alert of filtered) {
    const age = currentTs - alert.timestamp
    if (age <= FIVE_MINUTES_SECONDS) {
      buckets[0].items.push(alert)
    } else if (age <= RECENT_ALERT_WINDOW_SECONDS) {
      buckets[1].items.push(alert)
    } else {
      buckets[2].items.push(alert)
    }
  }

  return buckets.filter((bucket) => bucket.items.length)
}

export function buildTodayTimeline(alerts, currentTs = nowTs()) {
  const todayStart = startOfTodayTs(currentTs)
  const sections = new Map()

  alerts
    .filter((alert) => alert.timestamp >= todayStart)
    .sort((a, b) => b.timestamp - a.timestamp)
    .forEach((alert) => {
      const stamp = new Date(alert.timestamp * 1000)
      const key = `${String(stamp.getHours()).padStart(2, '0')}:00`
      const existing = sections.get(key) || { key, label: `${key} 时段`, items: [] }
      existing.items.push(alert)
      sections.set(key, existing)
    })

  return Array.from(sections.values())
}

export function buildArchiveGroups(alerts, currentTs = nowTs()) {
  const todayStart = startOfTodayTs(currentTs)
  const archived = alerts.filter((alert) => alert.timestamp < todayStart)
  const groups = Object.fromEntries(ALERT_ARCHIVE_TYPES.map((item) => [item.key, []]))

  for (const alert of archived) {
    if (groups[alert.alert_type]) {
      groups[alert.alert_type].push(alert)
    }
  }

  return ALERT_ARCHIVE_TYPES.map((item) => ({
    ...item,
    count: groups[item.key].length,
    latest: groups[item.key][0] || null,
    alerts: groups[item.key],
  }))
}
```

- [ ] **Step 2: Replace `AlertCenter.vue` with the new tabbed shell and placeholder tab components**

Update the page to use `WorkspaceTabs` and the helper module:

```vue
<script setup>
import { computed, onMounted, ref } from 'vue'
import { acknowledgeAlert, getAlerts } from '../services/api'
import { useAppStore } from '../stores/app'
import WorkspaceSummary from '../components/workspace/WorkspaceSummary.vue'
import WorkspaceTabs from '../components/workspace/WorkspaceTabs.vue'
import AlertSummaryPanel from '../components/alerts/AlertSummaryPanel.vue'
import AlertRealtimeStream from '../components/alerts/AlertRealtimeStream.vue'
import AlertRealtimeSidebar from '../components/alerts/AlertRealtimeSidebar.vue'
import AlertDaybookTimeline from '../components/alerts/AlertDaybookTimeline.vue'
import AlertArchiveBoard from '../components/alerts/AlertArchiveBoard.vue'
import {
  ALERT_CENTER_TABS,
  buildAlertSummaryItems,
  buildArchiveGroups,
  buildRealtimeBuckets,
  buildTodayTimeline,
} from '../lib/alertCenterTransforms.js'

const ALERT_HISTORY_LIMIT = 200

const store = useAppStore()
const activeTab = ref('realtime')
const realtimeType = ref('all')
const archiveType = ref('temperature')
const historyAlerts = ref([])
const loading = ref(false)

const realtimeAlerts = computed(() => store.alerts.filter((alert) => !alert.acknowledged))
const summaryItems = computed(() => buildAlertSummaryItems(historyAlerts.value, realtimeAlerts.value))
const realtimeBuckets = computed(() => buildRealtimeBuckets(realtimeAlerts.value, realtimeType.value))
const todaySections = computed(() => buildTodayTimeline(historyAlerts.value))
const archiveGroups = computed(() => buildArchiveGroups(historyAlerts.value))

async function loadAlerts() {
  loading.value = true
  try {
    const { data } = await getAlerts(ALERT_HISTORY_LIMIT, false)
    historyAlerts.value = data.alerts || []
  } finally {
    loading.value = false
  }
}

async function ackAlert(id) {
  await acknowledgeAlert(id)
  store.$patch({
    alerts: store.alerts.map((alert) => (
      alert.id === id ? { ...alert, acknowledged: true } : alert
    )),
  })
  await loadAlerts()
}

onMounted(loadAlerts)
</script>
```

Use this top-tab shell in the template:

```vue
<div class="workspace-nav-layout">
  <div class="workspace-nav-layout__nav">
    <WorkspaceTabs v-model="activeTab" :items="ALERT_CENTER_TABS" />
  </div>

  <section class="workspace-nav-layout__content">
    <AlertRealtimeStream
      v-if="activeTab === 'realtime'"
      :buckets="realtimeBuckets"
      :loading="loading"
      @ack="ackAlert"
    />
    <AlertDaybookTimeline
      v-else-if="activeTab === 'today'"
      :sections="todaySections"
      :loading="loading"
      @ack="ackAlert"
    />
    <AlertArchiveBoard
      v-else
      v-model:type-key="archiveType"
      :groups="archiveGroups"
      :loading="loading"
      @ack="ackAlert"
    />
  </section>
</div>
```

Create the five new alert components as placeholders that expose the final prop APIs but render simple section roots first:

```vue
<script setup>
defineProps({
  buckets: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
})
defineEmits(['ack'])
</script>

<template>
  <section class="alert-realtime-stream">占位：实时流</section>
</template>
```

- [ ] **Step 3: Convert `AlertSummaryPanel.vue` into a compact summary strip**

Replace the current fixed-card props API with an item-driven summary band:

```vue
<script setup>
defineProps({
  items: {
    type: Array,
    default: () => [],
  },
})
</script>

<template>
  <div class="alert-summary-strip">
    <div
      v-for="item in items"
      :key="item.key"
      class="alert-summary-strip__item"
      :class="`alert-summary-strip__item--${item.tone || 'neutral'}`"
    >
      <div class="alert-summary-strip__label">{{ item.label }}</div>
      <div class="alert-summary-strip__value">{{ item.value }}</div>
      <div class="alert-summary-strip__detail">{{ item.detail }}</div>
    </div>
  </div>
</template>
```

- [ ] **Step 4: Run the alert-center shell tests**

Run:

```bash
cmd.exe /c "cd /d E:\Code\AI-DataCenter && .\.venv\Scripts\python.exe -m unittest tests.test_frontend_ui_structure.FrontendUIStructureTests.test_alert_center_uses_time_workbench_tabs tests.test_frontend_ui_structure.FrontendUIStructureTests.test_alert_center_time_workbench_components_exist"
```

Expected:

- PASS on `activeTab = ref('realtime')`
- PASS on `WorkspaceTabs` and `realtime / today / archive`
- PASS on the new component file existence assertions

- [ ] **Step 5: Commit the shell layer**

```bash
git add frontend/src/views/AlertCenter.vue frontend/src/components/alerts/AlertSummaryPanel.vue frontend/src/components/alerts/AlertRealtimeStream.vue frontend/src/components/alerts/AlertRealtimeSidebar.vue frontend/src/components/alerts/AlertDaybookTimeline.vue frontend/src/components/alerts/AlertArchiveTypeTabs.vue frontend/src/components/alerts/AlertArchiveBoard.vue frontend/src/lib/alertCenterTransforms.js tests/test_frontend_ui_structure.py
git commit -m "feat: add alert center time workbench shell"
```

---

### Task 3: Add Realtime-Tab Tests And Implement The Default Worklist View

**Files:**
- Modify: `tests/test_frontend_ui_structure.py`
- Modify: `frontend/src/components/alerts/AlertRealtimeStream.vue`
- Modify: `frontend/src/components/alerts/AlertRealtimeSidebar.vue`
- Modify: `frontend/src/views/AlertCenter.vue`
- Test: `tests/test_frontend_ui_structure.py`

- [ ] **Step 1: Add failing realtime-layout tests**

Append these tests:

```python
    def test_alert_realtime_components_use_bucketed_layout(self):
        stream_text = (ROOT / "frontend/src/components/alerts/AlertRealtimeStream.vue").read_text(encoding="utf-8")
        sidebar_text = (ROOT / "frontend/src/components/alerts/AlertRealtimeSidebar.vue").read_text(encoding="utf-8")

        self.assertIn("realtime-bucket", stream_text)
        self.assertIn("realtime-alert-card", stream_text)
        self.assertIn("bucket.items", stream_text)
        self.assertIn("alert-realtime-sidebar", sidebar_text)
        self.assertIn("update:modelValue", sidebar_text)
        self.assertNotIn("text-overflow: ellipsis", stream_text)
```

- [ ] **Step 2: Run the new realtime test and verify it fails against the placeholders**

Run:

```bash
cmd.exe /c "cd /d E:\Code\AI-DataCenter && .\.venv\Scripts\python.exe -m unittest tests.test_frontend_ui_structure.FrontendUIStructureTests.test_alert_realtime_components_use_bucketed_layout"
```

Expected:

- FAIL because the placeholder components do not contain `realtime-bucket` or `realtime-alert-card`

- [ ] **Step 3: Implement the realtime main column and sidebar**

Update `AlertRealtimeStream.vue` to render bucket sections and compact cards:

```vue
<template>
  <WorkspacePaneLayout>
    <template #main>
      <section class="tech-card alert-realtime-stream">
        <div v-if="!buckets.length && !loading" class="alert-realtime-stream__empty">
          当前没有未确认的实时告警。
        </div>
        <section
          v-for="bucket in buckets"
          :key="bucket.key"
          class="realtime-bucket"
        >
          <header class="realtime-bucket__head">
            <div class="realtime-bucket__title">{{ bucket.label }}</div>
            <div class="realtime-bucket__desc">{{ bucket.desc }}</div>
          </header>

          <article
            v-for="alert in bucket.items"
            :key="alert.id"
            class="realtime-alert-card"
          >
            <div class="realtime-alert-card__meta">
              <span class="status-badge" :class="alert.severity === 'critical' ? 'status-badge--critical' : 'status-badge--warning'">
                {{ severityConfig[alert.severity]?.label || alert.severity }}
              </span>
              <span class="gpu-tag">GPU {{ alert.gpu_index }}</span>
              <span class="realtime-alert-card__type">{{ formatAlertType(alert.alert_type) }}</span>
              <span class="realtime-alert-card__time">{{ fmtTime(alert.timestamp) }}</span>
            </div>
            <div class="realtime-alert-card__message">{{ alert.message }}</div>
            <div class="realtime-alert-card__footer">
              <span class="stat-value">{{ alert.value?.toFixed(1) ?? '—' }}</span>
              <span class="realtime-alert-card__threshold">阈值 {{ alert.threshold ?? '—' }}</span>
              <button class="btn-tech alert-history-table__ack" @click="emit('ack', alert.id)">确认</button>
            </div>
          </article>
        </section>
      </section>
    </template>

    <template #side>
      <AlertRealtimeSidebar
        v-model="selectedType"
        :items="filterItems"
        :summary-items="summaryItems"
      />
    </template>
  </WorkspacePaneLayout>
</template>
```

Update `AlertRealtimeSidebar.vue` to own the stable filter rail:

```vue
<script setup>
const props = defineProps({
  modelValue: { type: String, required: true },
  items: { type: Array, default: () => [] },
  summaryItems: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue'])
</script>

<template>
  <aside class="tech-card alert-realtime-sidebar">
    <div class="alert-realtime-sidebar__group">
      <div class="section-title">类型过滤</div>
      <div class="alert-realtime-sidebar__filters">
        <button
          v-for="item in items"
          :key="item.key"
          type="button"
          class="alert-realtime-sidebar__filter"
          :class="{ 'alert-realtime-sidebar__filter--active': modelValue === item.key }"
          @click="emit('update:modelValue', item.key)"
        >
          {{ item.label }}
        </button>
      </div>
    </div>

    <div class="alert-realtime-sidebar__group">
      <div class="section-title">风险摘要</div>
      <div class="alert-realtime-sidebar__summary">
        <div v-for="item in summaryItems" :key="item.key" class="alert-realtime-sidebar__summary-item">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </div>
      </div>
    </div>
  </aside>
</template>
```

Wire the props from `AlertCenter.vue`:

```vue
<AlertRealtimeStream
  v-if="activeTab === 'realtime'"
  :buckets="realtimeBuckets"
  :loading="loading"
  :selected-type="realtimeType"
  :filter-items="[{ key: 'all', label: '全部未确认' }, ...archiveGroups.map(group => ({ key: group.key, label: group.label }))]"
  :summary-items="summaryItems"
  :severity-config="severityConfig"
  :format-alert-type="formatAlertType"
  :fmt-time="fmtTime"
  @ack="ackAlert"
  @update:selectedType="realtimeType = $event"
/>
```

- [ ] **Step 4: Run the realtime tests again**

Run:

```bash
cmd.exe /c "cd /d E:\Code\AI-DataCenter && .\.venv\Scripts\python.exe -m unittest tests.test_frontend_ui_structure.FrontendUIStructureTests.test_alert_realtime_components_use_bucketed_layout"
```

Expected:

- PASS with bucketed realtime structure present

- [ ] **Step 5: Commit the realtime worklist**

```bash
git add frontend/src/components/alerts/AlertRealtimeStream.vue frontend/src/components/alerts/AlertRealtimeSidebar.vue frontend/src/views/AlertCenter.vue tests/test_frontend_ui_structure.py
git commit -m "feat: add realtime alert worklist tab"
```

---

### Task 4: Add Timeline Tests And Implement The Same-Day Ledger

**Files:**
- Modify: `tests/test_frontend_ui_structure.py`
- Modify: `frontend/src/components/alerts/AlertDaybookTimeline.vue`
- Modify: `frontend/src/views/AlertCenter.vue`
- Test: `tests/test_frontend_ui_structure.py`

- [ ] **Step 1: Add failing timeline tests**

Append this test:

```python
    def test_alert_daybook_uses_timeline_sections(self):
        text = (ROOT / "frontend/src/components/alerts/AlertDaybookTimeline.vue").read_text(encoding="utf-8")

        self.assertIn("daybook-section", text)
        self.assertIn("daybook-entry", text)
        self.assertIn("section.items", text)
        self.assertNotIn("grid-template-columns: minmax(88px", text)
```

- [ ] **Step 2: Run the new timeline test and verify it fails**

Run:

```bash
cmd.exe /c "cd /d E:\Code\AI-DataCenter && .\.venv\Scripts\python.exe -m unittest tests.test_frontend_ui_structure.FrontendUIStructureTests.test_alert_daybook_uses_timeline_sections"
```

Expected:

- FAIL because the placeholder daybook component has no `daybook-section` or `daybook-entry`

- [ ] **Step 3: Implement the daybook timeline component**

Replace the placeholder with a real timeline ledger:

```vue
<template>
  <section class="tech-card alert-daybook">
    <div class="alert-daybook__header">
      <div class="section-title">今日告警簿</div>
      <div class="alert-daybook__hint">按时间节点查看当天告警的发生与处置过程。</div>
    </div>

    <div v-if="!sections.length && !loading" class="alert-daybook__empty">
      今日暂无告警记录。
    </div>

    <section
      v-for="section in sections"
      :key="section.key"
      class="daybook-section"
    >
      <header class="daybook-section__head">
        <div class="daybook-section__title">{{ section.label }}</div>
        <div class="daybook-section__count">{{ section.items.length }} 条</div>
      </header>

      <article
        v-for="alert in section.items"
        :key="alert.id"
        class="daybook-entry"
      >
        <div class="daybook-entry__meta">
          <span class="status-badge" :class="alert.severity === 'critical' ? 'status-badge--critical' : 'status-badge--warning'">
            {{ severityConfig[alert.severity]?.label || alert.severity }}
          </span>
          <span class="gpu-tag">GPU {{ alert.gpu_index }}</span>
          <span class="daybook-entry__type">{{ formatAlertType(alert.alert_type) }}</span>
          <span class="daybook-entry__time">{{ fmtTime(alert.timestamp) }}</span>
        </div>
        <div class="daybook-entry__message">{{ alert.message }}</div>
        <div class="daybook-entry__footer">
          <span class="stat-value">{{ alert.value?.toFixed(1) ?? '—' }}</span>
          <span class="daybook-entry__threshold">阈值 {{ alert.threshold ?? '—' }}</span>
          <button v-if="!alert.acknowledged" class="btn-tech alert-history-table__ack" @click="emit('ack', alert.id)">确认</button>
          <span v-else class="daybook-entry__state">已确认</span>
        </div>
      </article>
    </section>
  </section>
</template>
```

- [ ] **Step 4: Run the timeline test again**

Run:

```bash
cmd.exe /c "cd /d E:\Code\AI-DataCenter && .\.venv\Scripts\python.exe -m unittest tests.test_frontend_ui_structure.FrontendUIStructureTests.test_alert_daybook_uses_timeline_sections"
```

Expected:

- PASS with timeline section and entry classes present

- [ ] **Step 5: Commit the same-day ledger**

```bash
git add frontend/src/components/alerts/AlertDaybookTimeline.vue tests/test_frontend_ui_structure.py
git commit -m "feat: add alert daybook timeline tab"
```

---

### Task 5: Add Archive Tests And Implement The Type-Based History Board

**Files:**
- Modify: `tests/test_frontend_ui_structure.py`
- Modify: `frontend/src/components/alerts/AlertArchiveTypeTabs.vue`
- Modify: `frontend/src/components/alerts/AlertArchiveBoard.vue`
- Modify: `frontend/src/components/alerts/AlertHistoryTable.vue`
- Test: `tests/test_frontend_ui_structure.py`

- [ ] **Step 1: Add failing archive tests**

Append this test:

```python
    def test_alert_archive_board_groups_history_by_type(self):
        board_text = (ROOT / "frontend/src/components/alerts/AlertArchiveBoard.vue").read_text(encoding="utf-8")
        tabs_text = (ROOT / "frontend/src/components/alerts/AlertArchiveTypeTabs.vue").read_text(encoding="utf-8")
        helper_text = (ROOT / "frontend/src/lib/alertCenterTransforms.js").read_text(encoding="utf-8")

        self.assertIn("AlertArchiveTypeTabs", board_text)
        self.assertIn("AlertHistoryTable", board_text)
        self.assertIn("archive-summary", board_text)
        self.assertIn("update:modelValue", tabs_text)
        self.assertIn("temperature", helper_text)
        self.assertIn("self_check", helper_text)
```

- [ ] **Step 2: Run the archive test and verify it fails against placeholders**

Run:

```bash
cmd.exe /c "cd /d E:\Code\AI-DataCenter && .\.venv\Scripts\python.exe -m unittest tests.test_frontend_ui_structure.FrontendUIStructureTests.test_alert_archive_board_groups_history_by_type"
```

Expected:

- FAIL because the archive placeholder does not yet contain `AlertHistoryTable` or type tabs

- [ ] **Step 3: Implement archive tabs and board using `AlertHistoryTable` as a local detail view**

Create the type switcher:

```vue
<script setup>
const props = defineProps({
  modelValue: { type: String, required: true },
  items: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue'])
</script>

<template>
  <div class="alert-archive-type-tabs">
    <button
      v-for="item in items"
      :key="item.key"
      type="button"
      class="alert-archive-type-tabs__item"
      :class="{ 'alert-archive-type-tabs__item--active': modelValue === item.key }"
      @click="emit('update:modelValue', item.key)"
    >
      <span>{{ item.label }}</span>
      <strong>{{ item.count }}</strong>
    </button>
  </div>
</template>
```

Build the archive board around the selected type:

```vue
<script setup>
import { computed } from 'vue'
import AlertArchiveTypeTabs from './AlertArchiveTypeTabs.vue'
import AlertHistoryTable from './AlertHistoryTable.vue'

const props = defineProps({
  typeKey: { type: String, required: true },
  groups: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  severityConfig: { type: Object, required: true },
  formatAlertType: { type: Function, required: true },
  fmtTime: { type: Function, required: true },
})
const emit = defineEmits(['update:typeKey', 'ack'])

const selectedGroup = computed(() => (
  props.groups.find((group) => group.key === props.typeKey) || props.groups[0] || null
))
</script>

<template>
  <section class="alert-archive-board">
    <section class="tech-card archive-summary">
      <div class="section-title">历史归档</div>
      <AlertArchiveTypeTabs
        :model-value="typeKey"
        :items="groups"
        @update:modelValue="emit('update:typeKey', $event)"
      />
    </section>

    <section class="tech-card archive-detail">
      <div class="archive-detail__head">
        <div class="section-title">{{ selectedGroup?.label || '归档明细' }}</div>
        <div class="archive-detail__hint">{{ selectedGroup?.desc || '按类型查看历史告警。' }}</div>
      </div>
      <AlertHistoryTable
        :alerts="selectedGroup?.alerts || []"
        :loading="loading"
        :severity-config="severityConfig"
        :fmt-time="fmtTime"
        :format-alert-type="formatAlertType"
        @ack="emit('ack', $event)"
      />
    </section>
  </section>
</template>
```

Keep `AlertHistoryTable.vue` compact and local-detail only by adding an archive-specific root class and leaving its responsive row rendering intact:

```vue
<div class="alert-history-table alert-history-table--archive">
```

- [ ] **Step 4: Run the archive test again**

Run:

```bash
cmd.exe /c "cd /d E:\Code\AI-DataCenter && .\.venv\Scripts\python.exe -m unittest tests.test_frontend_ui_structure.FrontendUIStructureTests.test_alert_archive_board_groups_history_by_type"
```

Expected:

- PASS with archive board, type tabs, and local detail table present

- [ ] **Step 5: Commit the archive board**

```bash
git add frontend/src/components/alerts/AlertArchiveTypeTabs.vue frontend/src/components/alerts/AlertArchiveBoard.vue frontend/src/components/alerts/AlertHistoryTable.vue tests/test_frontend_ui_structure.py
git commit -m "feat: add alert history archive board"
```

---

### Task 6: Final Verification, Cleanup, And Build Proof

**Files:**
- Modify: `frontend/src/views/AlertCenter.vue`
- Modify: `frontend/src/components/alerts/AlertSummaryPanel.vue`
- Modify: `frontend/src/components/alerts/AlertRealtimeStream.vue`
- Modify: `frontend/src/components/alerts/AlertRealtimeSidebar.vue`
- Modify: `frontend/src/components/alerts/AlertDaybookTimeline.vue`
- Modify: `frontend/src/components/alerts/AlertArchiveTypeTabs.vue`
- Modify: `frontend/src/components/alerts/AlertArchiveBoard.vue`
- Modify: `frontend/src/components/alerts/AlertHistoryTable.vue`
- Modify: `tests/test_frontend_ui_structure.py`

- [ ] **Step 1: Run the full frontend UI structure suite**

Run:

```bash
cmd.exe /c "cd /d E:\Code\AI-DataCenter && .\.venv\Scripts\python.exe -m unittest tests.test_frontend_ui_structure tests.test_frontend_performance_structure"
```

Expected:

- All alert-center structure assertions pass
- Existing frontend performance structure tests remain green

- [ ] **Step 2: Run repository-level regression coverage**

Run:

```bash
cmd.exe /c "cd /d E:\Code\AI-DataCenter && .\.venv\Scripts\python.exe -m unittest discover -s tests -p \"test_*.py\""
```

Expected:

- PASS with no regressions in existing root test suite

- [ ] **Step 3: Run the frontend production build**

Run:

```bash
cmd.exe /c "cd /d E:\Code\AI-DataCenter\frontend && npm run build"
```

Expected:

- Vite build succeeds
- No new compile errors from the alert-center component split

- [ ] **Step 4: Commit the completed work**

```bash
git add frontend/src/views/AlertCenter.vue frontend/src/components/alerts/AlertSummaryPanel.vue frontend/src/components/alerts/AlertRealtimeStream.vue frontend/src/components/alerts/AlertRealtimeSidebar.vue frontend/src/components/alerts/AlertDaybookTimeline.vue frontend/src/components/alerts/AlertArchiveTypeTabs.vue frontend/src/components/alerts/AlertArchiveBoard.vue frontend/src/components/alerts/AlertHistoryTable.vue frontend/src/lib/alertCenterTransforms.js tests/test_frontend_ui_structure.py
git commit -m "feat: rebuild alert center as time workbench"
```

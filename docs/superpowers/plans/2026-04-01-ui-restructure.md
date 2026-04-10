# Frontend UI Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize the main frontend pages into layered, tabbed, stable layouts without changing routes or backend behavior.

**Architecture:** Introduce shared workspace-shell components for summary, tabs, and stable two-pane layouts, then refactor the major pages in batches. Keep the current ink-and-paper visual language, but move each page to a "summary + task tabs + stable content slots" structure and split oversized views into page-specific components.

**Tech Stack:** Vue 3, Vite, Tailwind utility classes, scoped CSS, Python `unittest` structure checks, `npm run build`

---

### Task 1: Add failing structure tests and shared workspace primitives

**Files:**
- Create: `tests/test_frontend_ui_structure.py`
- Create: `frontend/src/components/workspace/WorkspaceTabs.vue`
- Create: `frontend/src/components/workspace/WorkspaceSummary.vue`
- Create: `frontend/src/components/workspace/WorkspacePaneLayout.vue`
- Modify: `frontend/src/style.css`

- [ ] **Step 1: Write the failing test**

Create `tests/test_frontend_ui_structure.py` with structural checks for the new shell primitives and tabbed page organization:

```python
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class FrontendUIStructureTests(unittest.TestCase):
    def test_workspace_shell_components_exist(self):
        for rel in [
            "frontend/src/components/workspace/WorkspaceTabs.vue",
            "frontend/src/components/workspace/WorkspaceSummary.vue",
            "frontend/src/components/workspace/WorkspacePaneLayout.vue",
        ]:
            self.assertTrue((ROOT / rel).exists(), rel)

    def test_major_views_use_tab_state(self):
        for rel in [
            "frontend/src/views/Dashboard.vue",
            "frontend/src/views/TaskManager.vue",
            "frontend/src/views/Scheduler.vue",
            "frontend/src/views/EnergyOptimization.vue",
            "frontend/src/views/AIAssistant.vue",
        ]:
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("activeTab", text, rel)
            self.assertIn("WorkspaceTabs", text, rel)

    def test_vite_build_still_available(self):
        package_json = (ROOT / "frontend/package.json").read_text(encoding="utf-8")
        self.assertIn('"build": "vite build"', package_json)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_frontend_ui_structure -v`
Expected: FAIL because the shared workspace components do not exist and the major views do not use tab state yet.

- [ ] **Step 3: Create the shared shell components**

Add minimal shared Vue primitives:

```vue
<!-- frontend/src/components/workspace/WorkspaceTabs.vue -->
<script setup>
defineProps({
  items: { type: Array, required: true },
  modelValue: { type: String, required: true },
})
const emit = defineEmits(['update:modelValue'])
</script>

<template>
  <div class="workspace-tabs">
    <button
      v-for="item in items"
      :key="item.key"
      type="button"
      class="workspace-tab"
      :class="{ 'workspace-tab--active': modelValue === item.key }"
      @click="emit('update:modelValue', item.key)"
    >
      <span class="workspace-tab__label">{{ item.label }}</span>
      <span v-if="item.desc" class="workspace-tab__desc">{{ item.desc }}</span>
    </button>
  </div>
</template>
```

```vue
<!-- frontend/src/components/workspace/WorkspaceSummary.vue -->
<script setup>
defineProps({
  eyebrow: { type: String, default: '' },
  title: { type: String, required: true },
  description: { type: String, default: '' },
})
</script>

<template>
  <section class="workspace-summary tech-card">
    <div class="workspace-summary__eyebrow">{{ eyebrow }}</div>
    <h2 class="workspace-summary__title">{{ title }}</h2>
    <p class="workspace-summary__desc">{{ description }}</p>
    <slot />
  </section>
</template>
```

```vue
<!-- frontend/src/components/workspace/WorkspacePaneLayout.vue -->
<template>
  <div class="workspace-pane-layout">
    <div class="workspace-pane-layout__main">
      <slot name="main" />
    </div>
    <aside class="workspace-pane-layout__side">
      <slot name="side" />
    </aside>
  </div>
</template>
```

- [ ] **Step 4: Add the shared CSS**

Append stable shell layout styles to `frontend/src/style.css`:

```css
.workspace-tabs {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.workspace-tab {
  min-width: 164px;
  padding: 14px 16px;
  border-radius: 18px;
  border: 1px solid var(--border-color);
  background: rgba(255, 252, 247, 0.72);
  text-align: left;
}

.workspace-pane-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(320px, 0.9fr);
  gap: 18px;
  align-items: start;
}

.workspace-pane-layout__main,
.workspace-pane-layout__side {
  display: grid;
  gap: 18px;
  align-content: start;
}
```

- [ ] **Step 5: Re-run the targeted test**

Run: `python3 -m unittest tests.test_frontend_ui_structure -v`
Expected: FAIL because the page files are not refactored to use the new shell yet.

### Task 2: Refactor Dashboard and AlertCenter into layered workspaces

**Files:**
- Create: `frontend/src/components/dashboard/DashboardOverviewTab.vue`
- Create: `frontend/src/components/dashboard/DashboardAccessTab.vue`
- Create: `frontend/src/components/dashboard/DashboardLiveTab.vue`
- Create: `frontend/src/components/dashboard/DashboardStatusRail.vue`
- Create: `frontend/src/components/alerts/AlertSummaryPanel.vue`
- Modify: `frontend/src/views/Dashboard.vue`
- Modify: `frontend/src/views/AlertCenter.vue`

- [ ] **Step 1: Add Dashboard tab state**

Introduce task-oriented tabs:

```js
const activeTab = ref('overview')
const dashboardTabs = [
  { key: 'overview', label: '概览', desc: '判断与入口' },
  { key: 'access', label: '接入与自检', desc: '接入、自检、桌面服务' },
  { key: 'live', label: '实时态势', desc: 'GPU、图表、告警' },
]
```

- [ ] **Step 2: Replace the long-flow body with the workspace shell**

Restructure `Dashboard.vue` around the shared primitives:

```vue
<WorkspaceSummary
  eyebrow="智算中心优化代码生成系统"
  title="先看判断，再进入具体治理动作"
  :description="governanceTip"
>
  <DashboardStatusRail />
</WorkspaceSummary>

<WorkspaceTabs v-model="activeTab" :items="dashboardTabs" />

<DashboardOverviewTab v-if="activeTab === 'overview'" />
<DashboardAccessTab v-else-if="activeTab === 'access'" />
<DashboardLiveTab v-else />
```

- [ ] **Step 3: Split Dashboard content by task**

Move current sections into page-specific components:
- overview: hero conclusion, quick routes, governance summary
- access: connection center, self-check, desktop ops, remote assist
- live: GPU grid, trend charts, utilization chart, recent alerts

- [ ] **Step 4: Add AlertCenter summary and stable table slot**

Refactor `AlertCenter.vue` so the header becomes a compact summary layer and the table sits in a dedicated stable content panel:

```vue
<WorkspaceSummary
  eyebrow="风险台"
  title="先看风险数量，再处理告警明细"
  description="把提示、筛选和主表拆开，避免表格与说明互相挤压。"
>
  <AlertSummaryPanel />
</WorkspaceSummary>
```

- [ ] **Step 5: Run build-focused verification**

Run: `cd frontend && npm run build`
Expected: PASS

### Task 3: Refactor TaskManager and Scheduler into action-first tabs

**Files:**
- Create: `frontend/src/components/tasks/TaskActionsTab.vue`
- Create: `frontend/src/components/tasks/TaskFairnessTab.vue`
- Create: `frontend/src/components/tasks/TaskRulesTab.vue`
- Create: `frontend/src/components/scheduler/SchedulerControlTab.vue`
- Create: `frontend/src/components/scheduler/SchedulerResultsTab.vue`
- Create: `frontend/src/components/scheduler/SchedulerAuditTab.vue`
- Modify: `frontend/src/views/TaskManager.vue`
- Modify: `frontend/src/views/Scheduler.vue`

- [ ] **Step 1: Add TaskManager tabs and isolate the table**

Use:

```js
const activeTab = ref('actions')
const taskTabs = [
  { key: 'actions', label: '待处置任务', desc: '筛选与执行' },
  { key: 'fairness', label: '公平治理', desc: '占用结构与让路建议' },
  { key: 'rules', label: '规则配置', desc: '用户治理规则' },
]
```

Move the process table into `TaskActionsTab.vue`, and keep it inside a dedicated scroll container instead of the root page flow.

- [ ] **Step 2: Separate TaskManager fairness and rules**

Place fairness cards and yield candidates in `TaskFairnessTab.vue`; move user rule editors into `TaskRulesTab.vue` so editing rules no longer changes the table layout.

- [ ] **Step 3: Add Scheduler tabs**

Use:

```js
const activeTab = ref('control')
const schedulerTabs = [
  { key: 'control', label: '治理控制', desc: '预算与动作' },
  { key: 'results', label: '执行结果', desc: '结果、评估、对比' },
  { key: 'audit', label: '审计与报告', desc: '日志与报告' },
]
```

- [ ] **Step 4: Split Scheduler by intent**

Map the current content into:
- control: power budget, carbon budget, auto schedule, manual power control
- results: schedule result, strategy compare, evaluation
- audit: AI report and audit log list

Use `WorkspacePaneLayout` so controls and explanations occupy stable columns.

- [ ] **Step 5: Run the targeted structure test**

Run: `python3 -m unittest tests.test_frontend_ui_structure -v`
Expected: PASS for Dashboard, TaskManager, and Scheduler once they import `WorkspaceTabs` and define `activeTab`.

### Task 4: Refactor Energy, Monitor, AI, and polish remaining major pages

**Files:**
- Create: `frontend/src/components/energy/EnergyOverviewTab.vue`
- Create: `frontend/src/components/energy/EnergyForecastTab.vue`
- Create: `frontend/src/components/energy/EnergyInsightTab.vue`
- Create: `frontend/src/components/ai/AIControlTab.vue`
- Create: `frontend/src/components/ai/AIChatTab.vue`
- Create: `frontend/src/components/ai/AIConfigTab.vue`
- Modify: `frontend/src/views/EnergyOptimization.vue`
- Modify: `frontend/src/views/MonitorCenter.vue`
- Modify: `frontend/src/views/AIAssistant.vue`

- [ ] **Step 1: Add EnergyOptimization task tabs**

Use:

```js
const activeTab = ref('overview')
const energyTabs = [
  { key: 'overview', label: '总览', desc: '当前判断与关键指标' },
  { key: 'forecast', label: '预测与对比', desc: '趋势、预测、历史对比' },
  { key: 'insight', label: 'AI 洞察', desc: '异常与建议' },
]
```

- [ ] **Step 2: Keep MonitorCenter tabs but stabilize each tab body**

Do not change the existing tab taxonomy. Instead, convert each tab body to fixed slots:

```vue
<WorkspacePaneLayout>
  <template #main>
    <!-- charts or dense primary content -->
  </template>
  <template #side>
    <!-- stats, legends, detail cards -->
  </template>
</WorkspacePaneLayout>
```

- [ ] **Step 3: Split AIAssistant into control, chat, config**

Use:

```js
const activeTab = ref('control')
const aiTabs = [
  { key: 'control', label: '执行控制', desc: '审核与执行动作' },
  { key: 'chat', label: '对话解释', desc: '问答与解释' },
  { key: 'config', label: '模型配置', desc: 'LLM 接入' },
]
```

Move the plan/execute console into `AIControlTab.vue`, the chat transcript into `AIChatTab.vue`, and the LLM form into `AIConfigTab.vue`.

- [ ] **Step 4: Run frontend build verification**

Run: `cd frontend && npm run build`
Expected: PASS

### Task 5: Responsive and stability polish

**Files:**
- Modify: `frontend/src/style.css`
- Modify: page-local scoped styles in the refactored view and component files

- [ ] **Step 1: Add responsive fallback for stable panes**

Add CSS to collapse the two-pane layout without coupling unrelated modules:

```css
@media (max-width: 1180px) {
  .workspace-pane-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .workspace-tabs {
    overflow-x: auto;
    flex-wrap: nowrap;
  }
}
```

- [ ] **Step 2: Move long tables and lists into independent scroll containers**

Apply explicit wrappers such as:

```css
.panel-scroll {
  overflow: auto;
  max-height: 64vh;
}
```

Use these wrappers for task tables, alert tables, replay tables, and any other long data surfaces.

- [ ] **Step 3: Run repository verification**

Run: `python3 -m unittest discover -s tests -p 'test_*.py'`
Expected: PASS

- [ ] **Step 4: Run final frontend build**

Run: `cd frontend && npm run build`
Expected: PASS

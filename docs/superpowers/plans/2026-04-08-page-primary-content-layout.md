# Page Primary Content Layout Implementation Plan
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
**Goal:** 让 `总览 / 治理 / 观察 / 告警 / 能耗 / 智能` 六个一级页都遵守“主体直出”，首屏先进入 tabs 和工作区，不再被低信息密度摘要层压住。
**Architecture:** 维持现有路由与数据接口不变，继续复用 `ConsoleShell` 已完成的壳层头部裁剪，只收口各页面自己的页面级摘要。轻量页面直接删冗余 strip，超大页面把页头抽成独立组件，避免继续把 `MonitorCenter.vue`、`EnergyOptimization.vue`、`AIAssistant.vue` 堆大。
**Tech Stack:** Vue 3 SFC, Vue Router, Pinia, Vite, Python `unittest`, Node `node:test`
---
## File Map
- Modify: `frontend/src/views/Dashboard.vue` - 保留唯一 `dashboard-summary`，移除顶部 `quick-grid`
- Modify: `frontend/src/components/dashboard/DashboardOverviewTab.vue` - 接管 `quickStats` 的局部展示
- Modify: `frontend/src/views/GovernanceLayout.vue` - 删除 `stats-grid workspace-summary-strip`，只保留一层摘要
- Create: `frontend/src/components/monitor/MonitorWorkspaceSummary.vue` - 承接观察页页头摘要
- Modify: `frontend/src/views/MonitorCenter.vue` - 删除 `monitor-summary-grid`
- Modify: `frontend/src/views/AlertCenter.vue` - 把 `AlertSummaryPanel` 下沉到 tab 内容区
- Create: `frontend/src/components/energy/EnergyWorkspaceHeader.vue` - 替换 `ink-header + source-strip`
- Modify: `frontend/src/views/EnergyOptimization.vue` - 引入紧凑页头并删除 `source-strip`
- Create: `frontend/src/components/ai/AIAssistantWorkspaceSummary.vue` - 抽出 AI 页头，压薄首屏
- Modify: `frontend/src/views/AIAssistant.vue` - 使用新页头组件
- Create: `tests/test_page_primary_content_layout_structure.py` - 新增一级页主体优先布局结构回归
### Task 1: Compact Dashboard And Governance Entry Headers
**Files:**
- Create: `tests/test_page_primary_content_layout_structure.py`
- Modify: `frontend/src/views/Dashboard.vue`
- Modify: `frontend/src/components/dashboard/DashboardOverviewTab.vue`
- Modify: `frontend/src/views/GovernanceLayout.vue`
- Test: `tests/test_frontend_ui_structure.py`, `tests/test_governance_workbench_structure.py`

- [ ] **Step 1: Write the failing structure tests**
```python
# tests/test_page_primary_content_layout_structure.py
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class PagePrimaryContentLayoutStructureTests(unittest.TestCase):
    def test_dashboard_keeps_single_summary_layer(self):
        dashboard_text = (ROOT / "frontend/src/views/Dashboard.vue").read_text(encoding="utf-8")
        overview_text = (ROOT / "frontend/src/components/dashboard/DashboardOverviewTab.vue").read_text(encoding="utf-8")

        self.assertIn("dashboard-summary", dashboard_text)
        self.assertNotIn("dashboard-summary__quick-grid", dashboard_text)
        self.assertIn("props.model.quickStats", overview_text)
        self.assertIn("overview-quick-strip", overview_text)

    def test_governance_tabs_follow_summary_without_stats_strip(self):
        text = (ROOT / "frontend/src/views/GovernanceLayout.vue").read_text(encoding="utf-8")

        self.assertIn("WorkspaceSummary", text)
        self.assertNotIn("stats-grid workspace-summary-strip", text)
        self.assertIn("activeSummaryBadge", text)
```
- [ ] **Step 2: Run the new structure test and confirm failure**
Run: `python3 -m unittest tests.test_page_primary_content_layout_structure -q`
Expected: FAIL because `dashboard-summary__quick-grid`, `overview-quick-strip`, and `activeSummaryBadge` do not match yet.

- [ ] **Step 3: Implement the compact summary flow**
```vue
<!-- frontend/src/components/dashboard/DashboardOverviewTab.vue -->
<section class="tech-card overview-card overview-card--wide">
  <div class="section-title">导入范围速记</div>
  <div class="overview-quick-strip">
    <article v-for="item in props.model.quickStats" :key="item.label" class="overview-quick-item">
      <span>{{ item.label }}</span>
      <strong>{{ item.value }}</strong>
      <small>{{ item.hint }}</small>
    </article>
  </div>
</section>
```
```vue
<!-- frontend/src/views/Dashboard.vue -->
<section class="tech-card dashboard-summary">
  <div class="dashboard-summary__top">...</div>
  <div class="dashboard-summary__caption">
    如需更改机器或 GPU 范围，直接使用左侧“切换服务器”返回导入层。
  </div>
</section>
```
```js
// frontend/src/views/GovernanceLayout.vue
const activeSummaryBadge = computed(() => headerModel.value.quickStats?.[0] || null)
```
```vue
<!-- frontend/src/views/GovernanceLayout.vue -->
<span v-if="activeSummaryBadge" class="status-badge">
  {{ activeSummaryBadge.label }} {{ activeSummaryBadge.value }}
</span>
```
- [ ] **Step 4: Re-run focused regressions**
Run: `python3 -m unittest tests.test_page_primary_content_layout_structure tests.test_frontend_ui_structure tests.test_governance_workbench_structure -q`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add tests/test_page_primary_content_layout_structure.py frontend/src/views/Dashboard.vue frontend/src/components/dashboard/DashboardOverviewTab.vue frontend/src/views/GovernanceLayout.vue
git commit -m "feat: compact dashboard and governance headers"
```
### Task 2: Extract The Monitor Header And Remove The Summary Grid
**Files:**
- Create: `frontend/src/components/monitor/MonitorWorkspaceSummary.vue`
- Modify: `frontend/src/views/MonitorCenter.vue`
- Modify: `tests/test_page_primary_content_layout_structure.py`
- Test: `tests/test_frontend_performance_structure.py`

- [ ] **Step 1: Add the failing monitor structure assertions**
```python
def test_monitor_center_uses_single_summary_component(self):
    component_text = (ROOT / "frontend/src/components/monitor/MonitorWorkspaceSummary.vue").read_text(encoding="utf-8")
    page_text = (ROOT / "frontend/src/views/MonitorCenter.vue").read_text(encoding="utf-8")

    self.assertIn("WorkspaceSummary", component_text)
    self.assertIn("MonitorWorkspaceSummary", page_text)
    self.assertNotIn("monitor-summary-grid", page_text)
```
- [ ] **Step 2: Run the monitor-focused test and confirm failure**
Run: `python3 -m unittest tests.test_page_primary_content_layout_structure -q`
Expected: FAIL because the extracted component is missing and `monitor-summary-grid` still exists.

- [ ] **Step 3: Split the monitor page header out of the oversized view**
```vue
<!-- frontend/src/components/monitor/MonitorWorkspaceSummary.vue -->
<script setup>
import WorkspaceSummary from '../workspace/WorkspaceSummary.vue'
defineProps({ activeTabLabel: String, activeUserCount: Number, loading: Boolean })
</script>

<template>
  <WorkspaceSummary title="系统观察">
    <template #meta>
      <div class="ink-inline-meta">
        <span class="status-badge status-badge--ok">{{ activeTabLabel }}</span>
        <span class="status-badge status-badge--warning">{{ activeUserCount }} 个活跃用户</span>
        <span class="status-badge" :class="loading ? 'status-badge--warning' : 'status-badge--ok'">{{ loading ? '数据刷新中' : '观察就绪' }}</span>
      </div>
    </template>
  </WorkspaceSummary>
</template>
```
```vue
<!-- frontend/src/views/MonitorCenter.vue -->
<MonitorWorkspaceSummary
  :active-tab-label="activeTabLabel"
  :active-user-count="userStats.length"
  :loading="loading"
/>
```
- [ ] **Step 4: Re-run monitor regressions**
Run: `python3 -m unittest tests.test_page_primary_content_layout_structure tests.test_frontend_performance_structure -q`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add frontend/src/components/monitor/MonitorWorkspaceSummary.vue frontend/src/views/MonitorCenter.vue tests/test_page_primary_content_layout_structure.py
git commit -m "feat: front-load monitor workspace content"
```
### Task 3: Downshift Alert Summary And Replace The Energy Double Header
**Files:**
- Modify: `frontend/src/views/AlertCenter.vue`
- Create: `frontend/src/components/energy/EnergyWorkspaceHeader.vue`
- Modify: `frontend/src/views/EnergyOptimization.vue`
- Modify: `tests/test_page_primary_content_layout_structure.py`
- Test: `tests/test_frontend_ui_structure.py`, `tests/test_frontend_performance_structure.py`

- [ ] **Step 1: Add failing alert and energy assertions**
```python
def test_alert_center_moves_summary_into_content_zone(self):
    text = (ROOT / "frontend/src/views/AlertCenter.vue").read_text(encoding="utf-8")
    self.assertNotIn('<div class="workspace-summary-strip">', text)
    self.assertIn("activeTab !== 'realtime'", text)

def test_energy_page_uses_compact_workspace_header(self):
    component_text = (ROOT / "frontend/src/components/energy/EnergyWorkspaceHeader.vue").read_text(encoding="utf-8")
    page_text = (ROOT / "frontend/src/views/EnergyOptimization.vue").read_text(encoding="utf-8")
    self.assertIn("energy-workspace-header", component_text)
    self.assertIn("EnergyWorkspaceHeader", page_text)
    self.assertNotIn("source-strip", page_text)
```
- [ ] **Step 2: Run the structure test and confirm failure**
Run: `python3 -m unittest tests.test_page_primary_content_layout_structure -q`
Expected: FAIL because the alert top strip still exists and `EnergyWorkspaceHeader.vue` is missing.

- [ ] **Step 3: Implement the alert downshift and energy header extraction**
```vue
<!-- frontend/src/views/AlertCenter.vue -->
<section class="workspace-nav-layout__content">
  <div v-if="activeTab !== 'realtime'" class="alert-content-summary">
    <AlertSummaryPanel :items="summaryItems" />
  </div>
  <AlertRealtimeStream v-if="activeTab === 'realtime'" ... />
</section>
```
```vue
<!-- frontend/src/components/energy/EnergyWorkspaceHeader.vue -->
<script setup>
defineProps({ sourceLabel: String, budgetLabel: String, periodLabel: String, sourceHint: String })
</script>

<template>
  <header class="energy-workspace-header si" style="--d:0s">
    <div>
      <h1 class="ink-title">能耗治理</h1>
      <p class="energy-workspace-header__caption">{{ sourceHint }}</p>
    </div>
    <div class="energy-workspace-header__meta">
      <span class="ink-period">{{ sourceLabel }}</span>
      <span class="ink-period">{{ budgetLabel }}</span>
      <span class="ink-period">{{ periodLabel }}</span>
    </div>
  </header>
</template>
```
- [ ] **Step 4: Re-run alert and energy regressions**
Run: `python3 -m unittest tests.test_page_primary_content_layout_structure tests.test_frontend_ui_structure tests.test_frontend_performance_structure -q`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add frontend/src/views/AlertCenter.vue frontend/src/components/energy/EnergyWorkspaceHeader.vue frontend/src/views/EnergyOptimization.vue tests/test_page_primary_content_layout_structure.py
git commit -m "feat: promote alert and energy primary workspaces"
```
### Task 4: Extract The AI Summary And Finish The Single-Layer Header Sweep
**Files:**
- Create: `frontend/src/components/ai/AIAssistantWorkspaceSummary.vue`
- Modify: `frontend/src/views/AIAssistant.vue`
- Modify: `tests/test_page_primary_content_layout_structure.py`
- Test: `tests/test_frontend_ui_structure.py`

- [ ] **Step 1: Add the failing AI assertions**
```python
def test_ai_page_uses_compact_summary_component(self):
    component_text = (ROOT / "frontend/src/components/ai/AIAssistantWorkspaceSummary.vue").read_text(encoding="utf-8")
    page_text = (ROOT / "frontend/src/views/AIAssistant.vue").read_text(encoding="utf-8")

    self.assertIn("WorkspaceSummary", component_text)
    self.assertIn("AIAssistantWorkspaceSummary", page_text)
    self.assertIn("WorkspaceTabs", page_text)
```
- [ ] **Step 2: Run the structure test and confirm failure**
Run: `python3 -m unittest tests.test_page_primary_content_layout_structure -q`
Expected: FAIL because `AIAssistantWorkspaceSummary.vue` does not exist yet.

- [ ] **Step 3: Extract the AI header from the oversized page**
```js
// frontend/src/views/AIAssistant.vue
const activeTabLabel = computed(() =>
  assistantTabs.find((item) => item.key === activeTab.value)?.label || '执行控制台'
)
```
```vue
<!-- frontend/src/components/ai/AIAssistantWorkspaceSummary.vue -->
<script setup>
import WorkspaceSummary from '../workspace/WorkspaceSummary.vue'
defineProps({ activeTabLabel: String, llmReady: Boolean })
</script>

<template>
  <WorkspaceSummary title="AI 执行控制台">
    <template #meta>
      <div class="ink-inline-meta">
        <span class="status-badge status-badge--ok">{{ activeTabLabel }}</span>
        <span class="status-badge status-badge--warning">需风险确认</span>
        <span class="status-badge" :class="llmReady ? 'status-badge--ok' : 'status-badge--warning'">{{ llmReady ? 'LLM 已就绪' : '规则解析模式' }}</span>
      </div>
    </template>
  </WorkspaceSummary>
</template>
```
- [ ] **Step 4: Re-run AI structure checks**
Run: `python3 -m unittest tests.test_page_primary_content_layout_structure tests.test_frontend_ui_structure -q`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add frontend/src/components/ai/AIAssistantWorkspaceSummary.vue frontend/src/views/AIAssistant.vue tests/test_page_primary_content_layout_structure.py
git commit -m "feat: streamline ai console summary"
```
### Task 5: Run The Full Regression Sweep And Lock The Layout Policy
- [ ] **Step 1: Run the complete structure suite**
Run: `python3 -m unittest tests.test_shell_header_pruning_structure tests.test_page_primary_content_layout_structure tests.test_frontend_ui_structure tests.test_governance_workbench_structure tests.test_frontend_performance_structure -q`
Expected: PASS.

- [ ] **Step 2: Run the affected pure model tests**
Run: `node --test frontend/src/lib/dashboardPageModels.test.js frontend/src/lib/governancePageModels.test.js`
Expected: `pass`, `fail 0`.

- [ ] **Step 3: Commit the final layout sweep**
```bash
git add frontend/src/views/Dashboard.vue frontend/src/components/dashboard/DashboardOverviewTab.vue frontend/src/views/GovernanceLayout.vue frontend/src/components/monitor/MonitorWorkspaceSummary.vue frontend/src/views/MonitorCenter.vue frontend/src/views/AlertCenter.vue frontend/src/components/energy/EnergyWorkspaceHeader.vue frontend/src/views/EnergyOptimization.vue frontend/src/components/ai/AIAssistantWorkspaceSummary.vue frontend/src/views/AIAssistant.vue tests/test_page_primary_content_layout_structure.py docs/superpowers/plans/2026-04-08-page-primary-content-layout.md
git commit -m "feat: prioritize primary content across console pages"
```

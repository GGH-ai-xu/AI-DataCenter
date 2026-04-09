# Shell Header Pruning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hide the shell-level `app-chrome` summary card on routes that already render a full page-local header, so dashboard, monitor, and governance pages stop showing two stacked title cards.

**Architecture:** Keep the decision at the router layer by marking target routes with `meta.hideShellHeader = true`, then let `frontend/src/views/ConsoleShell.vue` render its shell header conditionally from `route.meta`. Leave page-local summaries untouched so the only visible top card is the one owned by the page itself.

**Tech Stack:** Vue 3 router meta, Vue SFC templates, Python `unittest` structure checks.

---

### Task 1: Lock The Double-Header Rule In Structure Tests

**Files:**
- Modify: `tests/test_frontend_ui_structure.py`
- Test: `python3 -m unittest tests.test_frontend_ui_structure -q`

- [ ] **Step 1: Write the failing tests for route meta and shell gating**

```python
# tests/test_frontend_ui_structure.py
    def test_routes_mark_double_header_pages_to_hide_shell_header(self):
        text = (ROOT / "frontend/src/main.js").read_text(encoding="utf-8")

        self.assertRegex(
            text,
            r"(?s)path:\s*'',\s*name:\s*'Dashboard',\s*component:\s*loadDashboardView,\s*meta:\s*\{\s*hideShellHeader:\s*true\s*\}",
        )
        self.assertRegex(
            text,
            r"(?s)path:\s*'governance',\s*component:\s*loadGovernanceLayoutView,\s*meta:\s*\{\s*hideShellHeader:\s*true\s*\}",
        )
        self.assertRegex(
            text,
            r"(?s)path:\s*'monitor',\s*name:\s*'MonitorCenter',\s*component:\s*loadMonitorCenterView,\s*meta:\s*\{\s*hideShellHeader:\s*true\s*\}",
        )
        self.assertNotRegex(text, r"(?s)path:\s*'energy'.*hideShellHeader")
        self.assertNotRegex(text, r"(?s)path:\s*'alerts'.*hideShellHeader")
        self.assertNotRegex(text, r"(?s)path:\s*'ai'.*hideShellHeader")

    def test_console_shell_hides_shell_header_on_meta_flag(self):
        text = (ROOT / "frontend/src/views/ConsoleShell.vue").read_text(encoding="utf-8")

        self.assertIn('v-if="!shell.route.meta?.hideShellHeader"', text)
        self.assertIn('class="app-chrome tech-card"', text)

    def test_double_header_pages_keep_page_local_summary_blocks(self):
        dashboard_text = (ROOT / "frontend/src/views/Dashboard.vue").read_text(encoding="utf-8")
        monitor_text = (ROOT / "frontend/src/views/MonitorCenter.vue").read_text(encoding="utf-8")
        governance_text = (ROOT / "frontend/src/views/GovernanceLayout.vue").read_text(encoding="utf-8")

        self.assertIn("dashboard-summary", dashboard_text)
        self.assertIn("WorkspaceSummary", monitor_text)
        self.assertIn("WorkspaceSummary", governance_text)
```

- [ ] **Step 2: Run the test to verify red**

Run: `python3 -m unittest tests.test_frontend_ui_structure -q`

Expected: FAIL because `frontend/src/main.js` does not yet declare `hideShellHeader`, and `frontend/src/views/ConsoleShell.vue` still renders `app-chrome` unconditionally.

- [ ] **Step 3: Commit the red test**

```bash
git add tests/test_frontend_ui_structure.py
git commit -m "test: cover shell header pruning routes"
```

### Task 2: Add Router-Level Header Suppression And Gate The Shell Chrome

**Files:**
- Modify: `frontend/src/main.js`
- Modify: `frontend/src/views/ConsoleShell.vue`
- Test: `python3 -m unittest tests.test_frontend_ui_structure -q`

- [ ] **Step 1: Mark the double-header routes with `hideShellHeader`**

```js
// frontend/src/main.js
  {
    path: '/',
    component: loadConsoleShellView,
    children: [
      { path: '', name: 'Dashboard', component: loadDashboardView, meta: { hideShellHeader: true } },
      { path: 'gpu/:index', name: 'GpuDetail', component: loadGpuDetailView },
      {
        path: 'governance',
        component: loadGovernanceLayoutView,
        meta: { hideShellHeader: true },
        children: [
          { path: '', redirect: '/governance/actions' },
          { path: 'actions', name: 'GovernanceActions', component: loadGovernanceActionsView },
          { path: 'policies', name: 'GovernancePolicies', component: loadGovernancePoliciesView },
          { path: 'review', name: 'GovernanceReview', component: loadGovernanceReviewView },
        ],
      },
      { path: 'tasks', redirect: '/governance/actions' },
      { path: 'scheduler', redirect: '/governance/policies' },
      { path: 'energy', name: 'EnergyOptimization', component: loadEnergyOptimizationView },
      { path: 'ai', name: 'AIAssistant', component: loadAIAssistantView },
      { path: 'alerts', name: 'AlertCenter', component: loadAlertCenterView },
      { path: 'monitor', name: 'MonitorCenter', component: loadMonitorCenterView, meta: { hideShellHeader: true } },
    ],
  },
```

- [ ] **Step 2: Make the shell header conditional**

```vue
<!-- frontend/src/views/ConsoleShell.vue -->
        <header v-if="!shell.route.meta?.hideShellHeader" class="app-chrome tech-card">
          <div class="app-chrome__top">
            <div class="app-chrome__copy">
              <div class="app-chrome__eyebrow">{{ shell.currentWorkspaceMeta.eyebrow }}</div>
              <div class="app-chrome__title-row">
                <h1 class="app-chrome__title">{{ shell.activeNavItem.label }}</h1>
                <span class="app-chrome__status" :class="shell.wsConnected ? 'app-chrome__status--ok' : 'app-chrome__status--warning'">
                  <span class="app-chrome__status-dot"></span>
                  {{ shell.wsConnected ? '实时连接正常' : '连接处理中' }}
                </span>
              </div>
              <p class="app-chrome__desc">
                {{ shell.activeNavItem.desc }} {{ shell.currentWorkspaceMeta.desc }}
              </p>
            </div>

            <div class="app-chrome__actions">
              <button
                v-if="shell.isDesktop && shell.appInfo.updateSupported"
                type="button"
                class="btn-tech"
                :disabled="shell.updateBusy"
                @click="shell.checkForUpdates"
              >
                {{ shell.updateBusy ? '检查中...' : '检查更新' }}
              </button>
            </div>
          </div>
          <div class="app-chrome__meta">
            <div v-for="item in shell.chromeMetrics" :key="item.label" class="app-chrome__metric">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </div>
          </div>
        </header>
```

- [ ] **Step 3: Run the structure test to verify green**

Run: `python3 -m unittest tests.test_frontend_ui_structure -q`

Expected: PASS, with `Dashboard` / `governance` / `monitor` all carrying `hideShellHeader` and the shell header now guarded by `route.meta`.

- [ ] **Step 4: Commit the feature**

```bash
git add frontend/src/main.js frontend/src/views/ConsoleShell.vue tests/test_frontend_ui_structure.py
git commit -m "feat: hide shell header on double-summary pages"
```

### Task 3: Run Focused Regression Coverage For Shell And Governance Layout

**Files:**
- Verify: `frontend/src/main.js`
- Verify: `frontend/src/views/ConsoleShell.vue`
- Verify: `frontend/src/views/Dashboard.vue`
- Verify: `frontend/src/views/MonitorCenter.vue`
- Verify: `frontend/src/views/GovernanceLayout.vue`
- Test: `tests/test_governance_workbench_structure.py`
- Test: `tests/test_frontend_ui_structure.py`
- Test: `tests/test_frontend_performance_structure.py`

- [ ] **Step 1: Run the focused regression suite**

Run: `python3 -m unittest tests.test_governance_workbench_structure tests.test_frontend_ui_structure tests.test_frontend_performance_structure -q`

Expected: PASS, confirming the shell header rule did not break governance routing, shared shell structure, or existing workspace layout constraints.

- [ ] **Step 2: Check the touched files for size regressions**

Run: `wc -l frontend/src/main.js frontend/src/views/ConsoleShell.vue tests/test_frontend_ui_structure.py`

Expected: line counts remain reasonable and no new oversized helper file is introduced for this small routing change.

- [ ] **Step 3: Commit the verification snapshot**

```bash
git add frontend/src/main.js frontend/src/views/ConsoleShell.vue tests/test_frontend_ui_structure.py
git commit -m "test: verify shell header pruning regression coverage"
```

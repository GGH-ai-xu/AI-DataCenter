# App Sidebar Entry-First Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把控制台左侧边栏改成“品牌摘要 + 分类入口 + 极简时间 footer”的入口优先布局。

**Architecture:** 保留 `AppPrimarySidebar.vue` 作为三段式宿主，顶部展示导入摘要，中部由 `SidebarNavRail.vue` 负责分类 tab 与入口过滤，底部由 `SidebarInfoDock.vue` 退化为单纯时间显示。`App.vue` 只补充导航分组元数据与摘要文案。

**Tech Stack:** Vue 3 SFC、Pinia、Vue Router、Python `unittest` 结构测试、Vite build。

---

### Task 1: Rewrite The Sidebar Structure Tests

**Files:**
- Modify: `tests/test_frontend_ui_structure.py`
- Test: `tests/test_frontend_ui_structure.py`

- [ ] **Step 1: Write the failing tests**

在 `tests/test_frontend_ui_structure.py` 中替换旧的 dock 断言，新增这些检查：

```python
def test_primary_sidebar_uses_group_tabs_for_navigation(self):
    text = (ROOT / "frontend/src/components/app/SidebarNavRail.vue").read_text(encoding="utf-8")
    self.assertIn("治理", text)
    self.assertIn("分析", text)
    self.assertIn("支持", text)
    self.assertIn("item.group === activeGroup.value", text)

def test_primary_sidebar_footer_is_time_only(self):
    text = (ROOT / "frontend/src/components/app/SidebarInfoDock.vue").read_text(encoding="utf-8")
    self.assertIn("时间", text)
    self.assertNotIn("运行台", text)
    self.assertNotIn("桌面端", text)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
timeout 60s cmd.exe /c ".venv\Scripts\python.exe -m unittest tests.test_frontend_ui_structure.FrontendUIStructureTests.test_primary_sidebar_uses_group_tabs_for_navigation tests.test_frontend_ui_structure.FrontendUIStructureTests.test_primary_sidebar_footer_is_time_only -v"
```

Expected: FAIL because `SidebarNavRail.vue` still renders a flat list and `SidebarInfoDock.vue` still contains the old runtime/desktop dock.

- [ ] **Step 3: Commit**

```bash
git add tests/test_frontend_ui_structure.py
git commit -m "test: redefine sidebar structure expectations"
```

### Task 2: Implement The Entry-First Sidebar

**Files:**
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/components/app/AppPrimarySidebar.vue`
- Modify: `frontend/src/components/app/SidebarBrandCard.vue`
- Modify: `frontend/src/components/app/SidebarNavRail.vue`
- Modify: `frontend/src/components/app/SidebarInfoDock.vue`
- Test: `tests/test_frontend_ui_structure.py`

- [ ] **Step 1: Write minimal implementation for summary and grouped nav**

实现这些变化：

```js
const navItems = [
  { path: '/', label: '总览', icon: '览', desc: '本次导入 GPU 总览', group: 'governance' },
  { path: '/tasks', label: '任务', icon: '务', desc: '处置真实任务', group: 'governance' },
  { path: '/scheduler', label: '调度', icon: '策', desc: '预算与治理动作', group: 'governance' },
  { path: '/energy', label: '能耗', icon: '能', desc: '节能复盘与测算', group: 'analysis' },
  { path: '/monitor', label: '观察', icon: '观', desc: '画像与过程观察', group: 'analysis' },
  { path: '/alerts', label: '告警', icon: '警', desc: '风险台与异常确认', group: 'analysis' },
  { path: '/ai', label: '智能', icon: '智', desc: 'AI 解释与问答', group: 'support' },
]
```

并在边栏组件中：

```vue
<SidebarBrandCard :app-info="props.appInfo" :summary="props.summary" />
<SidebarNavRail :nav-items="props.navItems" :current-path="props.currentPath" />
<SidebarInfoDock :current-time="props.currentTime" />
```

- [ ] **Step 2: Run sidebar structure tests**

Run:

```bash
timeout 60s cmd.exe /c ".venv\Scripts\python.exe -m unittest tests.test_frontend_ui_structure -v"
```

Expected: PASS for sidebar assertions and no regressions in the same file.

- [ ] **Step 3: Run frontend build**

Run:

```bash
cmd.exe /c "cd /d E:\Code\AI-DataCenter\frontend && npm run build"
```

Expected: Vite build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.vue frontend/src/components/app/AppPrimarySidebar.vue frontend/src/components/app/SidebarBrandCard.vue frontend/src/components/app/SidebarNavRail.vue frontend/src/components/app/SidebarInfoDock.vue
git commit -m "refactor: prioritize grouped navigation in sidebar"
```

## Self-Review

- Spec coverage: 已覆盖摘要、分类导航、时间 footer、旧 dock 移除。
- Placeholder scan: 无 `TODO`/`TBD` 占位符。
- Type consistency: 分组字段统一为 `group`，分组值统一为 `governance` / `analysis` / `support`。

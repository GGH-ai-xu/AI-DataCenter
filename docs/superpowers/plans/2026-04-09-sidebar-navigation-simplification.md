# Sidebar Navigation Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将控制台左侧边栏收敛为“轻量头部 + 六入口常驻导航”，保留切换服务器入口，删除低价值的时间与遥测信息块。

**Architecture:** 以 `AppPrimarySidebar.vue` 为统一容器，压缩 `SidebarBrandCard.vue` 为轻量头部，重写 `SidebarNavRail.vue` 为静态分组标题加六入口直达列表，并从 `useConsoleShell.js`、`ConsoleShell.vue`、`App.vue`、`style.css` 中移除只服务旧侧栏底部信息卡和分组按钮的死依赖。测试以 `tests/test_frontend_ui_structure.py` 为主，先写失败断言，再逐步实现。

**Tech Stack:** Vue 3 SFC、Vue Router、现有控制台 CSS 变量体系、Python `unittest` 结构测试。

---

### Task 1: 压缩侧栏头部并移除底部信息卡

**Files:**
- Modify: `tests/test_frontend_ui_structure.py`
- Modify: `frontend/src/components/app/AppPrimarySidebar.vue`
- Modify: `frontend/src/components/app/SidebarBrandCard.vue`
- Modify: `frontend/src/views/ConsoleShell.vue`
- Delete: `frontend/src/components/app/SidebarInfoDock.vue`

**Test:**
- `tests/test_frontend_ui_structure.py`

- [ ] **Step 1: 写失败测试，先锁定“没有底部信息卡、品牌区只剩摘要和切换按钮”**

```python
def test_primary_sidebar_is_split_into_specialized_components(self):
    for rel in [
        "frontend/src/components/app/SidebarBrandCard.vue",
        "frontend/src/components/app/SidebarNavRail.vue",
    ]:
        self.assertTrue((ROOT / rel).exists(), rel)

    text = (ROOT / "frontend/src/components/app/AppPrimarySidebar.vue").read_text(encoding="utf-8")
    self.assertIn("SidebarBrandCard", text)
    self.assertIn("SidebarNavRail", text)
    self.assertNotIn("SidebarInfoDock", text)

def test_primary_sidebar_uses_compact_summary_header(self):
    brand_text = (ROOT / "frontend/src/components/app/SidebarBrandCard.vue").read_text(encoding="utf-8")
    sidebar_text = (ROOT / "frontend/src/components/app/AppPrimarySidebar.vue").read_text(encoding="utf-8")

    self.assertIn("app-sidebar-brand-card__summary", brand_text)
    self.assertIn("切换服务器", brand_text)
    self.assertNotIn("app-sidebar-brand-card__pill", brand_text)
    self.assertNotIn("app-sidebar-brand-card__detail", brand_text)
    self.assertNotIn("current-time", sidebar_text)
    self.assertNotIn("telemetry", sidebar_text)
```

- [ ] **Step 2: 运行测试并确认它因旧结构失败**

Run:

```bash
timeout 60s python3 -m unittest \
  tests.test_frontend_ui_structure.FrontendUIStructureTests.test_primary_sidebar_is_split_into_specialized_components \
  tests.test_frontend_ui_structure.FrontendUIStructureTests.test_primary_sidebar_uses_compact_summary_header \
  -q
```

Expected:

```text
AssertionError: 'SidebarInfoDock' unexpectedly found
AssertionError: 'app-sidebar-brand-card__pill' unexpectedly found
```

- [ ] **Step 3: 写最小实现，先把侧栏容器和品牌头部压平**

`frontend/src/components/app/AppPrimarySidebar.vue`

```vue
<script setup>
import SidebarBrandCard from './SidebarBrandCard.vue'
import SidebarNavRail from './SidebarNavRail.vue'

const props = defineProps({
  appInfo: { type: Object, required: true },
  switchServerBusy: { type: Boolean, required: true },
  currentPath: { type: String, required: true },
  navItems: { type: Array, required: true },
  summary: { type: String, required: true },
  workspaceLocked: { type: Boolean, required: true },
})

const emit = defineEmits(['navigate', 'switch-server'])
</script>

<template>
  <div class="app-primary-sidebar">
    <SidebarBrandCard
      :app-info="props.appInfo"
      :summary="props.summary"
      :switch-server-busy="props.switchServerBusy"
      @switch-server="emit('switch-server')"
    />
    <div class="app-primary-sidebar__nav">
      <SidebarNavRail
        :nav-items="props.navItems"
        :current-path="props.currentPath"
        :workspace-locked="props.workspaceLocked"
        @navigate="emit('navigate', $event)"
      />
    </div>
  </div>
</template>

<style scoped>
.app-primary-sidebar {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: 18px;
  min-height: calc(100vh - 44px);
  padding: 18px;
  border-radius: 28px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: #121a24;
  box-shadow: 0 18px 44px rgba(0, 0, 0, 0.28);
}

.app-primary-sidebar__nav {
  min-height: 0;
}
</style>
```

`frontend/src/components/app/SidebarBrandCard.vue`

```vue
<template>
  <section class="app-sidebar-brand-card">
    <div class="app-sidebar-brand-card__main">
      <div class="app-sidebar-brand-card__crest">
        <img class="app-sidebar-brand-card__logo" src="/logo.svg" alt="AI-DataCenter logo" />
      </div>
      <div class="app-sidebar-brand-card__copy">
        <h1 class="app-sidebar-brand-card__title">{{ props.appInfo.name || '智算中心优化代码生成系统' }}</h1>
        <p class="app-sidebar-brand-card__summary">{{ props.summary || '导入范围待确认' }}</p>
      </div>
      <button
        type="button"
        class="app-sidebar-brand-card__switch"
        :disabled="props.switchServerBusy"
        @click="emit('switch-server')"
      >
        {{ props.switchServerBusy ? '切换中...' : '切换服务器' }}
      </button>
    </div>
  </section>
</template>
```

`frontend/src/views/ConsoleShell.vue`

```vue
<AppPrimarySidebar
  :app-info="shell.appInfo"
  :current-path="shell.route.path"
  :nav-items="shell.navItems"
  :summary="shell.sidebarSummary"
  :switch-server-busy="shell.switchServerBusy"
  :workspace-locked="shell.workspaceLocked"
  @navigate="shell.navigateTo"
  @switch-server="shell.switchServer"
/>
```

Delete the dead file entirely:

```text
frontend/src/components/app/SidebarInfoDock.vue
```

- [ ] **Step 4: 重新运行同一组测试，确认头部压缩和底部移除通过**

Run:

```bash
timeout 60s python3 -m unittest \
  tests.test_frontend_ui_structure.FrontendUIStructureTests.test_primary_sidebar_is_split_into_specialized_components \
  tests.test_frontend_ui_structure.FrontendUIStructureTests.test_primary_sidebar_uses_compact_summary_header \
  -q
```

Expected:

```text
OK
```

- [ ] **Step 5: 提交这一小步**

```bash
git add tests/test_frontend_ui_structure.py \
  frontend/src/components/app/AppPrimarySidebar.vue \
  frontend/src/components/app/SidebarBrandCard.vue \
  frontend/src/views/ConsoleShell.vue \
  frontend/src/components/app/SidebarInfoDock.vue
git commit -m "refactor: compact console sidebar header"
```

### Task 2: 重写导航为六入口常驻列表

**Files:**
- Modify: `tests/test_frontend_ui_structure.py`
- Modify: `frontend/src/components/app/SidebarNavRail.vue`

**Test:**
- `tests/test_frontend_ui_structure.py`

- [ ] **Step 1: 写失败测试，锁定“没有可点击分组按钮、只有静态分组标题、仅当前项显示描述”**

```python
def test_primary_sidebar_uses_static_section_titles_for_navigation(self):
    shell_text = (ROOT / "frontend/src/composables/useConsoleShell.js").read_text(encoding="utf-8")
    nav_text = (ROOT / "frontend/src/components/app/SidebarNavRail.vue").read_text(encoding="utf-8")

    self.assertIn("group: 'governance'", shell_text)
    self.assertIn("group: 'analysis'", shell_text)
    self.assertIn("group: 'support'", shell_text)
    self.assertNotIn("const NAV_GROUPS", nav_text)
    self.assertNotIn("activeGroup", nav_text)
    self.assertNotIn("app-primary-nav__group", nav_text)
    self.assertIn("app-primary-nav__section-title", nav_text)
    self.assertIn('v-if="isActive(item)"', nav_text)
```

- [ ] **Step 2: 运行测试并确认它因旧导航筛选逻辑失败**

Run:

```bash
timeout 60s python3 -m unittest \
  tests.test_frontend_ui_structure.FrontendUIStructureTests.test_primary_sidebar_uses_static_section_titles_for_navigation \
  -q
```

Expected:

```text
AssertionError: 'const NAV_GROUPS' unexpectedly found
AssertionError: 'app-primary-nav__section-title' not found
```

- [ ] **Step 3: 写最小实现，把导航改成静态分组标题 + 六入口直达**

`frontend/src/components/app/SidebarNavRail.vue`

```vue
<script setup>
import { computed } from 'vue'

const SECTION_ORDER = Object.freeze([
  { key: 'governance', label: '治理' },
  { key: 'analysis', label: '分析' },
  { key: 'support', label: '支持' },
])

const props = defineProps({
  navItems: { type: Array, required: true },
  currentPath: { type: String, required: true },
  workspaceLocked: { type: Boolean, required: true },
})

const emit = defineEmits(['navigate'])

const navSections = computed(() =>
  SECTION_ORDER.map((section) => ({
    ...section,
    items: props.navItems.filter((item) => item.group === section.key),
  })).filter((section) => section.items.length > 0)
)

function isActive(item) {
  const prefix = item.matchPrefix || item.path
  return props.currentPath === item.path || (prefix !== '/' && props.currentPath.startsWith(prefix))
}
</script>

<template>
  <nav class="app-primary-nav-rail">
    <section
      v-for="section in navSections"
      :key="section.key"
      class="app-primary-nav__section"
    >
      <div class="app-primary-nav__section-title">{{ section.label }}</div>
      <div class="app-primary-nav__scroll">
        <button
          v-for="item in section.items"
          :key="item.path"
          type="button"
          class="app-primary-nav__item"
          :class="{
            'app-primary-nav__item--active': isActive(item),
            'app-primary-nav__item--locked': props.workspaceLocked && item.path !== '/',
          }"
          @click="emit('navigate', item)"
        >
          <span class="app-primary-nav__seal">{{ item.icon }}</span>
          <span class="app-primary-nav__body">
            <strong class="app-primary-nav__label">{{ item.label }}</strong>
            <span v-if="isActive(item)" class="app-primary-nav__desc">{{ item.desc }}</span>
          </span>
        </button>
      </div>
    </section>
  </nav>
</template>
```

Style the section headers as static dividers, not pills:

```css
.app-primary-nav__section {
  display: grid;
  gap: 10px;
}

.app-primary-nav__section-title {
  padding: 0 4px;
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--text-muted);
}
```

- [ ] **Step 4: 重新运行导航测试，确认六入口常驻结构通过**

Run:

```bash
timeout 60s python3 -m unittest \
  tests.test_frontend_ui_structure.FrontendUIStructureTests.test_primary_sidebar_uses_static_section_titles_for_navigation \
  -q
```

Expected:

```text
OK
```

- [ ] **Step 5: 提交这一小步**

```bash
git add tests/test_frontend_ui_structure.py \
  frontend/src/components/app/SidebarNavRail.vue
git commit -m "refactor: keep six direct sidebar entries visible"
```

### Task 3: 收掉旧侧栏数据与全局无效选择器

**Files:**
- Modify: `tests/test_frontend_ui_structure.py`
- Modify: `frontend/src/composables/useConsoleShell.js`
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/style.css`

**Test:**
- `tests/test_frontend_ui_structure.py`

- [ ] **Step 1: 写失败测试，锁定“没有 currentTime、没有 sidebarTelemetry、没有分组按钮选择器”**

```python
def test_console_shell_sidebar_wiring_is_trimmed(self):
    shell_text = (ROOT / "frontend/src/composables/useConsoleShell.js").read_text(encoding="utf-8")
    console_text = (ROOT / "frontend/src/views/ConsoleShell.vue").read_text(encoding="utf-8")
    app_text = (ROOT / "frontend/src/App.vue").read_text(encoding="utf-8")
    style_text = (ROOT / "frontend/src/style.css").read_text(encoding="utf-8")

    self.assertNotIn(":current-time", console_text)
    self.assertNotIn(":telemetry", console_text)
    self.assertNotIn("currentTime = ref('')", shell_text)
    self.assertNotIn("sidebarTelemetry", shell_text)
    self.assertNotIn(".app-primary-nav__group", app_text)
    self.assertNotIn(".app-primary-nav__group", style_text)
```

- [ ] **Step 2: 运行测试并确认它因旧壳层状态和旧 selector 失败**

Run:

```bash
timeout 60s python3 -m unittest \
  tests.test_frontend_ui_structure.FrontendUIStructureTests.test_console_shell_sidebar_wiring_is_trimmed \
  -q
```

Expected:

```text
AssertionError: ':current-time' unexpectedly found
AssertionError: 'sidebarTelemetry' unexpectedly found
AssertionError: '.app-primary-nav__group' unexpectedly found
```

- [ ] **Step 3: 写最小实现，收掉旧状态并清理全局 selector**

`frontend/src/composables/useConsoleShell.js`

```js
export function useConsoleShell() {
  const route = useRoute()
  const router = useRouter()
  const store = useAppStore()
  const auth = useAuthStore()
  const appInfo = ref(baseAppInfo())
  const updateState = ref(null)
  const updateBusy = ref(false)
  const switchServerBusy = ref(false)
  const closeDialog = ref(null)
  const closeBusy = ref(false)
  let workspaceTimer = null
  let updateStateTimer = null
  let removeCloseListener = null

  const sidebarSummary = computed(() => {
    const modeLabel = compactSidebarModeLabel(appInfo.value.connectionModeLabel || '')
    const importedLabel = formatImportedGpuLabel(store.importContext?.imported_gpu_indexes || [])
    return `${modeLabel} · ${importedLabel}`
  })

  return {
    activeNavItem,
    appInfo,
    chromeMetrics,
    clearUpdateNotice,
    closeBusy,
    closeDialog,
    currentWorkspaceMeta,
    isDesktop,
    navItems: NAV_ITEMS,
    navigateTo,
    route,
    runtimeBanner,
    sidebarSummary,
    switchServer,
    switchServerBusy,
    updateBusy,
    updateState,
    workspaceLocked,
    wsConnected,
  }
}
```

`frontend/src/App.vue`

```js
const selector = [
  '.tech-card',
  '.btn-tech',
  '.workspace-tab',
  '.import-prep-tabs__item',
  '.app-primary-nav__item',
  '.app-mobile-nav__item',
  '.app-mobile-nav__action',
  '.overview-route',
  '.app-sidebar-brand-card__switch',
].join(', ')
```

`frontend/src/style.css`

```css
.tech-card,
.btn-tech,
.workspace-tab,
.import-prep-tabs__item,
.app-primary-nav__item,
.app-mobile-nav__item,
.app-mobile-nav__action,
.overview-route,
.app-sidebar-brand-card__switch {
  --spotlight-x: 50%;
  --spotlight-y: 0%;
  --spotlight-opacity: 0;
}
```

- [ ] **Step 4: 跑完整的前端结构测试文件，确认侧栏重构不破坏现有壳层结构**

Run:

```bash
timeout 60s python3 -m unittest tests.test_frontend_ui_structure -q
```

Expected:

```text
OK
```

- [ ] **Step 5: 提交这一小步**

```bash
git add tests/test_frontend_ui_structure.py \
  frontend/src/composables/useConsoleShell.js \
  frontend/src/App.vue \
  frontend/src/style.css
git commit -m "refactor: trim console sidebar shell state"
```

### Task 4: 最终回归与死引用扫描

**Files:**
- Modify: `tests/test_frontend_ui_structure.py` if any assertion names need final alignment

**Test:**
- `tests/test_frontend_ui_structure.py`
- `tests/test_shell_header_pruning_structure.py`
- `tests/test_page_primary_content_layout_structure.py`

- [ ] **Step 1: 扫描死引用，确认侧栏旧实现没有残留**

Run:

```bash
rg -n "SidebarInfoDock|app-primary-nav__group|sidebarTelemetry|currentTime = ref\\(''\\)" \
  frontend/src tests
```

Expected:

```text
stdout should be empty, or only mention the updated plan file and updated test file.
```

- [ ] **Step 2: 运行最终回归**

Run:

```bash
timeout 60s python3 -m unittest \
  tests.test_frontend_ui_structure \
  tests.test_shell_header_pruning_structure \
  tests.test_page_primary_content_layout_structure \
  -q
```

Expected:

```text
OK
```

- [ ] **Step 3: 提交最终整合结果**

```bash
git add tests/test_frontend_ui_structure.py \
  frontend/src/components/app/AppPrimarySidebar.vue \
  frontend/src/components/app/SidebarBrandCard.vue \
  frontend/src/components/app/SidebarNavRail.vue \
  frontend/src/composables/useConsoleShell.js \
  frontend/src/views/ConsoleShell.vue \
  frontend/src/App.vue \
  frontend/src/style.css
git commit -m "refactor: simplify console sidebar navigation"
```

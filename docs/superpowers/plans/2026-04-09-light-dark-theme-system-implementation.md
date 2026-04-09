# Light/Dark Theme System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a global light/dark theme system with `system / dark / light` preference, consistent root token switching, and a sidebar/mobile theme switch that works across the shell, import flow, auth pages, and key top-level pages.

**Architecture:** Add one theme state source in the app store, one theme runtime module for preference parsing and DOM sync, and a dual-token CSS system driven by `document.documentElement.dataset.theme`. Keep page-local theme variables such as `--console-*` and `--import-*`, but remap them to semantic global tokens so shells preserve their character without staying hardcoded dark.

**Tech Stack:** Vue 3, Pinia, Vite, Node `node:test`, Python `unittest`, scoped Vue SFC styles, global CSS custom properties.

---

## File Structure

### New files

- `frontend/src/lib/themeMode.js`
  - Theme constants, preference validation, system theme resolution, root DOM sync, listener registration, local storage helpers.
- `frontend/src/lib/themeMode.test.js`
  - Node tests for preference validation, system resolution, DOM sync, and listener behavior.
- `frontend/src/components/app/ThemeModeSwitch.vue`
  - Reusable three-state theme switch supporting expanded, collapsed, and compact/mobile rendering.

### Modified files

- `frontend/src/stores/app.js`
  - Store-owned `themePreference`, `resolvedTheme`, and actions for hydration and updates.
- `frontend/src/stores/app.test.js`
  - Regression coverage for theme state hydration and preference updates.
- `frontend/src/App.vue`
  - Bootstraps theme runtime and cleans up media-query listeners on unmount.
- `frontend/src/style.css`
  - Introduces `:root[data-theme='dark']` and `:root[data-theme='light']`, plus theme-aware background, scrollbar, selection, and card tokens.
- `frontend/src/views/ConsoleShell.vue`
  - Remaps `--console-*` to semantic tokens and wires in theme switch entry points for desktop/mobile shell chrome.
- `frontend/src/composables/useConsoleShell.js`
  - Proxies theme preference/resolved theme from the store into shell UI actions.
- `frontend/src/components/app/AppPrimarySidebar.vue`
  - Hosts the new theme switch above the collapse control.
- `frontend/src/components/app/SidebarBrandCard.vue`
  - Removes remaining hardcoded deep-dark button/background assumptions so brand block follows theme tokens.
- `frontend/src/components/app/SidebarNavRail.vue`
  - Replaces remaining hardcoded deep-dark nav item colors with semantic tokens.
- `frontend/src/views/ImportWorkspace.vue`
  - Remaps `--import-*` variables to semantic tokens so the import shell switches coherently.
- `frontend/src/views/LoginView.vue`
  - Makes hero gradient, card surfaces, and field colors theme-aware.
- `frontend/src/views/ChangePasswordView.vue`
  - Same theme-aware cleanup as login.
- `frontend/src/views/Dashboard.vue`
  - Fixes any remaining shell-specific hardcoded text/background assumptions under light theme.
- `frontend/src/views/GovernanceLayout.vue`
  - Ensures header/meta surfaces remain readable in light theme.
- `frontend/src/views/EnergyOptimization.vue`
  - Fixes page-local tokens and hardcoded translucent surfaces that assume dark backgrounds.
- `frontend/src/views/MonitorCenter.vue`
  - Fixes any remaining hardcoded highlight/background values revealed by light theme.
- `frontend/src/views/AIAssistant.vue`
  - Ensures panel surfaces, warnings, and highlights stay readable in light mode.
- `frontend/src/views/AlertCenter.vue`
  - Makes `severityConfig` derive from semantic theme variables instead of hardcoded warning/danger colors.
- `tests/test_frontend_ui_structure.py`
  - Structural assertions for the theme switch component, root theme tokens, and App bootstrap wiring.

---

### Task 1: Build Theme Runtime Core

**Files:**
- Create: `frontend/src/lib/themeMode.js`
- Test: `frontend/src/lib/themeMode.test.js`

- [ ] **Step 1: Write the failing test**

```js
import test from 'node:test'
import assert from 'node:assert/strict'

import {
  THEME_PREFERENCES,
  DEFAULT_THEME_PREFERENCE,
  normalizeThemePreference,
  resolveThemeFromPreference,
  applyResolvedThemeToDocument,
} from './themeMode.js'

test('normalizeThemePreference falls back to system for invalid values', () => {
  assert.equal(DEFAULT_THEME_PREFERENCE, 'system')
  assert.equal(normalizeThemePreference('dark'), 'dark')
  assert.equal(normalizeThemePreference('light'), 'light')
  assert.equal(normalizeThemePreference('system'), 'system')
  assert.equal(normalizeThemePreference('unexpected'), 'system')
  assert.deepEqual(THEME_PREFERENCES, ['system', 'dark', 'light'])
})

test('resolveThemeFromPreference respects explicit overrides before system state', () => {
  assert.equal(resolveThemeFromPreference('dark', false), 'dark')
  assert.equal(resolveThemeFromPreference('light', true), 'light')
  assert.equal(resolveThemeFromPreference('system', true), 'dark')
  assert.equal(resolveThemeFromPreference('system', false), 'light')
})

test('applyResolvedThemeToDocument updates dataset theme and color scheme', () => {
  const root = {
    dataset: {},
    style: {
      applied: {},
      setProperty(name, value) {
        this.applied[name] = value
      },
    },
  }

  applyResolvedThemeToDocument(root, 'light')
  assert.equal(root.dataset.theme, 'light')
  assert.equal(root.style.applied['color-scheme'], 'light')
})
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
npm test -- frontend/src/lib/themeMode.test.js
```

Expected: FAIL because `frontend/src/lib/themeMode.js` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

```js
export const THEME_PREFERENCES = Object.freeze(['system', 'dark', 'light'])
export const DEFAULT_THEME_PREFERENCE = 'system'

export function normalizeThemePreference(value) {
  return THEME_PREFERENCES.includes(value) ? value : DEFAULT_THEME_PREFERENCE
}

export function resolveThemeFromPreference(preference, systemPrefersDark) {
  const normalized = normalizeThemePreference(preference)
  if (normalized === 'dark') return 'dark'
  if (normalized === 'light') return 'light'
  return systemPrefersDark ? 'dark' : 'light'
}

export function applyResolvedThemeToDocument(root, resolvedTheme) {
  root.dataset.theme = resolvedTheme
  root.style.setProperty('color-scheme', resolvedTheme)
}
```

- [ ] **Step 4: Expand runtime helpers for storage and media-query wiring**

```js
export const THEME_STORAGE_KEY = 'ai-datacenter-theme-preference'

export function readStoredThemePreference(storage) {
  return normalizeThemePreference(storage?.getItem(THEME_STORAGE_KEY))
}

export function writeStoredThemePreference(storage, preference) {
  const normalized = normalizeThemePreference(preference)
  storage?.setItem(THEME_STORAGE_KEY, normalized)
  return normalized
}

export function watchSystemTheme(windowObject, onChange) {
  const query = windowObject.matchMedia('(prefers-color-scheme: dark)')
  const handler = (event) => onChange(Boolean(event.matches))
  query.addEventListener('change', handler)
  return {
    matches: Boolean(query.matches),
    dispose: () => query.removeEventListener('change', handler),
  }
}
```

- [ ] **Step 5: Run test to verify it passes**

Run:

```bash
npm test -- frontend/src/lib/themeMode.test.js
```

Expected: PASS with all `themeMode` tests green.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/themeMode.js frontend/src/lib/themeMode.test.js
git commit -m "feat: add theme runtime core"
```

### Task 2: Add Store-Owned Theme State

**Files:**
- Modify: `frontend/src/stores/app.js`
- Test: `frontend/src/stores/app.test.js`

- [ ] **Step 1: Write the failing store test**

```js
import test from 'node:test'
import assert from 'node:assert/strict'
import { createPinia, setActivePinia } from 'pinia'
import { useAppStore } from './app.js'

test('theme preference defaults to system and can resolve to explicit theme', () => {
  setActivePinia(createPinia())
  const store = useAppStore()

  assert.equal(store.themePreference, 'system')
  assert.equal(store.resolvedTheme, 'dark')

  store.setThemePreference('light')
  assert.equal(store.themePreference, 'light')
  assert.equal(store.resolvedTheme, 'light')
})
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
npm test -- frontend/src/stores/app.test.js
```

Expected: FAIL because `themePreference`, `resolvedTheme`, and `setThemePreference` do not exist.

- [ ] **Step 3: Add minimal store state and actions**

```js
import {
  DEFAULT_THEME_PREFERENCE,
  normalizeThemePreference,
  resolveThemeFromPreference,
} from '../lib/themeMode.js'

const themePreference = ref(DEFAULT_THEME_PREFERENCE)
const resolvedTheme = ref('dark')

function syncResolvedTheme(systemPrefersDark = true) {
  resolvedTheme.value = resolveThemeFromPreference(themePreference.value, systemPrefersDark)
}

function setThemePreference(nextPreference, systemPrefersDark = true) {
  themePreference.value = normalizeThemePreference(nextPreference)
  syncResolvedTheme(systemPrefersDark)
}
```

- [ ] **Step 4: Add hydration and helper computed values**

```js
const isSystemTheme = computed(() => themePreference.value === 'system')
const isDarkTheme = computed(() => resolvedTheme.value === 'dark')
const isLightTheme = computed(() => resolvedTheme.value === 'light')

function hydrateThemePreference(nextPreference, systemPrefersDark = true) {
  themePreference.value = normalizeThemePreference(nextPreference)
  syncResolvedTheme(systemPrefersDark)
}
```

- [ ] **Step 5: Export the theme store API**

```js
return {
  // existing exports...
  themePreference,
  resolvedTheme,
  isSystemTheme,
  isDarkTheme,
  isLightTheme,
  hydrateThemePreference,
  setThemePreference,
  syncResolvedTheme,
}
```

- [ ] **Step 6: Run test to verify it passes**

Run:

```bash
npm test -- frontend/src/stores/app.test.js
```

Expected: PASS with old store tests and new theme store test all green.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/stores/app.js frontend/src/stores/app.test.js
git commit -m "feat: add theme state to app store"
```

### Task 3: Bootstrap Theme Sync in App Root

**Files:**
- Modify: `frontend/src/App.vue`
- Modify: `tests/test_frontend_ui_structure.py`
- Test: `frontend/src/lib/themeMode.test.js`

- [ ] **Step 1: Write the failing structure test**

```python
def test_app_bootstraps_theme_mode_sync(self):
    app_text = (ROOT / "frontend/src/App.vue").read_text(encoding="utf-8")

    self.assertIn("hydrateThemePreference", app_text)
    self.assertIn("applyResolvedThemeToDocument", app_text)
    self.assertIn("watchSystemTheme", app_text)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
timeout 60s python3 -m unittest tests.test_frontend_ui_structure.FrontendUIStructureTests.test_app_bootstraps_theme_mode_sync -q
```

Expected: FAIL because App root does not contain the new theme bootstrap logic yet.

- [ ] **Step 3: Wire App root to theme runtime**

```vue
<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { useAppStore } from './stores/app.js'
import {
  applyResolvedThemeToDocument,
  readStoredThemePreference,
  watchSystemTheme,
} from './lib/themeMode.js'

const appStore = useAppStore()
let teardownThemeWatch = null

function syncTheme(systemPrefersDark) {
  appStore.syncResolvedTheme(systemPrefersDark)
  applyResolvedThemeToDocument(document.documentElement, appStore.resolvedTheme)
}

onMounted(() => {
  const initialPreference = readStoredThemePreference(window.localStorage)
  appStore.hydrateThemePreference(initialPreference, window.matchMedia('(prefers-color-scheme: dark)').matches)
  applyResolvedThemeToDocument(document.documentElement, appStore.resolvedTheme)
  const systemTheme = watchSystemTheme(window, (matches) => {
    if (appStore.themePreference === 'system') {
      syncTheme(matches)
    }
  })
  teardownThemeWatch = systemTheme.dispose
})

onUnmounted(() => {
  teardownThemeWatch?.()
})
</script>
```

- [ ] **Step 4: Add a runtime test for media-query listener cleanup**

```js
test('watchSystemTheme returns a dispose function that unregisters the listener', () => {
  let removed = false
  const query = {
    matches: true,
    addEventListener(_name, handler) {
      this.handler = handler
    },
    removeEventListener(_name, handler) {
      removed = this.handler === handler
    },
  }

  const watcher = watchSystemTheme({ matchMedia: () => query }, () => {})
  watcher.dispose()

  assert.equal(removed, true)
})
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
npm test -- frontend/src/lib/themeMode.test.js
timeout 60s python3 -m unittest tests.test_frontend_ui_structure.FrontendUIStructureTests.test_app_bootstraps_theme_mode_sync -q
```

Expected: PASS for the new runtime cleanup test and the new structure assertion.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/App.vue frontend/src/lib/themeMode.test.js tests/test_frontend_ui_structure.py
git commit -m "feat: bootstrap theme sync in app root"
```

### Task 4: Introduce Dual Global Theme Tokens

**Files:**
- Modify: `frontend/src/style.css`
- Modify: `tests/test_frontend_ui_structure.py`

- [ ] **Step 1: Write the failing structure test for light theme tokens**

```python
def test_global_styles_define_dark_and_light_theme_token_roots(self):
    style_text = (ROOT / "frontend/src/style.css").read_text(encoding="utf-8")

    self.assertIn(":root[data-theme='dark']", style_text)
    self.assertIn(":root[data-theme='light']", style_text)
    self.assertIn("--app-body-background", style_text)
    self.assertIn("--state-ok-bg", style_text)
    self.assertIn("--selection-bg", style_text)
    self.assertIn("--scrollbar-thumb", style_text)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
timeout 60s python3 -m unittest tests.test_frontend_ui_structure.FrontendUIStructureTests.test_global_styles_define_dark_and_light_theme_token_roots -q
```

Expected: FAIL because the current stylesheet only has a dark default root.

- [ ] **Step 3: Split the current root into explicit dark and light theme roots**

```css
:root {
  --font-ui: "Inter", "SF Pro Display", "Segoe UI", "PingFang SC", "Noto Sans SC", sans-serif;
  --radius-lg: 20px;
  --radius-md: 16px;
  --radius-sm: 12px;
  --ease-expo: cubic-bezier(0.16, 1, 0.3, 1);
}

:root[data-theme='dark'] {
  color-scheme: dark;
  --background-deep: #09101d;
  --background-base: #10192d;
  --text-primary: #edeef7;
  --border-color: rgba(184, 197, 236, 0.12);
  --state-ok-bg: rgba(94, 106, 210, 0.14);
  --state-ok-border: rgba(94, 106, 210, 0.3);
  --state-ok-text: #dbe0ff;
  --state-warning-bg: rgba(244, 185, 93, 0.14);
  --state-warning-border: rgba(244, 185, 93, 0.22);
  --state-warning-text: #f7d79d;
  --state-danger-bg: rgba(255, 120, 148, 0.14);
  --state-danger-border: rgba(255, 120, 148, 0.22);
  --state-danger-text: #ffd2de;
  --auth-hero-title-gradient: linear-gradient(180deg, #ffffff 0%, rgba(237, 238, 247, 0.72) 100%);
  --app-body-background: radial-gradient(ellipse at top, #2f4577 0%, #1a2746 24%, #10192d 58%, #0a111e 100%);
}

:root[data-theme='light'] {
  color-scheme: light;
  --background-deep: #eef3fb;
  --background-base: #f5f7fb;
  --text-primary: #182033;
  --border-color: rgba(24, 32, 51, 0.12);
  --state-ok-bg: rgba(94, 106, 210, 0.1);
  --state-ok-border: rgba(94, 106, 210, 0.18);
  --state-ok-text: #3140a7;
  --state-warning-bg: rgba(244, 185, 93, 0.14);
  --state-warning-border: rgba(244, 185, 93, 0.2);
  --state-warning-text: #9a6800;
  --state-danger-bg: rgba(255, 120, 148, 0.12);
  --state-danger-border: rgba(255, 120, 148, 0.18);
  --state-danger-text: #b63f63;
  --auth-hero-title-gradient: linear-gradient(180deg, #162033 0%, rgba(22, 32, 51, 0.62) 100%);
  --app-body-background: radial-gradient(ellipse at top, #f9fcff 0%, #eef3fb 38%, #e7edf7 100%);
}
```

- [ ] **Step 4: Replace hardcoded body/selection/scrollbar colors with theme tokens**

```css
body {
  background: var(--app-body-background), var(--background-deep);
  color: var(--text-primary);
}

::selection {
  background: var(--selection-bg);
  color: var(--text-primary);
}

::-webkit-scrollbar-thumb {
  background: var(--scrollbar-thumb);
}
```

- [ ] **Step 5: Run test to verify it passes**

Run:

```bash
timeout 60s python3 -m unittest tests.test_frontend_ui_structure.FrontendUIStructureTests.test_global_styles_define_dark_and_light_theme_token_roots -q
```

Expected: PASS with both explicit theme roots and background tokens present.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/style.css tests/test_frontend_ui_structure.py
git commit -m "feat: add dual global theme tokens"
```

### Task 5: Build and Integrate the Theme Switch UI

**Files:**
- Create: `frontend/src/components/app/ThemeModeSwitch.vue`
- Modify: `frontend/src/components/app/AppPrimarySidebar.vue`
- Modify: `frontend/src/views/ConsoleShell.vue`
- Modify: `frontend/src/composables/useConsoleShell.js`
- Modify: `tests/test_frontend_ui_structure.py`

- [ ] **Step 1: Write the failing structure test**

```python
def test_console_shell_uses_theme_mode_switch_in_sidebar_and_mobile_actions(self):
    sidebar_text = (ROOT / "frontend/src/components/app/AppPrimarySidebar.vue").read_text(encoding="utf-8")
    console_text = (ROOT / "frontend/src/views/ConsoleShell.vue").read_text(encoding="utf-8")

    self.assertTrue((ROOT / "frontend/src/components/app/ThemeModeSwitch.vue").exists())
    self.assertIn("ThemeModeSwitch", sidebar_text)
    self.assertIn("theme-preference", sidebar_text)
    self.assertIn("ThemeModeSwitch", console_text)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
timeout 60s python3 -m unittest tests.test_frontend_ui_structure.FrontendUIStructureTests.test_console_shell_uses_theme_mode_switch_in_sidebar_and_mobile_actions -q
```

Expected: FAIL because the component and wiring do not exist.

- [ ] **Step 3: Create the reusable switch component**

```vue
<script setup>
const THEME_OPTIONS = Object.freeze([
  { value: 'system', label: '系统', icon: '系' },
  { value: 'dark', label: '深色', icon: '深' },
  { value: 'light', label: '亮色', icon: '亮' },
])

const props = defineProps({
  preference: { type: String, required: true },
  resolvedTheme: { type: String, required: true },
  collapsed: { type: Boolean, default: false },
  compact: { type: Boolean, default: false },
})

const emit = defineEmits(['update:preference'])
</script>
```

- [ ] **Step 4: Integrate the switch into the sidebar footer and mobile action area**

```vue
<ThemeModeSwitch
  :preference="shell.themePreference"
  :resolved-theme="shell.resolvedTheme"
  :collapsed="shell.sidebarCollapsed"
  @update:preference="shell.setThemePreference"
/>
```

```vue
<ThemeModeSwitch
  compact
  :preference="shell.themePreference"
  :resolved-theme="shell.resolvedTheme"
  @update:preference="shell.setThemePreference"
/>
```

- [ ] **Step 5: Extend `useConsoleShell.js` to proxy theme state from the store**

```js
const themePreference = computed(() => store.themePreference)
const resolvedTheme = computed(() => store.resolvedTheme)

function setThemePreference(nextPreference) {
  store.setThemePreference(
    nextPreference,
    window.matchMedia('(prefers-color-scheme: dark)').matches,
  )
}
```

- [ ] **Step 6: Run test to verify it passes**

Run:

```bash
timeout 60s python3 -m unittest tests.test_frontend_ui_structure.FrontendUIStructureTests.test_console_shell_uses_theme_mode_switch_in_sidebar_and_mobile_actions -q
```

Expected: PASS and new component path exists.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/app/ThemeModeSwitch.vue frontend/src/components/app/AppPrimarySidebar.vue frontend/src/views/ConsoleShell.vue frontend/src/composables/useConsoleShell.js tests/test_frontend_ui_structure.py
git commit -m "feat: add shell theme switch"
```

### Task 6: Remap Shell and Import Workspace Variables to Semantic Tokens

**Files:**
- Modify: `frontend/src/views/ConsoleShell.vue`
- Modify: `frontend/src/components/app/SidebarBrandCard.vue`
- Modify: `frontend/src/components/app/SidebarNavRail.vue`
- Modify: `frontend/src/views/ImportWorkspace.vue`

- [ ] **Step 1: Write the failing structure test for semantic shell mappings**

```python
def test_shell_and_import_workspaces_map_local_theme_tokens_to_semantic_tokens(self):
    console_text = (ROOT / "frontend/src/views/ConsoleShell.vue").read_text(encoding="utf-8")
    import_text = (ROOT / "frontend/src/views/ImportWorkspace.vue").read_text(encoding="utf-8")

    self.assertIn("--console-text: var(--text-primary);", console_text)
    self.assertIn("--console-panel: var(--bg-card);", console_text)
    self.assertIn("--import-text: var(--text-primary);", import_text)
    self.assertIn("--import-panel-bg: var(--bg-card);", import_text)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
timeout 60s python3 -m unittest tests.test_frontend_ui_structure.FrontendUIStructureTests.test_shell_and_import_workspaces_map_local_theme_tokens_to_semantic_tokens -q
```

Expected: FAIL because both files still contain hardcoded deep-dark values.

- [ ] **Step 3: Replace hardcoded console shell tokens with semantic mappings**

```css
.app-shell {
  --console-bg: var(--bg-base);
  --console-shell: var(--bg-primary);
  --console-panel: var(--bg-card);
  --console-panel-hover: var(--bg-card-hover);
  --console-surface: var(--bg-surface);
  --console-border: var(--border-color);
  --console-text: var(--text-primary);
  --console-text-secondary: var(--text-secondary);
  --console-text-muted: var(--text-muted);
  --console-accent: var(--accent-primary);
}
```

- [ ] **Step 4: Replace hardcoded import workspace tokens with semantic mappings**

```css
.import-prep-layout {
  --import-page-bg: var(--bg-base);
  --import-panel-bg: var(--bg-card);
  --import-panel-bg-hover: var(--bg-card-hover);
  --import-surface-bg: var(--bg-primary);
  --import-surface-alt: var(--bg-secondary);
  --import-surface-soft: var(--bg-surface);
  --import-border: var(--border-color);
  --import-border-strong: var(--border-strong);
  --import-text: var(--text-primary);
  --import-text-secondary: var(--text-secondary);
  --import-text-muted: var(--text-muted);
  --import-accent: var(--accent-primary);
}
```

- [ ] **Step 5: Sweep sidebar subcomponents for hardcoded deep-dark backgrounds**

```css
.app-primary-sidebar {
  background: var(--console-panel);
}

.app-sidebar-brand-card {
  border-color: var(--border-color);
  background: var(--bg-surface);
}

.app-primary-nav__item {
  border-color: var(--border-color);
  background: var(--bg-surface);
}
```

- [ ] **Step 6: Run test to verify it passes**

Run:

```bash
timeout 60s python3 -m unittest tests.test_frontend_ui_structure.FrontendUIStructureTests.test_shell_and_import_workspaces_map_local_theme_tokens_to_semantic_tokens -q
```

Expected: PASS and light theme can reach both shells through shared semantic tokens.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/views/ConsoleShell.vue frontend/src/components/app/SidebarBrandCard.vue frontend/src/components/app/SidebarNavRail.vue frontend/src/views/ImportWorkspace.vue tests/test_frontend_ui_structure.py
git commit -m "feat: remap shell theme tokens"
```

### Task 7: Adapt Auth and Key Top-Level Pages for Light Theme Readability

**Files:**
- Modify: `frontend/src/views/LoginView.vue`
- Modify: `frontend/src/views/ChangePasswordView.vue`
- Modify: `frontend/src/views/Dashboard.vue`
- Modify: `frontend/src/views/GovernanceLayout.vue`
- Modify: `frontend/src/views/EnergyOptimization.vue`
- Modify: `frontend/src/views/MonitorCenter.vue`
- Modify: `frontend/src/views/AIAssistant.vue`
- Modify: `frontend/src/views/AlertCenter.vue`
- Modify: `tests/test_frontend_ui_structure.py`

- [ ] **Step 1: Write the failing structure test for theme-aware auth/page visuals**

```python
def test_auth_and_primary_views_use_theme_aware_surface_variables(self):
    login_text = (ROOT / "frontend/src/views/LoginView.vue").read_text(encoding="utf-8")
    change_password_text = (ROOT / "frontend/src/views/ChangePasswordView.vue").read_text(encoding="utf-8")
    dashboard_text = (ROOT / "frontend/src/views/Dashboard.vue").read_text(encoding="utf-8")
    governance_text = (ROOT / "frontend/src/views/GovernanceLayout.vue").read_text(encoding="utf-8")
    alert_text = (ROOT / "frontend/src/views/AlertCenter.vue").read_text(encoding="utf-8")
    monitor_text = (ROOT / "frontend/src/views/MonitorCenter.vue").read_text(encoding="utf-8")
    energy_text = (ROOT / "frontend/src/views/EnergyOptimization.vue").read_text(encoding="utf-8")
    ai_text = (ROOT / "frontend/src/views/AIAssistant.vue").read_text(encoding="utf-8")

    self.assertIn("var(--auth-hero-title-gradient", login_text)
    self.assertIn("var(--auth-hero-title-gradient", change_password_text)
    self.assertNotIn("background: linear-gradient(180deg, #ffffff 0%", login_text)
    self.assertNotIn("background: linear-gradient(180deg, #ffffff 0%", change_password_text)
    self.assertIn("var(--state-ok-bg)", dashboard_text)
    self.assertIn("var(--state-ok-bg)", governance_text)
    self.assertIn("const severityConfig = computed(() => ({", alert_text)
    self.assertIn("const monitorPalette = computed(() => ({", monitor_text)
    self.assertIn("const energyPalette = computed(() => ({", energy_text)
    self.assertIn("var(--state-warning-bg)", ai_text)
    self.assertIn("var(--state-danger-bg)", ai_text)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
timeout 60s python3 -m unittest tests.test_frontend_ui_structure.FrontendUIStructureTests.test_auth_and_primary_views_use_theme_aware_surface_variables -q
```

Expected: FAIL because auth pages still use hardcoded white gradient text and other files still assume dark-only surfaces.

- [ ] **Step 3: Add theme-aware auth gradients and surfaces**

```css
.auth-hero__title {
  background: var(--auth-hero-title-gradient);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.auth-hero__item {
  border: 1px solid var(--border-color);
  background: var(--bg-surface);
}
```

- [ ] **Step 4: Replace hardcoded dashboard, governance, and AI state surfaces with semantic state tokens**

```css
.dashboard-summary__status--ok {
  color: var(--state-ok-text);
  border-color: var(--state-ok-border);
  background: var(--state-ok-bg);
}

.dashboard-summary__status--warning,
.notice--warning,
.ai-notice {
  color: var(--state-warning-text);
  border-color: var(--state-warning-border);
  background: var(--state-warning-bg);
}

.dashboard-summary__status--critical,
.notice--critical,
.ai-feedback--error {
  color: var(--state-danger-text);
  border-color: var(--state-danger-border);
  background: var(--state-danger-bg);
}

.notice--ok,
.ai-feedback--success {
  color: var(--state-ok-text);
  border-color: var(--state-ok-border);
  background: var(--state-ok-bg);
}
```

- [ ] **Step 5: Make alert severity config and chart palettes derive from the active theme**

```js
function readThemeVar(name, fallback) {
  if (typeof window === 'undefined') return fallback
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return value || fallback
}

const severityConfig = computed(() => ({
  critical: {
    bg: readThemeVar('--state-danger-bg', 'rgba(255, 120, 148, 0.14)'),
    border: readThemeVar('--state-danger-border', 'rgba(255, 120, 148, 0.22)'),
    color: readThemeVar('--accent-danger', '#FF6F96'),
    icon: '⚠',
    label: '严重',
  },
  warning: {
    bg: readThemeVar('--state-warning-bg', 'rgba(244, 185, 93, 0.14)'),
    border: readThemeVar('--state-warning-border', 'rgba(244, 185, 93, 0.22)'),
    color: readThemeVar('--accent-warning', '#F4B95D'),
    icon: '△',
    label: '警告',
  },
}))
```

```js
const store = useAppStore()

const monitorPalette = computed(() => ({
  primary: readThemeVar('--accent-primary', '#7F8EFF'),
  secondary: readThemeVar('--accent-tertiary', '#6EB8FF'),
  warning: readThemeVar('--accent-warning', '#F4B95D'),
  danger: readThemeVar('--accent-danger', '#FF6F96'),
  text: readThemeVar('--text-primary', '#EDEEF7'),
  textSecondary: readThemeVar('--text-secondary', '#C6CEE1'),
  textMuted: readThemeVar('--text-tertiary', '#9EA8C0'),
  line: readThemeVar('--border-color', 'rgba(184, 197, 236, 0.12)'),
  border: readThemeVar('--border-strong', 'rgba(127, 142, 255, 0.22)'),
  panel: readThemeVar('--bg-strong', 'rgba(18, 26, 46, 0.96)'),
  inactive: readThemeVar('--text-muted', '#7380A0'),
}))
```

```js
const energyPalette = computed(() => ({
  primary: readThemeVar('--accent-primary', '#7F8EFF'),
  secondary: readThemeVar('--accent-secondary', '#97A5FF'),
  tertiary: readThemeVar('--accent-tertiary', '#6EB8FF'),
  warning: readThemeVar('--accent-warning', '#F4B95D'),
  danger: readThemeVar('--accent-danger', '#FF6F96'),
  text: readThemeVar('--text-primary', '#EDEEF7'),
  textSecondary: readThemeVar('--text-secondary', '#C6CEE1'),
  textMuted: readThemeVar('--text-tertiary', '#9EA8C0'),
  border: readThemeVar('--border-color', 'rgba(184, 197, 236, 0.12)'),
  panel: readThemeVar('--bg-strong', 'rgba(18, 26, 46, 0.96)'),
}))
```

- [ ] **Step 6: Run test to verify it passes**

Run:

```bash
timeout 60s python3 -m unittest tests.test_frontend_ui_structure.FrontendUIStructureTests.test_auth_and_primary_views_use_theme_aware_surface_variables -q
```

Expected: PASS and auth/title gradients are token-driven.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/views/LoginView.vue frontend/src/views/ChangePasswordView.vue frontend/src/views/Dashboard.vue frontend/src/views/GovernanceLayout.vue frontend/src/views/EnergyOptimization.vue frontend/src/views/MonitorCenter.vue frontend/src/views/AIAssistant.vue frontend/src/views/AlertCenter.vue tests/test_frontend_ui_structure.py
git commit -m "feat: adapt auth and key views for light theme"
```

### Task 8: Full Verification and Cleanup

**Files:**
- Verify only unless a failing test reveals a missing implementation detail.

- [ ] **Step 1: Run focused frontend unit tests**

Run:

```bash
npm test -- frontend/src/lib/themeMode.test.js frontend/src/stores/app.test.js
```

Expected: PASS with all theme runtime and store tests green.

- [ ] **Step 2: Run structural regression suite**

Run:

```bash
timeout 60s python3 -m unittest tests.test_frontend_ui_structure tests.test_shell_header_pruning_structure tests.test_page_primary_content_layout_structure -q
```

Expected: PASS with zero failures.

- [ ] **Step 3: Run Vue SFC parse checks for touched view/components**

Run:

```bash
node --input-type=module -e "import { readFileSync } from 'node:fs'; import { parse } from './frontend/node_modules/@vue/compiler-sfc/dist/compiler-sfc.cjs.js'; const files = ['frontend/src/components/app/ThemeModeSwitch.vue','frontend/src/components/app/AppPrimarySidebar.vue','frontend/src/views/ConsoleShell.vue','frontend/src/views/LoginView.vue','frontend/src/views/ChangePasswordView.vue','frontend/src/views/ImportWorkspace.vue']; for (const file of files) { const result = parse(readFileSync(file, 'utf8')); if (result.errors.length) { console.error(file, result.errors); process.exit(1); } } console.log('ok');"
```

Expected: `ok`

- [ ] **Step 4: Verify dirty-worktree safety before final handoff**

Run:

```bash
git status --short
```

Expected: Only intended theme-related files remain changed; unrelated user changes are untouched.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/themeMode.js frontend/src/lib/themeMode.test.js frontend/src/components/app/ThemeModeSwitch.vue frontend/src/stores/app.js frontend/src/stores/app.test.js frontend/src/App.vue frontend/src/style.css frontend/src/views/ConsoleShell.vue frontend/src/components/app/AppPrimarySidebar.vue frontend/src/components/app/SidebarBrandCard.vue frontend/src/components/app/SidebarNavRail.vue frontend/src/views/ImportWorkspace.vue frontend/src/views/LoginView.vue frontend/src/views/ChangePasswordView.vue frontend/src/views/Dashboard.vue frontend/src/views/GovernanceLayout.vue frontend/src/views/EnergyOptimization.vue frontend/src/views/MonitorCenter.vue frontend/src/views/AIAssistant.vue frontend/src/views/AlertCenter.vue tests/test_frontend_ui_structure.py
git commit -m "feat: add system light dark theme switching"
```

## Spec Coverage Self-Review

Spec requirements and matching tasks:

- Global `system / dark / light` preference: Task 1, Task 2, Task 3
- Root `data-theme` and `color-scheme` sync: Task 1, Task 3, Task 4
- Dual dark/light token system: Task 4
- Shell/local token remapping: Task 6
- Sidebar theme switch, collapsed mode, mobile entry: Task 5
- Auth/import/six primary page compatibility: Task 6, Task 7
- Validation without relying on `vite build`: Task 8

No uncovered spec sections remain.

## Placeholder Scan Self-Review

Checked for:

- `TODO`
- `TBD`
- “similar to task”
- vague “handle appropriately” wording without file targets

Resolved outcome:

- All tasks include explicit file paths, commands, and code snippets.
- The only conditional edits are limited to `ImportPrepSidebar.vue` and `ImportPrepWorkbench.vue`, and both are named explicitly with the condition that they only change if shell token remapping exposes contrast regressions.

## Type and Naming Consistency Self-Review

Confirmed consistent names across tasks:

- `themePreference`
- `resolvedTheme`
- `hydrateThemePreference`
- `setThemePreference`
- `syncResolvedTheme`
- `ThemeModeSwitch`
- `applyResolvedThemeToDocument`
- `watchSystemTheme`

No naming drift detected between runtime, store, App bootstrap, or structural tests.

# Import Preparation Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `/import` 重构成“左侧准备态摘要栏 + 右侧分阶段工作台”的准备页面，并用结构测试锁住新的布局边界。

**Architecture:** 以 `ImportWorkspace.vue` 为状态宿主，把当前平铺的 `ImportSourcePanel / ImportHardwareSummary / ImportGpuGrid` 重新组织进 `连接来源 / 硬件概览 / 选卡导入` 三个阶段组件。新增左侧摘要栏和右侧工作台骨架组件，使顶部 tab、内容滚动区、底部提交区完全解耦，避免任何一个区块高度变化牵连整页。

**Tech Stack:** Vue 3 `<script setup>`、现有 Pinia store 和 import API、Python `unittest` 结构测试、Vite build。

---

## File Map

**Create:**
- `frontend/src/components/import/ImportPrepSidebar.vue`
  Purpose: render the fixed left summary rail for brand, connection summary, selected GPU count, and scope note.
- `frontend/src/components/import/ImportPrepWorkbench.vue`
  Purpose: render the right workbench shell with tab header, scrollable body, and isolated footer action bar.
- `frontend/src/components/import/ImportPrepTabs.vue`
  Purpose: render the top-level stage tabs for `连接来源 / 硬件概览 / 选卡导入`.
- `frontend/src/components/import/ImportConnectionStage.vue`
  Purpose: host the source mode switch, source form, scan action card, and connection-side facts.
- `frontend/src/components/import/ImportHardwareStage.vue`
  Purpose: host the hardware summary bar and read-only GPU overview with `卡片视图 / 摘要视图`.
- `frontend/src/components/import/ImportSelectionStage.vue`
  Purpose: host the selection toolbar, `全部候选 / 已选清单` toggle, and scoped `ImportGpuGrid`.

**Modify:**
- `frontend/src/views/ImportWorkspace.vue`
  Purpose: keep data fetching and submit behavior, add active-stage orchestration, and replace the flat page template with the new workbench shell.
- `frontend/src/components/import/ImportSourcePanel.vue`
  Purpose: shrink to pure source-form responsibility so the stage shell owns mode switching, scan feedback, and action controls.
- `tests/test_import_layer_structure.py`
  Purpose: lock the new import workbench shell, stage decomposition, no-flattening rule, and independent scroll/footer regions.

**Verify:**
- `tests/test_frontend_ui_structure.py`
  Purpose: ensure the broader app shell still passes after the import workbench restructuring.

---

### Task 1: Lock The New Import Workbench Structure With Red Tests

**Files:**
- Modify: `tests/test_import_layer_structure.py`
- Test: `tests/test_import_layer_structure.py`

- [ ] **Step 1: Add failing structure tests for the new shell and stage decomposition**

Append these tests to `tests/test_import_layer_structure.py`:

```python
    def test_import_view_uses_sidebar_and_workbench_shell(self):
        text = (ROOT / "frontend/src/views/ImportWorkspace.vue").read_text(encoding="utf-8")

        self.assertIn("ImportPrepSidebar", text)
        self.assertIn("ImportPrepWorkbench", text)
        self.assertIn("import-prep-layout", text)

    def test_import_stage_components_and_tabs_exist(self):
        for rel in [
            "frontend/src/components/import/ImportPrepSidebar.vue",
            "frontend/src/components/import/ImportPrepWorkbench.vue",
            "frontend/src/components/import/ImportPrepTabs.vue",
            "frontend/src/components/import/ImportConnectionStage.vue",
            "frontend/src/components/import/ImportHardwareStage.vue",
            "frontend/src/components/import/ImportSelectionStage.vue",
        ]:
            self.assertTrue((ROOT / rel).exists(), rel)

        workbench_text = (ROOT / "frontend/src/components/import/ImportPrepTabs.vue").read_text(encoding="utf-8")
        self.assertIn("连接来源", workbench_text)
        self.assertIn("硬件概览", workbench_text)
        self.assertIn("选卡导入", workbench_text)

    def test_import_view_recomposes_flat_components_into_stage_components(self):
        text = (ROOT / "frontend/src/views/ImportWorkspace.vue").read_text(encoding="utf-8")

        self.assertIn("ImportConnectionStage", text)
        self.assertIn("ImportHardwareStage", text)
        self.assertIn("ImportSelectionStage", text)
        self.assertNotIn("<ImportSourcePanel", text)
        self.assertNotIn("<ImportHardwareSummary", text)
        self.assertNotIn("<ImportGpuGrid", text)

    def test_import_workbench_keeps_scroll_body_and_footer_isolated(self):
        text = (ROOT / "frontend/src/components/import/ImportPrepWorkbench.vue").read_text(encoding="utf-8")

        self.assertIn("import-prep-workbench__body", text)
        self.assertIn("import-prep-workbench__footer", text)
        self.assertIn("grid-template-rows: auto minmax(0, 1fr) auto;", text)
        self.assertIn("overflow-y: auto", text)

    def test_import_workbench_files_do_not_hide_copy_with_ellipsis(self):
        for rel in [
            "frontend/src/views/ImportWorkspace.vue",
            "frontend/src/components/import/ImportPrepSidebar.vue",
            "frontend/src/components/import/ImportPrepWorkbench.vue",
            "frontend/src/components/import/ImportConnectionStage.vue",
            "frontend/src/components/import/ImportHardwareStage.vue",
            "frontend/src/components/import/ImportSelectionStage.vue",
        ]:
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertNotIn("text-overflow: ellipsis", text, rel)
```

- [ ] **Step 2: Run the import structure tests and verify they fail**

Run:

```bash
timeout 60s cmd.exe /c ".venv\Scripts\python.exe -m unittest tests.test_import_layer_structure -v"
```

Expected:

- FAIL because the new shell and stage component files do not exist yet
- FAIL because `ImportWorkspace.vue` still renders `ImportSourcePanel / ImportHardwareSummary / ImportGpuGrid` directly

- [ ] **Step 3: Commit the red tests**

```bash
git add tests/test_import_layer_structure.py
git commit -m "test: define import workbench structure"
```

---

### Task 2: Build The Sidebar And Workbench Shell

**Files:**
- Create: `frontend/src/components/import/ImportPrepSidebar.vue`
- Create: `frontend/src/components/import/ImportPrepWorkbench.vue`
- Create: `frontend/src/components/import/ImportPrepTabs.vue`
- Create: `frontend/src/components/import/ImportConnectionStage.vue`
- Create: `frontend/src/components/import/ImportHardwareStage.vue`
- Create: `frontend/src/components/import/ImportSelectionStage.vue`
- Modify: `frontend/src/views/ImportWorkspace.vue`
- Test: `tests/test_import_layer_structure.py`

- [ ] **Step 1: Add the left-summary sidebar component**

Create `frontend/src/components/import/ImportPrepSidebar.vue`:

```vue
<script setup>
const props = defineProps({
  title: { type: String, required: true },
  description: { type: String, required: true },
  connectionSummary: { type: String, required: true },
  selectedSummary: { type: String, required: true },
  scopeSummary: { type: String, required: true },
  note: { type: String, required: true },
})
</script>

<template>
  <aside class="import-prep-sidebar tech-card">
    <div class="import-prep-sidebar__brand">
      <img class="import-prep-sidebar__logo" src="/logo.svg" alt="AI-DataCenter logo" />
      <div>
        <div class="import-prep-sidebar__eyebrow">GPU GOVERNANCE CONSOLE</div>
        <h1 class="import-prep-sidebar__title">{{ props.title }}</h1>
      </div>
    </div>
    <p class="import-prep-sidebar__description">{{ props.description }}</p>
    <div class="import-prep-sidebar__facts">
      <article class="import-prep-sidebar__fact">
        <span>当前连接</span>
        <strong>{{ props.connectionSummary }}</strong>
      </article>
      <article class="import-prep-sidebar__fact">
        <span>本次选择</span>
        <strong>{{ props.selectedSummary }}</strong>
      </article>
      <article class="import-prep-sidebar__fact">
        <span>控制范围</span>
        <strong>{{ props.scopeSummary }}</strong>
      </article>
    </div>
    <p class="import-prep-sidebar__note">{{ props.note }}</p>
  </aside>
</template>
```

- [ ] **Step 2: Add the tab strip and workbench shell**

Create `frontend/src/components/import/ImportPrepTabs.vue`:

```vue
<script setup>
const props = defineProps({
  modelValue: { type: String, required: true },
  tabs: { type: Array, required: true },
})
const emit = defineEmits(["update:modelValue"])
</script>

<template>
  <div class="import-prep-tabs">
    <button
      v-for="tab in props.tabs"
      :key="tab.key"
      type="button"
      class="import-prep-tabs__item"
      :class="{ 'import-prep-tabs__item--active': props.modelValue === tab.key }"
      @click="emit('update:modelValue', tab.key)"
    >
      {{ tab.label }}
    </button>
  </div>
</template>
```

Create `frontend/src/components/import/ImportPrepWorkbench.vue`:

```vue
<script setup>
import ImportPrepTabs from './ImportPrepTabs.vue'

const props = defineProps({
  activeTab: { type: String, required: true },
  tabs: { type: Array, required: true },
  footerMessage: { type: String, required: true },
  importBusy: { type: Boolean, required: true },
  importDisabled: { type: Boolean, required: true },
})

const emit = defineEmits(['update:activeTab', 'submit'])
</script>

<template>
  <section class="import-prep-workbench tech-card">
    <ImportPrepTabs
      :model-value="props.activeTab"
      :tabs="props.tabs"
      @update:model-value="emit('update:activeTab', $event)"
    />
    <div class="import-prep-workbench__body">
      <slot />
    </div>
    <div class="import-prep-workbench__footer">
      <div class="import-prep-workbench__status">{{ props.footerMessage }}</div>
      <button
        type="button"
        class="btn-tech btn-tech--primary"
        :disabled="props.importBusy || props.importDisabled"
        @click="emit('submit')"
      >
        {{ props.importBusy ? '导入中...' : '导入并进入控制台' }}
      </button>
    </div>
  </section>
</template>
```

- [ ] **Step 3: Create minimal stage components and wire `ImportWorkspace.vue` into the shell**

Create these minimal stage components first so the shell tests can pass without introducing fake placeholders:

```vue
<!-- frontend/src/components/import/ImportConnectionStage.vue -->
<template>
  <section class="tech-card import-connection-stage">
    <div class="section-title">连接来源</div>
  </section>
</template>
```

```vue
<!-- frontend/src/components/import/ImportHardwareStage.vue -->
<template>
  <section class="tech-card import-hardware-stage">
    <div class="section-title">硬件概览</div>
  </section>
</template>
```

```vue
<!-- frontend/src/components/import/ImportSelectionStage.vue -->
<template>
  <section class="tech-card import-selection-stage">
    <div class="section-title">选卡导入</div>
  </section>
</template>
```

Update `frontend/src/views/ImportWorkspace.vue` so it introduces:

```js
import ImportPrepSidebar from '../components/import/ImportPrepSidebar.vue'
import ImportPrepWorkbench from '../components/import/ImportPrepWorkbench.vue'
import ImportConnectionStage from '../components/import/ImportConnectionStage.vue'
import ImportHardwareStage from '../components/import/ImportHardwareStage.vue'
import ImportSelectionStage from '../components/import/ImportSelectionStage.vue'

const activeStage = ref('source')
const stageTabs = [
  { key: 'source', label: '连接来源' },
  { key: 'hardware', label: '硬件概览' },
  { key: 'selection', label: '选卡导入' },
]

const connectionSummary = computed(() => {
  if (providerType.value === 'ssh_linux') {
    return `SSH Linux / ${sshForm.host || '主机待输入'} / ${scanResult.value?.success ? '已扫描' : '未扫描'}`
  }
  if (providerType.value === 'http_remote') {
    return `远程 Agent / ${agentUrl.value || '地址待输入'} / ${scanResult.value?.success ? '已扫描' : '未扫描'}`
  }
  return `本机 Agent / 本地回环 / ${scanResult.value?.success ? '已扫描' : '未扫描'}`
})
```

And replace the top-level template with:

```vue
<div class="import-prep-layout">
  <ImportPrepSidebar
    :title="heroTitle"
    :description="heroDescription"
    :connection-summary="connectionSummary"
    :selected-summary="importedCountLabel"
    :scope-summary="'控制台只治理本次选中的卡'"
    :note="'先完成扫描，再切换到验机和选卡阶段。'"
  />
  <ImportPrepWorkbench
    v-model:active-tab="activeStage"
    :tabs="stageTabs"
    :footer-message="currentReason || '完成扫描后勾选需要导入的 GPU，再进入控制台。'"
    :import-busy="importBusy"
    :import-disabled="selectedGpuIndexes.length === 0"
    @submit="handleImport"
  >
    <ImportConnectionStage v-if="activeStage === 'source'" />
    <ImportHardwareStage v-else-if="activeStage === 'hardware'" />
    <ImportSelectionStage v-else />
  </ImportPrepWorkbench>
</div>
```

- [ ] **Step 4: Run the import structure tests and verify they pass**

Run:

```bash
timeout 60s cmd.exe /c ".venv\Scripts\python.exe -m unittest tests.test_import_layer_structure -v"
```

Expected:

- PASS for the new shell, tabs, and isolated footer/body assertions

- [ ] **Step 5: Commit the shell**

```bash
git add frontend/src/views/ImportWorkspace.vue frontend/src/components/import/ImportPrepSidebar.vue frontend/src/components/import/ImportPrepWorkbench.vue frontend/src/components/import/ImportPrepTabs.vue frontend/src/components/import/ImportConnectionStage.vue frontend/src/components/import/ImportHardwareStage.vue frontend/src/components/import/ImportSelectionStage.vue tests/test_import_layer_structure.py
git commit -m "feat: add import workbench shell"
```

---

### Task 3: Implement The Connection Stage And Slim ImportSourcePanel

**Files:**
- Modify: `frontend/src/components/import/ImportConnectionStage.vue`
- Modify: `frontend/src/components/import/ImportSourcePanel.vue`
- Modify: `frontend/src/views/ImportWorkspace.vue`
- Test: `tests/test_import_layer_structure.py`

- [ ] **Step 1: Add a failing test for stage composition**

Add this test to `tests/test_import_layer_structure.py`:

```python
    def test_connection_stage_owns_mode_switch_and_scan_status(self):
        stage_text = (ROOT / "frontend/src/components/import/ImportConnectionStage.vue").read_text(encoding="utf-8")
        panel_text = (ROOT / "frontend/src/components/import/ImportSourcePanel.vue").read_text(encoding="utf-8")

        self.assertIn("本机 Agent", stage_text)
        self.assertIn("远程 Agent", stage_text)
        self.assertIn("SSH Linux", stage_text)
        self.assertIn("扫描硬件", stage_text)
        self.assertNotIn("扫描硬件", panel_text)
        self.assertNotIn("已选", panel_text)
```

- [ ] **Step 2: Run the single test and verify it fails**

Run:

```bash
timeout 60s cmd.exe /c ".venv\Scripts\python.exe -m unittest tests.test_import_layer_structure.ImportLayerStructureTests.test_connection_stage_owns_mode_switch_and_scan_status -v"
```

Expected:

- FAIL because `ImportConnectionStage.vue` does not exist and `ImportSourcePanel.vue` still owns scan/status controls

- [ ] **Step 3: Implement the stage and trim the source panel**

Create `frontend/src/components/import/ImportConnectionStage.vue`:

```vue
<script setup>
import ImportSourcePanel from './ImportSourcePanel.vue'

const props = defineProps({
  providerType: { type: String, required: true },
  agentUrl: { type: String, required: true },
  agentLabel: { type: String, required: true },
  host: { type: String, required: true },
  port: { type: Number, required: true },
  username: { type: String, required: true },
  authType: { type: String, required: true },
  password: { type: String, required: true },
  privateKey: { type: String, required: true },
  privateKeyPassphrase: { type: String, required: true },
  sudoEnabled: { type: Boolean, required: true },
  sudoPassword: { type: String, required: true },
  scanBusy: { type: Boolean, required: true },
  feedback: { type: Object, default: null },
  connectionSummary: { type: String, required: true },
})

const emit = defineEmits([
  'update:providerType', 'update:agentUrl', 'update:agentLabel', 'update:host',
  'update:port', 'update:username', 'update:authType', 'update:password',
  'update:privateKey', 'update:privateKeyPassphrase', 'update:sudoEnabled',
  'update:sudoPassword', 'scan',
])
</script>
```

Update `ImportSourcePanel.vue` so it keeps only the form fields and removes:

```vue
<div class="import-source-panel__toggle">...</div>
<div class="import-source-panel__actions">...</div>
<div v-if="props.status" class="import-source-panel__status">...</div>
```

Then replace the source placeholder in `ImportWorkspace.vue` with:

```vue
<ImportConnectionStage
  v-if="activeStage === 'source'"
  v-model:provider-type="providerType"
  v-model:agent-url="agentUrl"
  v-model:agent-label="agentLabel"
  v-model:host="sshForm.host"
  v-model:port="sshForm.port"
  v-model:username="sshForm.username"
  v-model:auth-type="authType"
  v-model:password="sshForm.password"
  v-model:private-key="sshForm.privateKey"
  v-model:private-key-passphrase="sshForm.privateKeyPassphrase"
  v-model:sudo-enabled="sshForm.sudoEnabled"
  v-model:sudo-password="sshForm.sudoPassword"
  :scan-busy="scanBusy"
  :feedback="feedback"
  :connection-summary="connectionSummary"
  @scan="handleScan"
/>
```

- [ ] **Step 4: Run the import structure tests and verify they pass again**

Run:

```bash
timeout 60s cmd.exe /c ".venv\Scripts\python.exe -m unittest tests.test_import_layer_structure -v"
```

Expected:

- PASS with the new stage ownership rule

- [ ] **Step 5: Commit the connection stage**

```bash
git add frontend/src/components/import/ImportConnectionStage.vue frontend/src/components/import/ImportSourcePanel.vue frontend/src/views/ImportWorkspace.vue tests/test_import_layer_structure.py
git commit -m "refactor: isolate import connection stage"
```

---

### Task 4: Implement The Hardware And Selection Stages

**Files:**
- Modify: `frontend/src/components/import/ImportHardwareStage.vue`
- Modify: `frontend/src/components/import/ImportSelectionStage.vue`
- Modify: `frontend/src/views/ImportWorkspace.vue`
- Test: `tests/test_import_layer_structure.py`

- [ ] **Step 1: Add failing tests for hardware and selection stage tabs**

Add these tests to `tests/test_import_layer_structure.py`:

```python
    def test_hardware_stage_exposes_cards_and_summary_views(self):
        text = (ROOT / "frontend/src/components/import/ImportHardwareStage.vue").read_text(encoding="utf-8")
        self.assertIn("卡片视图", text)
        self.assertIn("摘要视图", text)

    def test_selection_stage_exposes_candidate_and_selected_views(self):
        text = (ROOT / "frontend/src/components/import/ImportSelectionStage.vue").read_text(encoding="utf-8")
        self.assertIn("全部候选", text)
        self.assertIn("已选清单", text)
        self.assertIn("ImportGpuGrid", text)
```

- [ ] **Step 2: Run the two tests and verify they fail**

Run:

```bash
timeout 60s cmd.exe /c ".venv\Scripts\python.exe -m unittest tests.test_import_layer_structure.ImportLayerStructureTests.test_hardware_stage_exposes_cards_and_summary_views tests.test_import_layer_structure.ImportLayerStructureTests.test_selection_stage_exposes_candidate_and_selected_views -v"
```

Expected:

- FAIL because the hardware and selection stage files do not exist yet

- [ ] **Step 3: Implement the two stage components and wire them into the workbench**

Create `frontend/src/components/import/ImportHardwareStage.vue` with a local view toggle:

```vue
<script setup>
import { computed, ref } from 'vue'
import ImportHardwareSummary from './ImportHardwareSummary.vue'

const props = defineProps({
  providerType: { type: String, required: true },
  agentLabel: { type: String, required: true },
  agentUrl: { type: String, required: true },
  agentHealth: { type: Object, default: null },
  system: { type: Object, default: null },
  capabilities: { type: Object, default: null },
  gpus: { type: Array, default: () => [] },
})

const activeView = ref('cards')
const busyCount = computed(() => props.gpus.filter((gpu) => Number(gpu.gpu_utilization || 0) > 0).length)
</script>
```

Create `frontend/src/components/import/ImportSelectionStage.vue` with a local source toggle:

```vue
<script setup>
import { computed, ref } from 'vue'
import ImportGpuGrid from './ImportGpuGrid.vue'

const props = defineProps({
  gpus: { type: Array, default: () => [] },
  modelValue: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:modelValue'])
const activeView = ref('all')
const selectedSet = computed(() => new Set(props.modelValue.map((value) => Number(value))))
const visibleGpus = computed(() =>
  activeView.value === 'selected'
    ? props.gpus.filter((gpu) => selectedSet.value.has(Number(gpu.index)))
    : props.gpus
)
</script>
```

Then replace the remaining stage placeholders in `ImportWorkspace.vue` with:

```vue
<ImportHardwareStage
  v-else-if="activeStage === 'hardware'"
  :provider-type="providerType"
  :agent-label="scanResult?.agent_label || agentLabel"
  :agent-url="scanResult?.agent_url || scanResult?.provider?.agent_url || (isSsh ? `ssh://${sshForm.username}@${sshForm.host}:${sshForm.port}` : agentUrl)"
  :agent-health="scanResult?.agent_health || null"
  :system="scanResult?.system || null"
  :capabilities="scanResult?.capabilities || null"
  :gpus="scanResult?.gpus || []"
/>
<ImportSelectionStage
  v-else
  v-model="selectedGpuIndexes"
  :gpus="scanResult?.gpus || []"
/>
```

- [ ] **Step 4: Run the import-layer test file and verify it passes**

Run:

```bash
timeout 60s cmd.exe /c ".venv\Scripts\python.exe -m unittest tests.test_import_layer_structure -v"
```

Expected:

- PASS with the stage decomposition, top-level tabs, secondary view toggles, and no-ellipsis assertions

- [ ] **Step 5: Commit the hardware and selection stages**

```bash
git add frontend/src/components/import/ImportHardwareStage.vue frontend/src/components/import/ImportSelectionStage.vue frontend/src/views/ImportWorkspace.vue tests/test_import_layer_structure.py
git commit -m "feat: add staged import workbench content"
```

---

### Task 5: Run Full Frontend Verification

**Files:**
- Verify: `tests/test_import_layer_structure.py`
- Verify: `tests/test_frontend_ui_structure.py`
- Verify: `frontend/`

- [ ] **Step 1: Run the import-layer structure tests**

Run:

```bash
timeout 60s cmd.exe /c ".venv\Scripts\python.exe -m unittest tests.test_import_layer_structure -v"
```

Expected:

- PASS

- [ ] **Step 2: Run the broader frontend UI structure tests**

Run:

```bash
timeout 60s cmd.exe /c ".venv\Scripts\python.exe -m unittest tests.test_frontend_ui_structure -v"
```

Expected:

- PASS

- [ ] **Step 3: Run the frontend production build**

Run:

```bash
cmd.exe /c "cd /d E:\Code\AI-DataCenter\frontend && npm run build"
```

Expected:

- Vite build succeeds
- Existing chunk-size warning may remain, but build exit code must be `0`

- [ ] **Step 4: Commit the verified work**

```bash
git add frontend/src/views/ImportWorkspace.vue frontend/src/components/import/ImportPrepSidebar.vue frontend/src/components/import/ImportPrepWorkbench.vue frontend/src/components/import/ImportPrepTabs.vue frontend/src/components/import/ImportConnectionStage.vue frontend/src/components/import/ImportHardwareStage.vue frontend/src/components/import/ImportSelectionStage.vue frontend/src/components/import/ImportSourcePanel.vue tests/test_import_layer_structure.py
git commit -m "refactor: redesign import preparation workbench"
```

## Self-Review

- Spec coverage: 覆盖了双栏骨架、三阶段主 tab、左侧准备态摘要、底部独立提交区、阶段组件拆分、无截断断言、独立滚动区。
- Placeholder scan: 计划中没有 `TODO`、`TBD`、`implement later`、`Similar to Task N` 之类占位语。
- Type consistency: 顶层阶段 key 统一为 `source / hardware / selection`；顶层组件名统一为 `ImportPrep*` 与 `Import*Stage`。

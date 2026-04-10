# AI 助手悬浮窗工作台布局 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 AI 助手页面重排为“顶部轻量控制 + 左侧会话卡片 + 右侧聊天卡片”，并把模型配置改成右上角触发的悬浮窗。

**Architecture:** 保持现有 `useAiAssistantWorkbench` / `useAiAssistantRuntimeSession` 业务逻辑不变，只调整前端承载结构。页面层移除中部 `WorkspaceTabs`，新增一个局部弹窗组件承接模型配置，`AgentWorkbench` 改成左右两张独立卡片，`AgentSessionRail` 与 `AgentComposer` 分别负责可识别的会话栏与更突出的输入卡。

**Tech Stack:** Vue 3 `script setup`, Vite, scoped CSS, Python `unittest`

---

## File Structure

- Create: `frontend/src/components/agent/AgentModelConfigDialog.vue`
  - 页面内模型配置悬浮窗，负责遮罩、关闭交互、键盘关闭和内容容器。
- Modify: `frontend/src/views/AIAssistant.vue`
  - 删除 `WorkspaceTabs` 与 `activeTab` 依赖，接入顶部 `模型配置` 按钮、悬浮窗开关和单一工作台主体。
- Modify: `frontend/src/components/agent/AgentWorkbench.vue`
  - 改成左右两张卡片布局，左侧包裹会话卡片，右侧包裹聊天工作区卡片。
- Modify: `frontend/src/components/agent/AgentSessionRail.vue`
  - 增加 `会话栏 / 最近会话` 头部与空状态文案，收窄宽度并强化卡片可识别性。
- Modify: `frontend/src/components/agent/AgentComposer.vue`
  - 增大输入框可用高度，收紧 chips 与按钮布局。
- Modify: `tests/test_frontend_ui_structure.py`
  - 移除 AI 页面必须使用 `WorkspaceTabs` 的断言，改为悬浮窗与双卡布局断言。

## Task 1: Lock New AI Page Structure With Failing Tests

**Files:**
- Modify: `tests/test_frontend_ui_structure.py`

- [ ] **Step 1: Write the failing structure assertions for the new page shell**

Add or replace AI-page-specific assertions so they match the modal layout instead of tabs:

```python
    def test_ai_assistant_uses_workspace_summary_without_workspace_tabs(self):
        text = (ROOT / "frontend/src/views/AIAssistant.vue").read_text(encoding="utf-8")

        self.assertIn("WorkspaceSummary", text)
        self.assertNotIn("WorkspaceTabs", text)
        self.assertNotIn("activeTab", text)
        self.assertIn("模型配置", text)

    def test_ai_assistant_uses_model_config_dialog_and_workbench(self):
        view_text = (ROOT / "frontend/src/views/AIAssistant.vue").read_text(encoding="utf-8")
        dialog_text = (
            ROOT / "frontend/src/components/agent/AgentModelConfigDialog.vue"
        ).read_text(encoding="utf-8")

        self.assertIn("AgentWorkbench", view_text)
        self.assertIn("AgentModelConfigDialog", view_text)
        self.assertIn("showModelConfig", view_text)
        self.assertIn("keydown", dialog_text)
        self.assertIn("AgentModelConfigPane", dialog_text)

    def test_ai_session_rail_has_explicit_heading_and_empty_state_copy(self):
        text = (ROOT / "frontend/src/components/agent/AgentSessionRail.vue").read_text(encoding="utf-8")

        self.assertIn("会话栏", text)
        self.assertIn("最近会话", text)
        self.assertIn("暂无历史会话", text)
```

- [ ] **Step 2: Run the targeted structure test to verify it fails**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m unittest tests.test_frontend_ui_structure -q
```

Expected: FAIL because `AIAssistant.vue` still imports `WorkspaceTabs`, no dialog file exists, and `AgentSessionRail.vue` still has no heading or empty-state copy.

## Task 2: Implement Top-Right Model Config Dialog In AIAssistant

**Files:**
- Create: `frontend/src/components/agent/AgentModelConfigDialog.vue`
- Modify: `frontend/src/views/AIAssistant.vue`

- [ ] **Step 1: Add the dialog component with explicit overlay and close interactions**

Create `frontend/src/components/agent/AgentModelConfigDialog.vue`:

```vue
<script setup>
import { onBeforeUnmount, onMounted } from 'vue'

import AgentModelConfigPane from './AgentModelConfigPane.vue'

const props = defineProps({
  open: { type: Boolean, default: false },
  llmReady: { type: Boolean, default: false },
  llmBusy: { type: Boolean, default: false },
  llmNotice: { type: String, default: '' },
  llmFeedback: { type: Object, default: null },
  llmForm: { type: Object, required: true },
  hasStoredKey: { type: Boolean, default: false },
  savedKeyHint: { type: String, default: '' },
  llmSourceLabel: { type: String, default: '' },
  llmUpdatedAt: { type: String, default: '' },
  canTestLlm: { type: Boolean, default: false },
  canSaveLlm: { type: Boolean, default: false },
})

const emit = defineEmits(['close', 'runTest', 'save'])

function handleKeydown(event) {
  if (!props.open || event.key !== 'Escape') return
  emit('close')
}

onMounted(() => window.addEventListener('keydown', handleKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', handleKeydown))
</script>
```

Use a centered overlay container and render `<AgentModelConfigPane />` inside it only when `open` is true.

- [ ] **Step 2: Run the structure test and verify it still fails for the page shell**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m unittest tests.test_frontend_ui_structure -q
```

Expected: still FAIL because `AIAssistant.vue` still uses `WorkspaceTabs` and has not wired `showModelConfig`.

- [ ] **Step 3: Refactor AIAssistant.vue to a single-page workbench with top-right controls**

In `frontend/src/views/AIAssistant.vue`:

```vue
import { computed, onMounted, ref } from 'vue'

import AgentModelConfigDialog from '../components/agent/AgentModelConfigDialog.vue'
import AgentWorkbench from '../components/agent/AgentWorkbench.vue'
import WorkspaceSummary from '../components/workspace/WorkspaceSummary.vue'
```

Add the dialog state:

```vue
const showModelConfig = ref(false)

const llmStatusLabel = computed(() => (
  llmReady.value ? 'LLM 已就绪' : '规则解析模式'
))
```

Replace the middle `WorkspaceTabs` block with:

```vue
<section class="ai-page__workspace">
  <AgentWorkbench
    :sessions="sessionHistory"
    :active-session-id="activeSessionId"
    :topbar="workbenchView.topbar"
    :thread-items="workbenchView.items"
    :composer-text="composerText"
    :quick-prompts="QUICK_PROMPTS"
    :busy="loading || controlPlanning || controlExecuting"
    @select-session="selectSession"
    @update:composerText="composerText = $event"
    @submit="submitWorkbenchInput"
    @use-prompt="useWorkbenchPrompt"
    @approve="handleApproval(true)"
    @reject="handleApproval(false)"
    @choose-route="resolveRouteConfirm"
  />
</section>
<AgentModelConfigDialog
  :open="showModelConfig"
  :llm-ready="llmReady"
  :llm-busy="llmBusy"
  :llm-notice="llmNotice"
  :llm-feedback="llmFeedback"
  :llm-form="llmForm"
  :has-stored-key="hasStoredKey"
  :saved-key-hint="savedKeyHint"
  :llm-source-label="llmSourceLabel"
  :llm-updated-at="llmUpdatedAt"
  :can-test-llm="canTestLlm"
  :can-save-llm="canSaveLlm"
  @close="showModelConfig = false"
  @run-test="runLlmTest"
  @save="saveLlmConfig"
/>
```

Top-right meta area should include a `模型配置` button that toggles `showModelConfig`.

- [ ] **Step 4: Run the structure test and verify the page shell now passes**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m unittest tests.test_frontend_ui_structure -q
```

Expected: the new `AIAssistant` assertions for removing `WorkspaceTabs`, wiring `showModelConfig`, and mounting `AgentModelConfigDialog` all PASS.

## Task 3: Convert Workbench Into Session Card + Chat Card Layout

**Files:**
- Modify: `frontend/src/components/agent/AgentWorkbench.vue`
- Modify: `frontend/src/components/agent/AgentSessionRail.vue`
- Modify: `frontend/src/components/agent/AgentComposer.vue`

- [ ] **Step 1: Adjust the structure assertions to require the new session-rail copy**

Confirm the rail test checks these strings:

```python
self.assertIn("会话栏", text)
self.assertIn("最近会话", text)
self.assertIn("暂无历史会话", text)
```

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m unittest tests.test_frontend_ui_structure -q
```

Expected: FAIL because current rail still renders only the list buttons.

- [ ] **Step 2: Rebuild AgentSessionRail.vue as a clearly labeled card**

Refactor `frontend/src/components/agent/AgentSessionRail.vue` to render:

```vue
<aside class="agent-session-rail tech-card">
  <header class="agent-session-rail__head">
    <h3>会话栏</h3>
    <p>最近会话</p>
  </header>
  <div v-if="!sessions.length" class="agent-session-rail__empty">
    <strong>暂无历史会话</strong>
    <span>执行或追问后，会在这里沉淀会话记录</span>
  </div>
  <div v-else class="agent-session-rail__list">
    <!-- existing button list -->
  </div>
</aside>
```

Keep each list item compact and keep width-oriented styling in the component.

- [ ] **Step 3: Refactor AgentWorkbench.vue into two wrapped cards**

Change the workbench template to:

```vue
<section class="agent-workbench">
  <div class="agent-workbench__rail-card">
    <AgentSessionRail
      :sessions="sessions"
      :active-session-id="activeSessionId"
      @select="emit('selectSession', $event)"
    />
  </div>
  <div class="agent-workbench__chat-card tech-card">
    <AgentWorkbenchTopbar :model="topbar" />
    <AgentThread
      :items="threadItems"
      @approve="emit('approve', $event)"
      @reject="emit('reject', $event)"
      @choose-route="emit('chooseRoute', $event)"
    />
    <AgentComposer
      :input-text="composerText"
      :quick-prompts="quickPrompts"
      :disabled="busy"
      @update:inputText="emit('update:composerText', $event)"
      @submit="emit('submit')"
      @usePrompt="emit('usePrompt', $event)"
    />
  </div>
</section>
```

Use `grid-template-columns: 216px minmax(0, 1fr);` on desktop to keep the rail narrow.

- [ ] **Step 4: Make AgentComposer more prominent without changing behavior**

Update `frontend/src/components/agent/AgentComposer.vue`:

```css
.agent-composer {
  gap: 10px;
  padding: 16px 18px 18px;
  border: 1px solid var(--border-color);
  border-radius: 20px;
  background: color-mix(in srgb, var(--bg-card) 82%, transparent);
}

.agent-composer__input {
  min-height: 152px;
}
```

Keep the existing emit contract unchanged.

- [ ] **Step 5: Run structure tests to verify the layout now passes**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m unittest tests.test_frontend_ui_structure tests.test_real_data_only_structure -q
```

Expected: PASS

## Task 4: Final Verification

**Files:**
- Modify: `frontend/src/views/AIAssistant.vue`
- Modify: `frontend/src/components/agent/AgentWorkbench.vue`
- Modify: `frontend/src/components/agent/AgentSessionRail.vue`
- Modify: `frontend/src/components/agent/AgentComposer.vue`
- Create: `frontend/src/components/agent/AgentModelConfigDialog.vue`
- Modify: `tests/test_frontend_ui_structure.py`

- [ ] **Step 1: Run the focused frontend regression tests**

Run:

```bash
timeout 60s ./.venv/Scripts/python.exe -m unittest tests.test_frontend_ui_structure tests.test_real_data_only_structure -q
```

Expected: PASS

- [ ] **Step 2: Run the frontend production build**

Run:

```bash
npm --prefix frontend run build
```

Expected: build succeeds with no Vue compile errors and no missing component imports.

- [ ] **Step 3: Commit the layout refactor**

```bash
git add \
  frontend/src/views/AIAssistant.vue \
  frontend/src/components/agent/AgentWorkbench.vue \
  frontend/src/components/agent/AgentSessionRail.vue \
  frontend/src/components/agent/AgentComposer.vue \
  frontend/src/components/agent/AgentModelConfigDialog.vue \
  tests/test_frontend_ui_structure.py \
  docs/superpowers/plans/2026-04-09-ai-assistant-modal-workbench-layout.md
git commit -m "refactor: streamline ai assistant workbench layout"
```

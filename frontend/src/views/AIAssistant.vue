<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AgentModelConfigDialog from '../components/agent/AgentModelConfigDialog.vue'
import AgentWorkbench from '../components/agent/AgentWorkbench.vue'
import WorkspaceSummary from '../components/workspace/WorkspaceSummary.vue'
import { useAiAssistantLlm } from '../composables/useAiAssistantLlm.js'
import { useAiAssistantWorkbench } from '../composables/useAiAssistantWorkbench.js'

const showModelConfig = ref(false)
const workbenchPage = ref('workbench')
const route = useRoute()
const router = useRouter()

const llmState = useAiAssistantLlm()
const {
  llmReady,
  llmBusy,
  llmNotice,
  llmFeedback,
  llmForm,
  hasStoredKey,
  savedKeyHint,
  llmSourceLabel,
  llmUpdatedAt,
  canTestLlm,
  canSaveLlm,
  loadAssistantCapability,
  runLlmTest,
  saveLlmConfig,
} = llmState

const workbenchState = useAiAssistantWorkbench({
  pageState: workbenchPage,
  llmReady,
  llmNotice,
})
const {
  composerText,
  loading,
  controlPermissionMode,
  controlPlanning,
  controlExecuting,
  workbenchView,
  sessionHistory,
  activeSessionId,
  loadSessionHistory,
  submitWorkbenchInput,
  handleApproval,
  selectSession,
  deleteSession,
  startNewSession,
} = workbenchState

const llmStatusLabel = computed(() => (
  llmReady.value ? 'LLM 已就绪' : '规则解析模式'
))

async function consumeWorkbenchDraftFromRoute() {
  const draft = String(route.query.draft || '').trim()
  if (!draft) return

  const autorun = String(route.query.autorun || '') === '1'
  if (autorun) {
    startNewSession()
    await nextTick()
  }

  composerText.value = draft
  await router.replace({
    path: route.path,
    query: {},
  })

  if (autorun) {
    await submitWorkbenchInput(draft)
  }
}

onMounted(async () => {
  await loadAssistantCapability()
  await loadSessionHistory()
  await consumeWorkbenchDraftFromRoute()
})

watch(
  () => [route.query.draft, route.query.autorun],
  async ([draft]) => {
    if (!String(draft || '').trim()) return
    await consumeWorkbenchDraftFromRoute()
  },
)
</script>

<template>
  <div class="ai-page ink-page-shell">
    <WorkspaceSummary title="AI 助手工作台">
      <template #meta>
        <div class="ink-inline-meta ai-page__meta">
          <button
            type="button"
            class="ai-page__model-trigger"
            @click="showModelConfig = true"
          >
            模型配置
          </button>
          <span class="status-badge" :class="llmReady ? 'status-badge--ok' : 'status-badge--warning'">
            {{ llmStatusLabel }}
          </span>
          <div class="ai-mode-switch">
            <button
              type="button"
              class="ai-mode-switch__item"
              :class="{ 'ai-mode-switch__item--active': controlPermissionMode === 'low' }"
              @click="controlPermissionMode = 'low'"
            >
              低权限
            </button>
            <button
              type="button"
              class="ai-mode-switch__item"
              :class="{ 'ai-mode-switch__item--active': controlPermissionMode === 'high' }"
              @click="controlPermissionMode = 'high'"
            >
              高权限
            </button>
          </div>
        </div>
      </template>
    </WorkspaceSummary>

    <section class="ai-page__workspace">
      <AgentWorkbench
        :sessions="sessionHistory"
        :active-session-id="activeSessionId"
        :topbar="workbenchView.topbar"
        :lead-message="workbenchView.leadMessage"
        :interactions="workbenchView.interactions"
        :composer-text="composerText"
        :busy="loading || controlPlanning || controlExecuting"
        @create-session="startNewSession"
        @select-session="selectSession"
        @delete-session="deleteSession"
        @update:composerText="composerText = $event"
        @submit="submitWorkbenchInput"
        @approve="handleApproval(true)"
        @reject="handleApproval(false)"
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
  </div>
</template>

<style scoped>
.ai-page {
  max-width: 1280px;
  margin: 0 auto;
  --ai-warning-surface: var(--state-warning-bg);
  --ai-danger-surface: var(--state-danger-bg);
}

.ai-page__meta {
  flex-wrap: wrap;
}

.ai-page__model-trigger {
  border: 1px solid color-mix(in srgb, var(--accent-color) 38%, var(--border-color));
  border-radius: 999px;
  background: color-mix(in srgb, var(--accent-color) 14%, transparent);
  color: var(--text-primary);
  padding: 9px 16px;
  cursor: pointer;
}

.ai-mode-switch {
  display: inline-flex;
  padding: 3px;
  border: 1px solid var(--border-color);
  border-radius: 999px;
  background: var(--bg-card);
}

.ai-mode-switch__item {
  border: 0;
  background: transparent;
  color: var(--text-secondary);
  padding: 6px 12px;
  border-radius: 999px;
  cursor: pointer;
}

.ai-mode-switch__item--active {
  background: color-mix(in srgb, var(--accent-color) 16%, transparent);
  color: var(--text-primary);
}

.ai-page__workspace {
  margin-top: 18px;
}
</style>

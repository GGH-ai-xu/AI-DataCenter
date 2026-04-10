<script setup>
import { computed, onMounted, provide, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AgentModelConfigDialog from '../components/agent/AgentModelConfigDialog.vue'
import WorkspaceTabs from '../components/workspace/WorkspaceTabs.vue'
import { AI_WORKSPACE_SHELL_CONTEXT_KEY } from '../composables/aiWorkspaceShellContext.js'
import { useAiAssistantLlm } from '../composables/useAiAssistantLlm.js'

defineOptions({ name: 'AIWorkspaceLayout' })

const route = useRoute()
const router = useRouter()
const llmState = useAiAssistantLlm()
const {
  llmBusy,
  llmReady,
  llmNotice,
  llmFeedback,
  llmForm,
  hasStoredKey,
  savedKeyHint,
  llmSourceLabel,
  llmUpdatedAt,
  canTestLlm,
  canSaveLlm,
} = llmState
const showModelConfig = ref(false)
const controlPermissionMode = ref('low')
const graphConnected = ref(false)
const graphStatusLoaded = ref(false)

const AI_WORKSPACE_TABS = Object.freeze([
  { key: 'workbench', label: '智能工作台', desc: '对话与执行' },
  { key: 'graph', label: '图谱工作台', desc: '入图与策略' },
])

const activeTab = computed(() => (
  route.name === 'AIGraphWorkspace' ? 'graph' : 'workbench'
))
const llmStatusLabel = computed(() => (
  llmReady.value ? 'LLM 已就绪' : '规则解析模式'
))
const graphLlmStatusLabel = computed(() => (
  llmReady.value ? 'LLM 已就绪' : 'LLM 未就绪'
))
const graphStatusLabel = computed(() => {
  if (!graphStatusLoaded.value) {
    return '图库状态读取中'
  }
  return graphConnected.value ? '图库在线' : '图库离线'
})
const graphStatusClass = computed(() => (
  graphStatusLoaded.value && graphConnected.value ? 'status-badge--ok' : 'status-badge--warning'
))

function setGraphToolbarStatus(summary = null) {
  graphConnected.value = !!summary?.neo4j_connected
  graphStatusLoaded.value = true
}

function resetGraphToolbarStatus() {
  graphConnected.value = false
  graphStatusLoaded.value = false
}

function switchTab(nextTab) {
  const nextPath = nextTab === 'graph' ? '/ai/graph' : '/ai/workbench'
  if (route.path !== nextPath) {
    void router.push(nextPath)
  }
}

provide(AI_WORKSPACE_SHELL_CONTEXT_KEY, {
  llmState,
  controlPermissionMode,
  setGraphToolbarStatus,
  resetGraphToolbarStatus,
})

onMounted(() => {
  void llmState.loadAssistantCapability()
})
</script>

<template>
  <div class="ai-workspace-layout">
    <div class="workspace-nav-layout">
      <div class="workspace-nav-layout__nav">
        <div class="ai-workspace-layout__toolbar">
          <WorkspaceTabs
            :model-value="activeTab"
            :items="AI_WORKSPACE_TABS"
            compact
            @update:model-value="switchTab"
          />
          <div class="workspace-action-rail__meta ai-workspace-layout__toolbar-actions">
            <template v-if="activeTab === 'workbench'">
              <button
                type="button"
                class="ai-workspace-layout__model-trigger"
                @click="showModelConfig = true"
              >
                模型配置
              </button>
              <span class="status-badge" :class="llmReady ? 'status-badge--ok' : 'status-badge--warning'">
                {{ llmStatusLabel }}
              </span>
              <div class="ai-workspace-mode-switch">
                <button
                  type="button"
                  class="ai-workspace-mode-switch__item"
                  :class="{ 'ai-workspace-mode-switch__item--active': controlPermissionMode === 'low' }"
                  @click="controlPermissionMode = 'low'"
                >
                  低权限
                </button>
                <button
                  type="button"
                  class="ai-workspace-mode-switch__item"
                  :class="{ 'ai-workspace-mode-switch__item--active': controlPermissionMode === 'high' }"
                  @click="controlPermissionMode = 'high'"
                >
                  高权限
                </button>
              </div>
            </template>
            <template v-else>
              <span class="status-badge" :class="graphStatusClass">
                {{ graphStatusLabel }}
              </span>
              <span class="status-badge" :class="llmReady ? 'status-badge--ok' : 'status-badge--warning'">
                {{ graphLlmStatusLabel }}
              </span>
            </template>
          </div>
        </div>
      </div>

      <section class="workspace-nav-layout__content">
        <router-view />
      </section>
    </div>

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
      @run-test="llmState.runLlmTest"
      @save="llmState.saveLlmConfig"
    />
  </div>
</template>

<style scoped>
.ai-workspace-layout {
  max-width: 1280px;
  margin: 0 auto;
}

.ai-workspace-layout__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.ai-workspace-layout__toolbar :deep(.workspace-tabs) {
  flex: 1 1 auto;
  min-width: 0;
}

.ai-workspace-layout__toolbar-actions {
  flex: 0 0 auto;
  min-width: max-content;
}

.ai-workspace-layout__model-trigger {
  border: 1px solid color-mix(in srgb, var(--accent-color) 38%, var(--border-color));
  border-radius: 999px;
  background: color-mix(in srgb, var(--accent-color) 14%, transparent);
  color: var(--text-primary);
  padding: 9px 16px;
  cursor: pointer;
}

.ai-workspace-mode-switch {
  display: inline-flex;
  padding: 3px;
  border: 1px solid var(--border-color);
  border-radius: 999px;
  background: var(--bg-card);
}

.ai-workspace-mode-switch__item {
  border: 0;
  background: transparent;
  color: var(--text-secondary);
  padding: 6px 12px;
  border-radius: 999px;
  cursor: pointer;
}

.ai-workspace-mode-switch__item--active {
  background: color-mix(in srgb, var(--accent-color) 16%, transparent);
  color: var(--text-primary);
}

@media (max-width: 980px) {
  .ai-workspace-layout__toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .ai-workspace-layout__toolbar-actions {
    width: 100%;
    min-width: 0;
    justify-content: flex-start;
  }
}
</style>

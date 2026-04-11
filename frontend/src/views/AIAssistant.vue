<script setup>
import { computed, inject, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AgentWorkbench from '../components/agent/AgentWorkbench.vue'
import WorkspaceSummary from '../components/workspace/WorkspaceSummary.vue'
import { AI_WORKSPACE_SHELL_CONTEXT_KEY } from '../composables/aiWorkspaceShellContext.js'
import { useAiAssistantWorkbench } from '../composables/useAiAssistantWorkbench.js'

const workbenchPage = ref('workbench')
const route = useRoute()
const router = useRouter()
const shellContext = inject(AI_WORKSPACE_SHELL_CONTEXT_KEY, null)

if (!shellContext) {
  throw new Error('AI workspace shell context is unavailable.')
}

const { llmState, controlPermissionMode } = shellContext
const { llmReady, llmNotice } = llmState

const workbenchState = useAiAssistantWorkbench({
  pageState: workbenchPage,
  llmReady,
  llmNotice,
  controlPermissionMode,
})
const {
  composerText,
  loading,
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
const modeBadgeLabel = computed(() => (
  controlPermissionMode.value === 'high' ? '高权限' : '低权限'
))
const llmBadgeLabel = computed(() => (
  llmReady.value ? 'LLM 已就绪' : '规则解析模式'
))
const sessionBadgeLabel = computed(() => (
  activeSessionId.value ? '继续会话' : '新建会话'
))
const summaryDescription = computed(() => (
  llmReady.value
    ? '在同一会话里连续追问、审批与执行，让对话和治理过程保持连贯。'
    : '当前未接入 LLM，将回退为规则解析模式，可先在右上角完成模型配置。'
))
const sessionSummary = computed(() => {
  const sessionCount = sessionHistory.value.length
  if (activeSessionId.value) {
    return `当前正在查看历史会话，已沉淀 ${sessionCount} 个会话记录。`
  }
  if (sessionCount > 0) {
    return `当前处于新会话草稿态，左侧会话栏已保存 ${sessionCount} 个历史会话。`
  }
  return '当前还没有历史会话，发送第一条消息后会自动沉淀会话记录。'
})

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
    <WorkspaceSummary
      title="智能工作台"
      :description="summaryDescription"
    >
      <template #meta>
        <div class="ink-inline-meta">
          <span class="status-badge" :class="llmReady ? 'status-badge--ok' : 'status-badge--warning'">
            {{ llmBadgeLabel }}
          </span>
          <span class="status-badge">{{ modeBadgeLabel }}</span>
          <span class="status-badge status-badge--ok">{{ sessionBadgeLabel }}</span>
        </div>
      </template>
      <div class="ai-page__summary-caption">
        {{ sessionSummary }}
      </div>
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
  </div>
</template>

<style scoped>
.ai-page {
  max-width: 1280px;
  margin: 0 auto;
  display: grid;
  gap: 16px;
  --ai-warning-surface: var(--state-warning-bg);
  --ai-danger-surface: var(--state-danger-bg);
}

.ai-page__summary-caption {
  font-size: 0.92rem;
  line-height: 1.8;
  color: var(--console-text-secondary, var(--text-secondary));
}
</style>

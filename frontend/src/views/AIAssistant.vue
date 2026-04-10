<script setup>
import { inject, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AgentWorkbench from '../components/agent/AgentWorkbench.vue'
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
  --ai-warning-surface: var(--state-warning-bg);
  --ai-danger-surface: var(--state-danger-bg);
}

.ai-page__workspace {
  margin-top: 18px;
}
</style>

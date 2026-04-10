import { computed, ref, watch } from 'vue'

import { resolveWorkbenchDispatchResult } from '../lib/agentWorkbenchDispatch.js'
import { buildAgentWorkbenchThread } from '../lib/agentWorkbenchThread.js'
import { reduceChatStreamEvent } from '../lib/agentChatStreaming.js'
import { parseSseFrames, readResponseTextChunks } from '../lib/sseFrameStream.js'
import { dispatchAiWorkbenchMessage, openAiChatStream } from '../services/api'
import { useAiAssistantRuntimeSession } from './useAiAssistantRuntimeSession.js'

const DEFAULT_INTRO = '你好，我是 AI 治理助手。我可以解释当前 GPU 状态，也可以把自然语言目标转换成可审核、可执行的治理动作。'
const BLOCKED_INTRO = 'AI 助手当前未启用。请先接入并启用 LLM 后再进行问答或执行请求。'
const LIVE_PHASE_LABELS = {
  planning: '计划生成中',
  awaiting_approval: '等待审批',
  executing: '正在执行',
  completed: '执行完成',
  failed: '执行失败',
}

function buildIntroMessage(ready) {
  return {
    id: 'intro',
    role: 'assistant',
    content: ready ? DEFAULT_INTRO : BLOCKED_INTRO,
  }
}

function buildPendingAssistantMessage(id) {
  return { id, role: 'assistant', content: '正在生成回复...' }
}

export function useAiAssistantWorkbench({ pageState, llmReady, llmNotice }) {
  const messages = ref([])
  const composerText = ref('')
  const loading = ref(false)
  const controlPermissionMode = ref('low')
  let messageSequence = 0

  function nextMessageId(prefix = 'msg') {
    messageSequence += 1
    return `${prefix}-${messageSequence}`
  }

  function pushAssistantMessage(content) {
    messages.value.push({ id: nextMessageId('assistant'), role: 'assistant', content })
  }

  const runtime = useAiAssistantRuntimeSession({
    pageState,
    controlPermissionMode,
    onError: pushAssistantMessage,
  })

  const liveProgressText = computed(() => (
    runtime.plannerStreamError.value || runtime.plannerLiveText.value
  ))
  const liveProgressTone = computed(() => (
    runtime.plannerStreamError.value
      ? 'error'
      : (runtime.plannerStreamActive.value ? 'active' : 'idle')
  ))
  const liveProgressLabel = computed(() => (
    runtime.plannerStreamError.value
      ? '流式更新异常'
      : (LIVE_PHASE_LABELS[runtime.plannerLivePhase.value] || '实时进展')
  ))
  const workbenchView = computed(() => {
    const view = buildAgentWorkbenchThread({
      chatMessages: messages.value,
      runtimeSession: runtime.runtimeSession.value,
      runtimeEvents: runtime.runtimeEvents.value,
    })
    return {
      ...view,
      topbar: {
        ...view.topbar,
        liveText: liveProgressText.value,
        liveLabel: liveProgressLabel.value,
        liveTone: liveProgressTone.value,
      },
    }
  })

  function resetThreadState() {
    messages.value = [buildIntroMessage(llmReady.value)]
    composerText.value = ''
    loading.value = false
  }

  function ensureIntroMessage() {
    const intro = buildIntroMessage(llmReady.value)
    if (!messages.value.length) {
      messages.value = [intro]
      return
    }
    if (messages.value[0]?.id === 'intro') {
      messages.value.splice(0, 1, intro)
    }
  }

  function replaceAssistantMessage(index, nextState) {
    messages.value.splice(index, 1, {
      id: messages.value[index].id,
      role: 'assistant',
      content: nextState.error || nextState.text || '正在生成回复...',
      suggestions: nextState.suggestions || [],
    })
  }

  function appendUserMessage(text) {
    messages.value.push({ id: nextMessageId('user'), role: 'user', content: text })
  }

  async function streamChatReply(text) {
    const assistantIndex = messages.value.length
    messages.value.push(buildPendingAssistantMessage(nextMessageId('assistant')))
    let chatState = { text: '', suggestions: [], error: '' }
    try {
      const response = await openAiChatStream(text)
      for await (const frame of parseSseFrames(readResponseTextChunks(response))) {
        chatState = reduceChatStreamEvent(chatState, frame)
        replaceAssistantMessage(assistantIndex, chatState)
      }
    } catch {
      replaceAssistantMessage(assistantIndex, {
        text: 'AI 服务暂时不可用，请检查 LLM 配置。',
      })
    }
  }

  async function runRuntimeFromSubmittedMessage(message) {
    const text = String(message || '').trim()
    if (!text) return
    await runtime.startRuntimeRequest(text)
  }

  async function submitWorkbenchInput(message = composerText.value.trim()) {
    const text = String(message || '').trim()
    if (!text || loading.value || runtime.controlPlanning.value || runtime.controlExecuting.value) {
      return
    }

    appendUserMessage(text)
    composerText.value = ''
    loading.value = true

    try {
      const { data } = await dispatchAiWorkbenchMessage(text)
      const action = resolveWorkbenchDispatchResult(data)
      if (action.kind === 'chat_inline') {
        pushAssistantMessage(action.reply)
        return
      }
      if (action.kind === 'chat_stream') {
        await streamChatReply(text)
        return
      }
      await runRuntimeFromSubmittedMessage(action.message)
    } catch (error) {
      pushAssistantMessage(
        error?.response?.data?.detail
          || error?.message
          || llmNotice.value
          || 'AI 判路失败，请检查模型配置。',
      )
    } finally {
      loading.value = false
    }
  }

  async function selectSession(sessionId) {
    resetThreadState()
    await runtime.selectSession(sessionId)
  }

  async function deleteSession(sessionId) {
    const targetSession = runtime.sessionHistory.value.find((item) => item.id === sessionId)
    if (!targetSession) return
    if (!window.confirm(`将永久删除会话“${targetSession.title}”，是否继续？`)) {
      return
    }
    try {
      const deletedActiveSession = await runtime.deleteSession(sessionId)
      if (deletedActiveSession) {
        resetThreadState()
      }
    } catch (error) {
      pushAssistantMessage(
        error?.response?.data?.detail || error?.message || '删除会话失败。',
      )
    }
  }

  function startNewSession() {
    resetThreadState()
    runtime.resetActiveSession()
  }

  watch(llmReady, ensureIntroMessage, { immediate: true })

  return {
    messages,
    composerText,
    loading,
    controlPermissionMode,
    controlPlanning: runtime.controlPlanning,
    controlExecuting: runtime.controlExecuting,
    workbenchView,
    sessionHistory: runtime.sessionHistory,
    activeSessionId: runtime.activeSessionId,
    plannerLiveText: runtime.plannerLiveText,
    loadSessionHistory: runtime.loadSessionHistory,
    submitWorkbenchInput,
    handleApproval: runtime.handleApproval,
    selectSession,
    deleteSession,
    startNewSession,
    startRuntimeRequest: runRuntimeFromSubmittedMessage,
  }
}

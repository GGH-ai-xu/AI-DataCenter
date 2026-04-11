import { computed, ref, watch } from 'vue'

import { resolveWorkbenchDispatchResult } from '../lib/agentWorkbenchDispatch.js'
import { buildTranscriptFromAgentEvents } from '../lib/agentWorkbenchEventTranscript.js'
import { buildAgentWorkbenchThread } from '../lib/agentWorkbenchThread.js'
import { reduceChatStreamEvent } from '../lib/agentChatStreaming.js'
import {
  DRAFT_TRANSCRIPT_KEY,
  deleteSessionTranscript,
  loadSessionTranscript,
  moveTranscript,
  saveSessionTranscript,
} from '../lib/agentWorkbenchTranscript.js'
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

function buildPendingAssistantMessage(id, roundIndex = 0) {
  return { id, role: 'assistant', content: '正在生成回复...', roundIndex }
}

export function useAiAssistantWorkbench({
  pageState,
  llmReady,
  llmNotice,
  controlPermissionMode: externalControlPermissionMode,
}) {
  const messages = ref([])
  const composerText = ref('')
  const loading = ref(false)
  const controlPermissionMode = externalControlPermissionMode || ref('low')
  let messageSequence = 0

  function nextMessageId(prefix = 'msg') {
    messageSequence += 1
    return `${prefix}-${messageSequence}`
  }

  function activeTranscriptKey() {
    return runtime.activeSessionId.value || DRAFT_TRANSCRIPT_KEY
  }

  function transcriptMessages() {
    return messages.value.filter((item) => item.id !== 'intro')
  }

  function loadTranscript(sessionId = '') {
    const transcript = loadSessionTranscript(sessionId || DRAFT_TRANSCRIPT_KEY)
    messages.value = [buildIntroMessage(llmReady.value), ...transcript]
  }

  function persistTranscript(sessionId = '') {
    saveSessionTranscript(
      sessionId || activeTranscriptKey(),
      transcriptMessages(),
    )
  }

  function nextRuntimeRound() {
    const transcriptRound = transcriptMessages().reduce(
      (maxRound, item) => Math.max(maxRound, Number(item.roundIndex || 0)),
      0,
    )
    return Math.max(Number(runtime.runtimeSession.value?.current_round || 0), transcriptRound) + 1
  }

  function pushAssistantMessage(content, roundIndex = 0) {
    messages.value.push({
      id: nextMessageId('assistant'),
      role: 'assistant',
      content,
      roundIndex,
    })
    persistTranscript()
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

  function syncSessionTranscript(sessionId) {
    const transcript = buildTranscriptFromAgentEvents(runtime.runtimeEvents.value)
    if (!transcript.length) {
      loadTranscript(sessionId)
      return
    }
    messages.value = [buildIntroMessage(llmReady.value), ...transcript]
    saveSessionTranscript(sessionId, transcript)
  }

  function syncCreatedSession(session, previousSessionId) {
    if (!session?.session_id) return
    if (!previousSessionId) {
      moveTranscript(DRAFT_TRANSCRIPT_KEY, session.session_id)
    }
    syncSessionTranscript(session.session_id)
  }

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
      roundIndex: messages.value[index].roundIndex || 0,
    })
    persistTranscript()
  }

  function appendUserMessage(text) {
    messages.value.push({ id: nextMessageId('user'), role: 'user', content: text, roundIndex: 0 })
    persistTranscript()
  }

  function markLatestUserMessageRound(roundIndex) {
    const latestIndex = [...messages.value]
      .map((item, index) => ({ item, index }))
      .reverse()
      .find(({ item }) => item.role === 'user')?.index
    if (latestIndex == null) return
    messages.value.splice(latestIndex, 1, {
      ...messages.value[latestIndex],
      roundIndex,
    })
    persistTranscript()
  }

  async function streamChatReply(text) {
    const assistantIndex = messages.value.length
    messages.value.push(buildPendingAssistantMessage(nextMessageId('assistant')))
    persistTranscript()
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
    return chatState
  }

  async function runRuntimeFromSubmittedMessage(message, options = {}) {
    const text = String(message || '').trim()
    if (!text) return
    return await runtime.startRuntimeRequest(text, options)
  }

  async function persistChatReply(message, reply, previousSessionId, options = {}) {
    const session = await runtime.persistChatTurn(message, reply, {
      sessionId: previousSessionId,
      replyMode: options.replyMode || 'inline',
      suggestions: options.suggestions || [],
    })
    syncCreatedSession(session, previousSessionId)
  }

  async function submitWorkbenchInput(message = composerText.value.trim()) {
    const text = String(message || '').trim()
    if (!text || loading.value || runtime.controlPlanning.value || runtime.controlExecuting.value) {
      return
    }

    appendUserMessage(text)
    composerText.value = ''
    loading.value = true
    const previousSessionId = runtime.activeSessionId.value

    try {
      const { data } = await dispatchAiWorkbenchMessage(text)
      const action = resolveWorkbenchDispatchResult(data)
      if (action.kind === 'chat_inline') {
        pushAssistantMessage(action.reply)
        await persistChatReply(text, action.reply, previousSessionId)
        return
      }
      if (action.kind === 'chat_stream') {
        const chatState = await streamChatReply(text)
        const reply = chatState.error || chatState.text || 'AI 服务暂时不可用，请检查 LLM 配置。'
        await persistChatReply(text, reply, previousSessionId, {
          replyMode: 'stream',
          suggestions: chatState.suggestions || [],
        })
        return
      }
      const roundIndex = previousSessionId ? nextRuntimeRound() : 1
      markLatestUserMessageRound(roundIndex)
      const session = await runRuntimeFromSubmittedMessage(action.message, {
        sessionId: previousSessionId,
      })
      syncCreatedSession(session, previousSessionId)
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
    composerText.value = ''
    loading.value = false
    await runtime.selectSession(sessionId)
    syncSessionTranscript(sessionId)
  }

  async function deleteSession(sessionId) {
    const targetSession = runtime.sessionHistory.value.find((item) => item.id === sessionId)
    if (!targetSession) return
    if (!window.confirm(`将永久删除会话“${targetSession.title}”，是否继续？`)) {
      return
    }
    try {
      const deletedActiveSession = await runtime.deleteSession(sessionId)
      deleteSessionTranscript(sessionId)
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
    deleteSessionTranscript(DRAFT_TRANSCRIPT_KEY)
    resetThreadState()
    runtime.resetActiveSession()
  }

  loadTranscript()

  watch(llmReady, () => {
    ensureIntroMessage()
    if (runtime.activeSessionId.value) {
      persistTranscript(runtime.activeSessionId.value)
      return
    }
    persistTranscript(DRAFT_TRANSCRIPT_KEY)
  }, { immediate: true })

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

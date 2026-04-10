import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { buildAgentSessionHistory } from '../lib/agentSessionHistory.js'
import { createAgentRuntimeSessionPolling } from '../lib/agentRuntimeSessionPolling.js'
import { reduceRuntimeStreamEvent } from '../lib/agentRuntimeStreaming.js'
import { parseSseFrames, readResponseTextChunks } from '../lib/sseFrameStream.js'
import {
  approveAgentRuntimeSession,
  deleteAgentRuntimeSession,
  getAgentRuntimeSession,
  getAgentRuntimeSessionEvents,
  getAgentRuntimeSessions,
  openAgentRuntimeSessionStream,
  startAgentRuntimeSession,
} from '../services/api'

const ACTIVE_RUNTIME_STATUSES = new Set(['running', 'awaiting_approval'])

function toRuntimeStreamState({
  plannerLiveText,
  plannerLiveRevision,
  runtimeEvents,
  runtimeSession,
}) {
  return {
    plannerLiveText: plannerLiveText.value,
    plannerLiveRevision: plannerLiveRevision.value,
    runtimeEvents: runtimeEvents.value,
    runtimeSession: runtimeSession.value || {},
  }
}

export function useAiAssistantRuntimeSession({
  pageState,
  controlPermissionMode,
  onError,
}) {
  const controlPlanning = ref(false)
  const controlExecuting = ref(false)
  const runtimeSession = ref(null)
  const runtimeEvents = ref([])
  const sessionHistory = ref([])
  const plannerStreamActive = ref(false)
  const plannerLiveText = ref('')
  const plannerLiveRevision = ref(0)
  const plannerLivePhase = ref('planning')
  const plannerStreamError = ref('')
  const runtimePolling = createAgentRuntimeSessionPolling()
  const activeSessionId = computed(() => runtimeSession.value?.session_id || '')
  let runtimeStreamController = null

  function mergeRuntimeSession(snapshot) {
    const previous = runtimeSession.value || {}
    const nextSession = { ...previous, ...(snapshot || {}) }
    nextSession.pending_approval = nextSession.status === 'awaiting_approval'
      ? nextSession.pending_approval || previous.pending_approval || null
      : null
    runtimeSession.value = nextSession
    plannerLivePhase.value = nextSession.live_phase || plannerLivePhase.value
  }

  function resetPlannerStream() {
    plannerStreamActive.value = false
    plannerLiveText.value = ''
    plannerLiveRevision.value = 0
    plannerLivePhase.value = 'planning'
    plannerStreamError.value = ''
  }

  function stopRuntimeStream() {
    runtimeStreamController?.abort()
    runtimeStreamController = null
    plannerStreamActive.value = false
  }

  function resetActiveSession() {
    runtimePolling.stop()
    stopRuntimeStream()
    runtimeSession.value = null
    runtimeEvents.value = []
    resetPlannerStream()
  }

  async function loadSessionHistory() {
    try {
      const { data } = await getAgentRuntimeSessions(20)
      sessionHistory.value = buildAgentSessionHistory(data.sessions || [])
    } catch {
      sessionHistory.value = []
    }
  }

  async function refreshRuntimeSession(sessionId = runtimeSession.value?.session_id) {
    if (!sessionId) return runtimeSession.value
    const [{ data: sessionData }, { data: eventData }] = await Promise.all([
      getAgentRuntimeSession(sessionId),
      getAgentRuntimeSessionEvents(sessionId),
    ])
    mergeRuntimeSession(sessionData)
    runtimeEvents.value = eventData.events || []
    plannerLiveText.value = sessionData?.planner_stream?.latest_text || ''
    plannerLiveRevision.value = Number(sessionData?.planner_stream?.revision || 0)
    return runtimeSession.value
  }

  function applyRuntimeStreamFrame(frame) {
    const nextState = reduceRuntimeStreamEvent(
      toRuntimeStreamState({
        plannerLiveText,
        plannerLiveRevision,
        runtimeEvents,
        runtimeSession,
      }),
      frame,
    )
    plannerLiveText.value = nextState.plannerLiveText || ''
    plannerLiveRevision.value = nextState.plannerLiveRevision || 0
    runtimeEvents.value = nextState.runtimeEvents || []
    runtimeSession.value = nextState.runtimeSession || null
    plannerLivePhase.value = nextState.runtimeSession?.live_phase || plannerLivePhase.value
    plannerStreamError.value = nextState.runtimeStreamError || ''
  }

  async function connectRuntimeStream(sessionId) {
    stopRuntimeStream()
    const controller = new AbortController()
    runtimeStreamController = controller
    plannerStreamActive.value = true
    plannerStreamError.value = ''
    try {
      const response = await openAgentRuntimeSessionStream(sessionId, {
        signal: controller.signal,
      })
      for await (const frame of parseSseFrames(readResponseTextChunks(response))) {
        applyRuntimeStreamFrame(frame)
      }
    } catch (error) {
      if (!controller.signal.aborted) {
        plannerStreamError.value = error?.message || '连接运行时流失败。'
      }
    } finally {
      if (runtimeStreamController === controller) {
        plannerStreamActive.value = false
      }
    }
  }

  function syncRuntimePolling() {
    const status = runtimeSession.value?.status
    const shouldPoll = pageState.value === 'workbench'
      && runtimeSession.value?.session_id
      && !plannerStreamActive.value
      && ACTIVE_RUNTIME_STATUSES.has(status)
    if (!shouldPoll) {
      runtimePolling.stop()
      return
    }
    runtimePolling.start(() => refreshRuntimeSession(runtimeSession.value.session_id))
  }

  async function startRuntimeRequest(message) {
    const text = String(message || '').trim()
    if (!text || controlPlanning.value) return
    controlPlanning.value = true
    stopRuntimeStream()
    resetPlannerStream()
    runtimeEvents.value = []
    try {
      const { data } = await startAgentRuntimeSession(text, controlPermissionMode.value)
      mergeRuntimeSession(data)
      if (data?.session_id) {
        void connectRuntimeStream(data.session_id)
        await refreshRuntimeSession(data.session_id)
      }
      await loadSessionHistory()
    } catch (error) {
      runtimeSession.value = null
      runtimeEvents.value = []
      resetPlannerStream()
      onError?.(error?.response?.data?.detail || '创建运行时会话失败。')
    } finally {
      controlPlanning.value = false
    }
  }

  async function handleApproval(approved) {
    if (!runtimeSession.value?.session_id || controlExecuting.value) return
    controlExecuting.value = true
    try {
      await approveAgentRuntimeSession(runtimeSession.value.session_id, approved)
      await refreshRuntimeSession(runtimeSession.value.session_id)
      await loadSessionHistory()
    } catch (error) {
      onError?.(error?.response?.data?.detail || '审批处理失败。')
    } finally {
      controlExecuting.value = false
    }
  }

  async function selectSession(sessionId) {
    await refreshRuntimeSession(sessionId)
    if (ACTIVE_RUNTIME_STATUSES.has(runtimeSession.value?.status)) {
      void connectRuntimeStream(sessionId)
    }
  }

  async function deleteSession(sessionId) {
    const isActiveSession = activeSessionId.value === sessionId
    await deleteAgentRuntimeSession(sessionId)
    if (isActiveSession) {
      resetActiveSession()
    }
    await loadSessionHistory()
    return isActiveSession
  }

  watch(
    () => `${pageState.value}|${runtimeSession.value?.session_id || ''}|${runtimeSession.value?.status || ''}`,
    syncRuntimePolling,
  )

  onBeforeUnmount(() => {
    runtimePolling.stop()
    stopRuntimeStream()
  })

  return {
    controlPlanning,
    controlExecuting,
    runtimeSession,
    runtimeEvents,
    sessionHistory,
    activeSessionId,
    plannerStreamActive,
    plannerLiveText,
    plannerLiveRevision,
    plannerLivePhase,
    plannerStreamError,
    loadSessionHistory,
    refreshRuntimeSession,
    resetActiveSession,
    startRuntimeRequest,
    handleApproval,
    selectSession,
    deleteSession,
  }
}

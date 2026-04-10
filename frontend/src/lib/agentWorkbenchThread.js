const RUNTIME_STATUS_MAP = {
  awaiting_approval: 'awaiting_approval',
  completed: 'completed',
  failed: 'failed',
  aborted: 'failed',
}

const STEP_KIND_LABELS = {
  llm: 'LLM 调用',
  plan: '计划',
  approval: '审批',
  execute: '执行',
  complete: '完成',
  failed: '失败',
}

const LLM_EVENT_TYPES = new Set([
  'LLMRequestPrepared',
  'LLMResponseReceived',
  'LLMPlanExtracted',
  'LLMCallFailed',
])

function mapRuntimeEventTone(eventType) {
  if (String(eventType || '').startsWith('LLM')) return 'llm'
  if (eventType === 'PlanCreated' || eventType === 'GoalParsed' || eventType === 'RuleFallbackUsed') {
    return 'planner'
  }
  if (String(eventType || '').includes('Approval')) return 'approval'
  if (String(eventType || '').includes('Failed')) return 'danger'
  return 'runtime'
}

function buildRuntimeItem(event) {
  if (event.event_type === 'PlanCreated') return buildPlanCard(event)
  if (event.event_type === 'AwaitingApproval') return buildApprovalCard(event)
  if (event.event_type === 'SessionCompleted') return buildResultCard(event)
  if (event.event_type === 'SessionFailed' || event.event_type === 'LLMCallFailed') {
    return buildErrorCard(event)
  }
  return buildToolEventCard(event)
}

function buildPlanCard(event) {
  return buildBaseRuntimeCard(event, 'plan_card', event.payload?.summary || '已生成执行计划')
}

function buildApprovalCard(event) {
  const count = event.payload?.actions?.length || 0
  return buildBaseRuntimeCard(event, 'approval_card', `待审批动作 ${count} 条`)
}

function buildResultCard(event) {
  return buildBaseRuntimeCard(event, 'result_card', event.payload?.summary || '执行已完成')
}

function buildErrorCard(event) {
  return buildBaseRuntimeCard(
    event,
    'error_card',
    event.payload?.error || event.payload?.summary || event.event_type,
  )
}

function buildToolEventCard(event) {
  return {
    ...buildBaseRuntimeCard(event, 'tool_event', event.payload?.summary || event.event_type),
    collapsed: true,
  }
}

function buildBaseRuntimeCard(event, kind, summary) {
  return {
    id: `event-${event.sequence}`,
    kind,
    eventType: event.event_type,
    tone: mapRuntimeEventTone(event.event_type),
    source: 'runtime',
    summary,
    details: event.payload || {},
  }
}

function buildMessageItem(message, index) {
  return {
    id: message.id || `chat-${index}`,
    kind: message.role === 'user' ? 'user_message' : 'assistant_message',
    source: 'chat',
    role: message.role,
    content: message.content,
    suggestions: message.suggestions || [],
  }
}

function createInteractionFromMessage(message, index) {
  return {
    id: `interaction-${message.id || index}`,
    userMessage: buildMessageItem(message, index),
    assistantMessages: [],
    assistantReply: '',
    runtimeCards: [],
    status: 'processing',
    steps: [],
  }
}

function createRuntimeOnlyInteraction(runtimeSession) {
  const content = runtimeSession?.goal_json?.raw_message
    || runtimeSession?.goal_json?.message
    || runtimeSession?.summary
    || '执行请求'
  return {
    id: `interaction-runtime-${runtimeSession?.session_id || 'active'}`,
    userMessage: {
      id: `runtime-user-${runtimeSession?.session_id || 'active'}`,
      kind: 'user_message',
      source: 'runtime',
      role: 'user',
      content,
      suggestions: [],
    },
    assistantMessages: [],
    assistantReply: '',
    runtimeCards: [],
    status: 'processing',
    steps: [],
  }
}

function appendAssistantMessage(interaction, message, index) {
  if (!interaction) return
  const item = buildMessageItem(message, index)
  interaction.assistantMessages.push(item)
  interaction.assistantReply = interaction.assistantMessages
    .map((entry) => String(entry.content || '').trim())
    .filter(Boolean)
    .join('\n\n')
  if (interaction.assistantReply) {
    interaction.status = 'completed'
  }
}

function isLeadMessage(message, index, interactions) {
  return message.role === 'assistant' && index === 0 && interactions.length === 0
}

function normalizeChatInteractions(chatMessages) {
  const interactions = []
  let leadMessage = null
  let currentInteraction = null
  chatMessages.forEach((message, index) => {
    if (isLeadMessage(message, index, interactions)) {
      leadMessage = buildMessageItem(message, index)
      return
    }
    if (message.role === 'user') {
      currentInteraction = createInteractionFromMessage(message, index)
      interactions.push(currentInteraction)
      return
    }
    appendAssistantMessage(currentInteraction, message, index)
  })
  return { leadMessage, interactions }
}

function findRuntimeTargetInteraction(interactions, runtimeSession) {
  const rawMessage = runtimeSession?.goal_json?.raw_message || runtimeSession?.goal_json?.message
  if (rawMessage) {
    const matched = [...interactions].reverse().find(
      (item) => item.userMessage.content === rawMessage,
    )
    if (matched) return matched
  }
  return interactions[interactions.length - 1] || null
}

function mapInteractionStatus(runtimeSession, runtimeCards, interaction) {
  const mappedStatus = RUNTIME_STATUS_MAP[runtimeSession?.status]
  if (mappedStatus) return mappedStatus
  if (runtimeCards.some((card) => card.kind === 'error_card')) return 'failed'
  if (runtimeCards.some((card) => card.kind === 'approval_card')) return 'awaiting_approval'
  if (runtimeCards.some((card) => card.kind === 'result_card')) return 'completed'
  if (runtimeCards.length > 0) return 'processing'
  return interaction.assistantReply ? 'completed' : 'processing'
}

function pushStep(steps, key, state) {
  steps.push({
    key,
    label: STEP_KIND_LABELS[key],
    state,
  })
}

function isLlmRuntimeCard(card) {
  return LLM_EVENT_TYPES.has(card.eventType)
}

function isExecutionRuntimeCard(card) {
  if (card.kind === 'result_card') return true
  if (card.kind === 'tool_event') return !isLlmRuntimeCard(card)
  if (card.kind === 'error_card') return !isLlmRuntimeCard(card)
  return false
}

function buildInteractionSteps(runtimeCards, status) {
  if (!runtimeCards.length) return []
  const steps = []
  const hasLlm = runtimeCards.some(isLlmRuntimeCard)
  const hasLlmFailure = runtimeCards.some((card) => card.eventType === 'LLMCallFailed')
  const hasLlmResponse = runtimeCards.some((card) => (
    card.eventType === 'LLMResponseReceived' || card.eventType === 'LLMPlanExtracted'
  ))
  const hasPlan = runtimeCards.some((card) => card.kind === 'plan_card')
  const hasApproval = runtimeCards.some((card) => card.kind === 'approval_card')
  const hasExecution = runtimeCards.some(isExecutionRuntimeCard)
  const hasResult = runtimeCards.some((card) => card.kind === 'result_card')
  const hasError = runtimeCards.some((card) => card.kind === 'error_card')

  if (hasLlm) {
    let llmState = 'active'
    if (hasLlmFailure) llmState = 'error'
    else if (hasLlmResponse) llmState = 'done'
    pushStep(steps, 'llm', llmState)
  }
  if (hasPlan) pushStep(steps, 'plan', status === 'processing' && !hasExecution ? 'active' : 'done')
  if (hasApproval) pushStep(steps, 'approval', status === 'awaiting_approval' ? 'active' : 'done')
  if (hasExecution && !hasError) {
    const state = status === 'completed' ? 'done' : 'active'
    pushStep(steps, 'execute', state)
  }
  if (hasResult) pushStep(steps, 'complete', 'done')
  if (hasError || status === 'failed') pushStep(steps, 'failed', 'error')
  return steps
}

function buildRuntimeAssistantReply(runtimeSession, interaction) {
  if (interaction.assistantReply) return interaction.assistantReply
  const phase = runtimeSession?.live_phase || runtimeSession?.status
  if (phase === 'awaiting_approval') return '计划已生成，等待审批。'
  if (phase === 'executing') return '已批准执行，正在推进步骤。'
  if (phase === 'completed') return runtimeSession?.summary || '执行已完成。'
  if (phase === 'failed' || phase === 'aborted') {
    return runtimeSession?.latest_error || runtimeSession?.summary || '执行失败，请查看详细步骤。'
  }
  if (runtimeSession?.session_id) return '已进入执行链，正在生成计划。'
  return interaction.assistantReply
}

function applyRuntimeState(interactions, runtimeSession, runtimeEvents) {
  if (!runtimeSession && runtimeEvents.length === 0) return interactions
  let target = findRuntimeTargetInteraction(interactions, runtimeSession)
  if (!target) {
    target = createRuntimeOnlyInteraction(runtimeSession)
    interactions.push(target)
  }
  target.runtimeCards = runtimeEvents.map(buildRuntimeItem)
  target.status = mapInteractionStatus(runtimeSession, target.runtimeCards, target)
  target.steps = buildInteractionSteps(target.runtimeCards, target.status)
  target.assistantReply = buildRuntimeAssistantReply(runtimeSession, target)
  return interactions
}

export function buildAgentWorkbenchThread({
  chatMessages = [],
  runtimeSession = null,
  runtimeEvents = [],
}) {
  const { leadMessage, interactions } = normalizeChatInteractions(chatMessages)
  return {
    topbar: {},
    leadMessage,
    interactions: applyRuntimeState([...interactions], runtimeSession, runtimeEvents),
  }
}

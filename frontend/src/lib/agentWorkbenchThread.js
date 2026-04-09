const STATUS_LABELS = {
  idle: '未开始',
  running: '执行中',
  awaiting_approval: '等待审批',
  completed: '已完成',
  failed: '执行失败',
  aborted: '已终止',
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

function buildRouteConfirmItems(pendingRouteConfirm) {
  if (!pendingRouteConfirm) return []
  return [{
    id: pendingRouteConfirm.id,
    kind: 'route_confirm_card',
    source: 'system',
    message: pendingRouteConfirm.message,
  }]
}

function buildTopbar(runtimeSession) {
  const pendingApprovalCount = runtimeSession?.pending_approval?.actions?.length || 0
  return {
    modeLabel: '统一工作台',
    statusLabel: STATUS_LABELS[runtimeSession?.status] || '未开始',
    approvalLabel: runtimeSession?.awaiting_approval ? `待审批 ${pendingApprovalCount}` : '无需审批',
  }
}

export function buildAgentWorkbenchThread({
  chatMessages = [],
  runtimeSession = null,
  runtimeEvents = [],
  pendingRouteConfirm = null,
}) {
  return {
    topbar: buildTopbar(runtimeSession),
    items: [
      ...chatMessages.map(buildMessageItem),
      ...runtimeEvents.map(buildRuntimeItem),
      ...buildRouteConfirmItems(pendingRouteConfirm),
    ],
  }
}

const HIGHLIGHT_EVENT_TYPES = new Set([
  'AwaitingApproval',
  'LLMResponseReceived',
  'PlanRevised',
  'StepFailed',
  'SessionFailed',
  'SessionCompleted',
])

function mapEventTone(eventType) {
  if (eventType.startsWith('LLM')) return 'llm'
  if (eventType.includes('Approval')) return 'approval'
  if (eventType.includes('Failed')) return 'danger'
  if (eventType === 'SessionCompleted' || eventType === 'StepCompleted') return 'success'
  return 'planning'
}

function sortEvents(events) {
  return [...(events || [])].sort((left, right) => (
    (Number(left.round_index || 0) - Number(right.round_index || 0))
    || (Number(left.sequence || 0) - Number(right.sequence || 0))
    || (Number(left.timestamp || 0) - Number(right.timestamp || 0))
  ))
}

function buildRoundRecord(roundIndex) {
  return {
    roundIndex,
    events: [],
  }
}

function buildEventRecord(event) {
  return {
    eventType: event.event_type,
    tone: mapEventTone(event.event_type),
    summary: event.payload?.summary || event.payload?.error || event.event_type,
    details: event.payload || {},
    timestamp: event.timestamp || 0,
    sequence: Number(event.sequence || 0),
  }
}

export function buildExecutionLedgerView({ session, events }) {
  const sortedEvents = sortEvents(events)
  const rounds = []
  const roundMap = new Map()
  let llmCallCount = 0

  for (const event of sortedEvents) {
    if (event.event_type === 'LLMResponseReceived') {
      llmCallCount += 1
    }
    const roundIndex = Number(event.round_index || 0)
    if (!roundMap.has(roundIndex)) {
      const roundRecord = buildRoundRecord(roundIndex)
      roundMap.set(roundIndex, roundRecord)
      rounds.push(roundRecord)
    }
    roundMap.get(roundIndex).events.push(buildEventRecord(event))
  }

  return {
    overview: {
      status: session?.status || 'idle',
      eventCount: sortedEvents.length,
      llmCallCount,
      currentRound: rounds.at(-1)?.roundIndex || 0,
      awaitingApproval: !!session?.awaiting_approval,
      latestError: session?.latest_error || '',
    },
    rounds,
    highlightedEvents: sortEvents(events)
      .filter((event) => HIGHLIGHT_EVENT_TYPES.has(event.event_type))
      .reverse()
      .map(buildEventRecord),
  }
}

const CHAT_EVENT_ROLE_MAP = {
  UserMessageSubmitted: 'user',
  AssistantMessageGenerated: 'assistant',
}

function eventMessageId(event, fallbackIndex) {
  if (event?.id != null) return `event-${event.id}`
  const roundIndex = Number(event?.round_index || 0)
  const sequence = Number(event?.sequence || 0)
  return `event-${roundIndex}-${sequence}-${fallbackIndex}`
}

export function buildTranscriptFromAgentEvents(events = []) {
  return (events || []).flatMap((event, index) => {
    const role = CHAT_EVENT_ROLE_MAP[event?.event_type]
    const content = String(event?.payload?.content || '').trim()
    if (!role || !content) return []
    return [{
      id: eventMessageId(event, index),
      role,
      content,
      suggestions: role === 'assistant' ? [...(event?.payload?.suggestions || [])] : [],
      roundIndex: Number(event?.round_index || 0),
    }]
  })
}

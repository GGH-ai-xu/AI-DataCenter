function formatHistoryTime(value) {
  const ts = Number(value || 0)
  if (!ts) return '刚刚'
  return new Date(ts * 1000).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

function buildSessionTitle(session) {
  const originalMessage = session?.goal_json?.raw_message || session?.goal_json?.message
  return String(originalMessage || session?.summary || '未命名会话').trim()
}

export function buildAgentSessionHistory(sessions = []) {
  return sessions.map((session) => ({
    id: session.session_id,
    title: buildSessionTitle(session),
    status: session.status || 'idle',
    canDelete: session.status !== 'running',
    timeLabel: formatHistoryTime(session.updated_at),
  }))
}

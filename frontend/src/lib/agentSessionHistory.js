function formatHistoryTime(value) {
  const ts = Number(value || 0)
  if (!ts) return '刚刚'
  return new Date(ts * 1000).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

function buildSessionTitle(session) {
  const fallback = session?.goal_json?.message || '未命名会话'
  return String(session?.summary || fallback).trim()
}

export function buildAgentSessionHistory(sessions = []) {
  return sessions.map((session) => ({
    id: session.session_id,
    title: buildSessionTitle(session),
    status: session.status || 'idle',
    timeLabel: formatHistoryTime(session.updated_at),
  }))
}

export function resolveWorkbenchDispatchResult(payload = {}) {
  const routeKind = String(payload?.route_kind || '').trim()
  const replyMode = String(payload?.reply_mode || '').trim()
  const reply = String(payload?.reply || '').trim()
  const message = String(payload?.message || '').trim()

  if (routeKind === 'chat' && replyMode === 'inline' && reply) {
    return { kind: 'chat_inline', reply }
  }
  if (routeKind === 'chat' && replyMode === 'stream') {
    return { kind: 'chat_stream' }
  }
  if (routeKind === 'runtime' && message) {
    return { kind: 'runtime', message }
  }
  throw new Error('AI 工作台判路结果无效。')
}

const RUNTIME_PATTERNS = /(暂停|恢复|终止|调度|功耗上限|预算|priority|优先级|执行)/i
const CHAT_PATTERNS = /(为什么|怎么回事|解释|总结|分析|原因|风险)/i

export function resolveWorkbenchIntent(message = '') {
  const text = String(message || '').trim()
  if (!text) return { kind: 'empty' }
  if (RUNTIME_PATTERNS.test(text)) return { kind: 'runtime' }
  if (CHAT_PATTERNS.test(text)) return { kind: 'chat' }
  return { kind: 'confirm' }
}

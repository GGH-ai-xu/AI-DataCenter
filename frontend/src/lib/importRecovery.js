const DEFAULT_SSH_PORT = 22

export const UNREADABLE_SAVED_HOST_CREDENTIAL_MESSAGE = '已保存 SSH 凭据无法用当前主密钥解密'
export const MISSING_SAVED_HOST_CREDENTIAL_MESSAGE = '已保存 SSH 凭据不存在'

export function buildSavedHostRecoveryDraft(host = {}) {
  return {
    providerType: host.provider_type || 'ssh_linux',
    agentLabel: host.label || 'SSH Linux',
    agentUrl: host.agent_url || '',
    authType: host.auth_type || 'password',
    hostFingerprint: host.host_fingerprint || '',
    sshForm: {
      host: host.host || '',
      port: Number(host.port || DEFAULT_SSH_PORT),
      username: host.username || '',
      sudoEnabled: Boolean(host.sudo_enabled),
    },
  }
}

function requiresSavedHostRecovery(detail = '', host = null) {
  const message = String(detail || '').trim()
  if (host?.credential_status === 'unreadable') return true
  if (host?.credential_status === 'missing') return true
  return (
    message.includes(UNREADABLE_SAVED_HOST_CREDENTIAL_MESSAGE)
    || message.includes(MISSING_SAVED_HOST_CREDENTIAL_MESSAGE)
  )
}

export function resolveSavedHostScanFailure({ detail = '', host = null } = {}) {
  const message = String(detail || '').trim() || '扫描失败'
  if (!host || !requiresSavedHostRecovery(message, host)) {
    return {
      shouldRecoverSavedHost: false,
      feedbackText: message,
    }
  }
  return {
    shouldRecoverSavedHost: true,
    feedbackText: '已保存 SSH 凭据已失效，请在“连接来源”重新输入密码或私钥后再扫描。',
    nextStage: 'source',
    nextSelectedSavedHostId: null,
    nextScanResult: null,
    nextSelectedGpuIndexes: [],
  }
}

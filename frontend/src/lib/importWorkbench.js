export const IMPORT_STAGE_TABS = Object.freeze([
  { key: 'saved', label: '已保存主机', desc: '复用成功连接过的目标' },
  { key: 'source', label: '连接来源', desc: '配置地址、凭据与扫描入口' },
  { key: 'hardware', label: '硬件概览', desc: '确认本次扫描出的真实硬件' },
  { key: 'selection', label: '选卡导入', desc: '确定后续纳入治理的 GPU 范围' },
])

export function buildImportProviderPayload({
  providerType,
  agentLabel,
  agentUrl,
  authType,
  hostFingerprint,
  sshForm,
}) {
  if (providerType === 'ssh_linux') {
    return {
      provider_type: 'ssh_linux',
      label: (agentLabel || '').trim(),
      host: (sshForm.host || '').trim(),
      port: Number(sshForm.port || 22),
      username: (sshForm.username || '').trim(),
      auth_type: authType,
      sudo_enabled: Boolean(sshForm.sudoEnabled),
      host_fingerprint: hostFingerprint || null,
    }
  }
  return {
    provider_type: providerType,
    label: (agentLabel || '').trim(),
    agent_url: providerType === 'http_remote' ? (agentUrl || '').trim() || null : null,
  }
}

export function buildImportCredentialPayload({ providerType, authType, sshForm }) {
  if (providerType !== 'ssh_linux') return {}
  return {
    password: authType === 'password' ? sshForm.password : '',
    private_key: authType === 'private_key' ? sshForm.privateKey : '',
    private_key_passphrase: authType === 'private_key' ? sshForm.privateKeyPassphrase : '',
    sudo_password: sshForm.sudoEnabled ? sshForm.sudoPassword : '',
  }
}

export function resolveImportAgentUrl({ providerType, scanResult, agentUrl, sshForm }) {
  if (scanResult?.agent_url) return scanResult.agent_url
  if (scanResult?.provider?.agent_url) return scanResult.provider.agent_url
  if (providerType === 'ssh_linux') {
    const user = sshForm.username || 'user'
    const host = sshForm.host || 'host'
    return `ssh://${user}@${host}:${sshForm.port || 22}`
  }
  if (providerType === 'http_remote') return agentUrl || '远程地址待输入'
  return '本机 / 回环连接'
}

export function resolveImportConnectionSummary({
  providerType,
  currentAgentUrl,
  scanBusy,
  scanResult,
}) {
  const sourceLabel = providerType === 'ssh_linux'
    ? 'SSH Linux'
    : (providerType === 'http_remote' ? '远程 Agent' : '本机')
  const scanLabel = scanBusy ? '扫描中' : (scanResult?.success ? '已扫描' : '未扫描')
  return `${sourceLabel} / ${currentAgentUrl} / ${scanLabel}`
}

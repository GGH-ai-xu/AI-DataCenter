import { buildSavedHostRecoveryDraft } from './importRecovery.js'

export function createSshForm(defaultPort) {
  return {
    host: '',
    port: defaultPort,
    username: '',
    password: '',
    privateKey: '',
    privateKeyPassphrase: '',
    sudoEnabled: false,
    sudoPassword: '',
  }
}

export function responseTarget(data) {
  return data?.provider || {}
}

export function clearCredentialInputs(sshForm) {
  sshForm.password = ''
  sshForm.privateKey = ''
  sshForm.privateKeyPassphrase = ''
  sshForm.sudoPassword = ''
}

export function clearScanState(scanResult, selectedGpuIndexes) {
  scanResult.value = null
  selectedGpuIndexes.value = []
}

export function errorDetail(error, fallbackText) {
  return error?.response?.data?.detail || error?.message || fallbackText
}

export function findSavedHost(hosts, hostId) {
  return hosts.find((item) => item.id === Number(hostId)) || null
}

export function applySavedHostRecovery({
  host,
  feedbackText,
  applyTarget,
  sshForm,
  scanResult,
  selectedGpuIndexes,
  activeStage,
  feedback,
  selectedSavedHostId,
}) {
  const draft = buildSavedHostRecoveryDraft(host)
  applyTarget({
    provider_type: draft.providerType,
    label: draft.agentLabel,
    agent_url: draft.agentUrl,
    auth_type: draft.authType,
    host_fingerprint: draft.hostFingerprint,
    host: draft.sshForm.host,
    port: draft.sshForm.port,
    username: draft.sshForm.username,
    sudo_enabled: draft.sshForm.sudoEnabled,
  })
  selectedSavedHostId.value = null
  clearCredentialInputs(sshForm)
  clearScanState(scanResult, selectedGpuIndexes)
  activeStage.value = 'source'
  feedback.value = { tone: 'warning', text: feedbackText }
}

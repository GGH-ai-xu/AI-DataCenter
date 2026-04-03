import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildSavedHostRecoveryDraft,
  resolveSavedHostScanFailure,
  UNREADABLE_SAVED_HOST_CREDENTIAL_MESSAGE,
} from './importRecovery.js'

test('buildSavedHostRecoveryDraft maps saved host into manual source form draft', () => {
  const draft = buildSavedHostRecoveryDraft({
    provider_type: 'ssh_linux',
    label: 'ssh',
    host: '10.151.225.108',
    port: 22,
    username: 'dell',
    auth_type: 'password',
    sudo_enabled: true,
    host_fingerprint: 'fingerprint',
  })

  assert.deepEqual(draft, {
    providerType: 'ssh_linux',
    agentLabel: 'ssh',
    agentUrl: '',
    authType: 'password',
    hostFingerprint: 'fingerprint',
    sshForm: {
      host: '10.151.225.108',
      port: 22,
      username: 'dell',
      sudoEnabled: true,
    },
  })
})

test('resolveSavedHostScanFailure requests manual credential recovery for unreadable saved host', () => {
  const result = resolveSavedHostScanFailure({
    detail: UNREADABLE_SAVED_HOST_CREDENTIAL_MESSAGE,
    host: {
      id: 1,
      provider_type: 'ssh_linux',
      label: 'ssh',
      host: '10.151.225.108',
      port: 22,
      username: 'dell',
      auth_type: 'password',
      credential_status: 'unreadable',
    },
  })

  assert.equal(result.shouldRecoverSavedHost, true)
  assert.equal(result.nextStage, 'source')
  assert.equal(result.nextSelectedSavedHostId, null)
  assert.equal(result.nextScanResult, null)
  assert.deepEqual(result.nextSelectedGpuIndexes, [])
  assert.match(result.feedbackText, /重新输入密码或私钥/)
})

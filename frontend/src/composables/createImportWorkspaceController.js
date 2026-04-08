import { computed, reactive, ref, watch } from 'vue'

import { formatImportedGpuLabel, hasValidImportContext } from '../lib/importContext.js'
import { resolveSavedHostScanFailure } from '../lib/importRecovery.js'
import {
  buildImportCredentialPayload,
  buildImportProviderPayload,
  IMPORT_STAGE_TABS,
  resolveImportAgentUrl,
} from '../lib/importWorkbench.js'
import {
  applySavedHostRecovery,
  clearScanState,
  createSshForm,
  errorDetail,
  findSavedHost,
  responseTarget,
} from '../lib/importWorkspaceState.js'
const DEFAULT_SSH_PORT = 22

function createState() {
  return {
    providerType: ref('http_local'),
    agentUrl: ref(''),
    agentLabel: ref('本机'),
    authType: ref('password'),
    hostFingerprint: ref(''),
    activeStage: ref('saved'),
    selectedSavedHostId: ref(null),
    syncingSavedHost: ref(false),
    sshForm: reactive(createSshForm()),
    scanBusy: ref(false),
    importBusy: ref(false),
    feedback: ref(null),
    scanResult: ref(null),
    selectedGpuIndexes: ref([]),
  }
}

function resolveStepState(stepKey, state) {
  if (stepKey === state.activeStage.value) return 'current'
  if (stepKey === 'saved') {
    return state.activeStage.value === 'saved' ? 'current' : 'done'
  }
  if (stepKey === 'source') {
    return state.scanResult.value?.success ? 'done' : 'pending'
  }
  if (stepKey === 'hardware') {
    if (!state.scanResult.value?.success) return 'pending'
    return state.activeStage.value === 'selection' ? 'done' : 'pending'
  }
  if (stepKey === 'selection') {
    if (!state.scanResult.value?.success) return 'pending'
    return state.selectedGpuIndexes.value.length > 0 ? 'ready' : 'pending'
  }
  return 'pending'
}

function buildComputed(state, deps) {
  const currentContext = computed(() => deps.store.importContext)
  const currentReason = computed(() => currentContext.value?.invalid_reason || '')
  const hasCurrentScope = computed(() => hasValidImportContext(currentContext.value))
  const canViewAllSavedHosts = computed(() => deps.auth.currentUser?.role === 'admin')
  const importedCountLabel = computed(() => formatImportedGpuLabel(state.selectedGpuIndexes.value))
  const currentAgentUrl = computed(() => resolveImportAgentUrl({
    providerType: state.providerType.value,
    scanResult: state.scanResult.value,
    agentUrl: state.agentUrl.value,
    sshForm: state.sshForm,
  }))
  return {
    currentReason,
    hasCurrentScope,
    canViewAllSavedHosts,
    importedCountLabel,
    currentAgentUrl,
    stepItems: computed(() => IMPORT_STAGE_TABS.map((tab, index) => ({
      ...tab,
      order: index + 1,
      state: resolveStepState(tab.key, state),
    }))),
    sidebarSelectedSummary: computed(() => state.selectedGpuIndexes.value.length > 0 ? importedCountLabel.value : '尚未选择 GPU'),
    heroTitle: computed(() => hasCurrentScope.value ? '调整治理范围' : '治理前准备'),
    heroDescription: computed(() => hasCurrentScope.value
      ? '按步骤检查目标来源、扫描结果与导入范围，再更新本次真正受控的 GPU 集合。'
      : '先确认连接来源，再执行一次真实扫描，最后只导入本次需要纳入治理的 GPU。'),
    sidebarScopeSummary: computed(() => hasCurrentScope.value
      ? `当前有效范围：${formatImportedGpuLabel(currentContext.value?.imported_gpu_indexes || [])}`
      : '控制台只治理本次导入选中的卡'),
    footerMessage: computed(() => resolveFooterMessage(state, deps, currentReason.value)),
    canSubmitImport: computed(() => Boolean(state.scanResult.value?.success) && state.selectedGpuIndexes.value.length > 0),
    activeSavedHost: computed(() => findSavedHost(deps.savedHosts.hosts.value, state.selectedSavedHostId.value)),
  }
}
function resolveFooterMessage(state, deps, currentReason) {
  if (state.activeStage.value === 'saved') {
    return deps.savedHosts.loading.value
      ? '正在读取已保存主机，请稍候。'
      : '可以先复用已保存主机，也可以切换到“连接来源”手动新建连接。'
  }
  if (state.scanBusy.value) return '正在扫描目标机器，请稍候。'
  if (!state.scanResult.value?.success) {
    return currentReason || '先完成一次扫描，再继续验机和选卡。'
  }
  if (state.selectedGpuIndexes.value.length <= 0) {
    return '至少选择 1 张 GPU，才能导入并进入控制台。'
  }
  return '导入后控制台只显示和治理本次选中的卡。'
}
function savedHostSummary(host, scanResult) {
  if (!host || !scanResult?.success) return null
  return {
    label: host.label || '已保存主机',
    target: host.agent_url || `${host.username || 'user'}@${host.host || 'host'}:${host.port || DEFAULT_SSH_PORT}`,
    mode: 'saved',
  }
}
function payloadBase(state) {
  if (state.selectedSavedHostId.value) {
    return { saved_host_id: state.selectedSavedHostId.value }
  }
  return {
    provider: buildImportProviderPayload({
      providerType: state.providerType.value,
      agentLabel: state.agentLabel.value,
      agentUrl: state.agentUrl.value,
      authType: state.authType.value,
      hostFingerprint: state.hostFingerprint.value,
      sshForm: state.sshForm,
    }),
    credentials: buildImportCredentialPayload({
      providerType: state.providerType.value,
      authType: state.authType.value,
      sshForm: state.sshForm,
    }),
  }
}
function applyTarget(state, target) {
  state.syncingSavedHost.value = true
  state.providerType.value = target.provider_type || state.providerType.value
  state.agentLabel.value = target.label || state.agentLabel.value
  state.agentUrl.value = target.agent_url || ''
  state.authType.value = target.auth_type || 'password'
  state.hostFingerprint.value = target.host_fingerprint || ''
  state.sshForm.host = target.host || ''
  state.sshForm.port = target.port || DEFAULT_SSH_PORT
  state.sshForm.username = target.username || ''
  state.sshForm.sudoEnabled = Boolean(target.sudo_enabled)
  queueMicrotask(() => {
    state.syncingSavedHost.value = false
  })
}
function applyScanResponse(state, data) {
  state.scanResult.value = data
  applyTarget(state, responseTarget(data))
  state.hostFingerprint.value = data?.provider?.host_fingerprint || data?.capabilities?.host_fingerprint || ''
  state.selectedGpuIndexes.value = data.success ? data.gpus.map((gpu) => Number(gpu.index)) : []
  state.feedback.value = { tone: data.success ? 'ok' : 'warning', text: data.message || (data.success ? '扫描完成，已更新候选硬件列表。' : '扫描失败') }
  if (data.success) state.activeStage.value = 'hardware'
}
function recoverSavedHost(state, host, feedbackText) {
  applySavedHostRecovery({
    host,
    feedbackText,
    applyTarget: (target) => applyTarget(state, target),
    sshForm: state.sshForm,
    scanResult: state.scanResult,
    selectedGpuIndexes: state.selectedGpuIndexes,
    activeStage: state.activeStage,
    feedback: state.feedback,
    selectedSavedHostId: state.selectedSavedHostId,
  })
}
async function refreshContext(state, deps) {
  const { data } = await deps.api.getImportContext()
  deps.store.setImportContext(data)
  applyTarget(state, {
    provider_type: data?.provider_type || (data?.source_mode === 'remote' ? 'http_remote' : 'http_local'),
    label: data?.agent_label || '',
    agent_url: data?.agent_url || '',
  })
  state.selectedGpuIndexes.value = (data?.imported_gpu_indexes || []).map((value) => Number(value))
}
async function refreshSavedHosts(deps, scope = deps.savedHosts.scope.value) {
  try {
    await deps.savedHosts.loadHosts(scope)
  } catch {}
}
async function scanTarget(state, deps, payload, host = null) {
  state.scanBusy.value = true
  state.feedback.value = null
  try {
    const { data } = await deps.api.scanImportContext(payload)
    applyScanResponse(state, data)
  } catch (error) {
    clearScanState(state.scanResult, state.selectedGpuIndexes)
    const result = resolveSavedHostScanFailure({
      detail: errorDetail(error, '扫描失败'),
      host,
    })
    if (result.shouldRecoverSavedHost && host) {
      recoverSavedHost(state, host, result.feedbackText)
    } else {
      state.feedback.value = { tone: 'error', text: result.feedbackText }
    }
  } finally {
    state.scanBusy.value = false
  }
}
async function handleScan(state, deps) {
  state.selectedSavedHostId.value = null
  await scanTarget(state, deps, payloadBase(state))
}
async function handleSavedHostScan(state, deps, hostId) {
  const host = findSavedHost(deps.savedHosts.hosts.value, hostId)
  state.selectedSavedHostId.value = Number(hostId)
  const result = resolveSavedHostScanFailure({ host })
  if (result.shouldRecoverSavedHost && host) {
    recoverSavedHost(state, host, result.feedbackText)
    return
  }
  await scanTarget(state, deps, payloadBase(state), host)
}
function handleSavedHostEdit(state, deps, hostId) {
  const host = findSavedHost(deps.savedHosts.hosts.value, hostId)
  if (!host) return
  recoverSavedHost(state, host, '已载入主机记录，请补充密码或私钥后重新扫描。')
}
async function handleDeleteSavedHost(state, deps, hostId) {
  if (state.selectedSavedHostId.value === Number(hostId)) {
    state.selectedSavedHostId.value = null
  }
  await deps.savedHosts.deleteHost(hostId)
}
async function handleImport(state, deps) {
  state.importBusy.value = true
  state.feedback.value = null
  try {
    const { data } = await deps.api.commitImportContext({
      ...payloadBase(state),
      gpu_indexes: state.selectedGpuIndexes.value,
    })
    deps.store.setImportContext(data.import_context)
    deps.store.setWorkspaceReady(true)
    await refreshSavedHosts(deps)
    await deps.router.replace('/')
  } catch (error) {
    const host = findSavedHost(deps.savedHosts.hosts.value, state.selectedSavedHostId.value)
    const result = resolveSavedHostScanFailure({
      detail: errorDetail(error, '导入失败'),
      host,
    })
    if (result.shouldRecoverSavedHost && host) {
      recoverSavedHost(state, host, result.feedbackText)
    } else {
      state.feedback.value = { tone: 'error', text: result.feedbackText }
      state.activeStage.value = 'selection'
    }
  } finally {
    state.importBusy.value = false
  }
}
function wireWatchers(state) {
  watch([state.providerType, state.agentUrl, state.agentLabel, state.authType], () => {
    if (state.syncingSavedHost.value) return
    state.selectedSavedHostId.value = null
  })
  watch(() => state.sshForm.sudoEnabled, (enabled) => {
    if (!enabled) state.sshForm.sudoPassword = ''
  })
  watch([() => state.sshForm.host, () => state.sshForm.port, () => state.sshForm.username], () => {
    if (state.syncingSavedHost.value) return
    state.selectedSavedHostId.value = null
  })
  watch(state.authType, (value) => {
    if (value === 'password') {
      state.sshForm.privateKey = ''
      state.sshForm.privateKeyPassphrase = ''
      return
    }
    state.sshForm.password = ''
  })
}
export function createImportWorkspaceController(deps) {
  const state = createState()
  const computedState = buildComputed(state, deps)
  state.savedHostSummary = computed(() =>
    savedHostSummary(computedState.activeSavedHost.value, state.scanResult.value))
  wireWatchers(state)
  return {
    ...state,
    ...computedState,
    savedHostDeleteBusyId: deps.savedHosts.deletingId,
    savedHostErrorText: deps.savedHosts.errorText,
    savedHostList: deps.savedHosts.hosts,
    savedHostLoading: deps.savedHosts.loading,
    savedHostScope: deps.savedHosts.scope,
    tabs: IMPORT_STAGE_TABS,
    refreshContext: () => refreshContext(state, deps),
    refreshSavedHosts: (scope) => refreshSavedHosts(deps, scope),
    handleScan: () => handleScan(state, deps),
    handleSavedHostScan: (hostId) => handleSavedHostScan(state, deps, hostId),
    handleSavedHostEdit: (hostId) => handleSavedHostEdit(state, deps, hostId),
    handleDeleteSavedHost: (hostId) => handleDeleteSavedHost(state, deps, hostId),
    handleImport: () => handleImport(state, deps),
  }
}

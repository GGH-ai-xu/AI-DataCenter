import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { commitImportContext, getImportContext, scanImportContext } from '../services/api.js'
import { formatImportedGpuLabel, hasValidImportContext } from '../lib/importContext.js'
import {
  resolveSavedHostScanFailure,
} from '../lib/importRecovery.js'
import {
  buildImportCredentialPayload,
  buildImportProviderPayload,
  IMPORT_STAGE_TABS,
  resolveImportAgentUrl,
  resolveImportConnectionSummary,
} from '../lib/importWorkbench.js'
import {
  applySavedHostRecovery,
  clearScanState,
  createSshForm,
  errorDetail,
  findSavedHost,
  responseTarget,
} from '../lib/importWorkspaceState.js'
import { useAppStore } from '../stores/app.js'
import { useAuthStore } from '../stores/auth.js'
import { useSavedHosts } from './useSavedHosts.js'
const DEFAULT_SSH_PORT = 22
export function useImportWorkspace() {
  const router = useRouter()
  const store = useAppStore()
  const auth = useAuthStore()
  const savedHosts = useSavedHosts()
  const providerType = ref('http_local')
  const agentUrl = ref('')
  const agentLabel = ref('本机 Agent')
  const authType = ref('password')
  const hostFingerprint = ref('')
  const activeStage = ref('saved')
  const selectedSavedHostId = ref(null)
  const syncingSavedHost = ref(false)
  const sshForm = reactive(createSshForm())
  const scanBusy = ref(false)
  const importBusy = ref(false)
  const feedback = ref(null)
  const scanResult = ref(null)
  const selectedGpuIndexes = ref([])

  const currentContext = computed(() => store.importContext)
  const currentReason = computed(() => currentContext.value?.invalid_reason || '')
  const hasCurrentScope = computed(() => hasValidImportContext(currentContext.value))
  const canViewAllSavedHosts = computed(() => auth.currentUser?.role === 'admin')
  const importedCountLabel = computed(() => formatImportedGpuLabel(selectedGpuIndexes.value))
  const heroTitle = computed(() => (hasCurrentScope.value ? '重新导入管理范围' : '进入控制台前的准备'))
  const heroDescription = computed(() => (hasCurrentScope.value
    ? '先看已保存主机或新建连接，再确认本次需要纳入治理的 GPU 范围。'
    : '先从已保存主机或新建连接里选择目标，验看硬件后再勾选本次纳入治理的 GPU。'))
  const currentAgentUrl = computed(() => resolveImportAgentUrl({ providerType: providerType.value, scanResult: scanResult.value, agentUrl: agentUrl.value, sshForm }))
  const connectionSummary = computed(() => resolveImportConnectionSummary({ providerType: providerType.value, currentAgentUrl: currentAgentUrl.value, scanBusy: scanBusy.value, scanResult: scanResult.value }))
  const sidebarSelectedSummary = computed(() => (selectedGpuIndexes.value.length > 0 ? importedCountLabel.value : '尚未选择 GPU'))
  const sidebarScopeSummary = computed(() => {
    if (hasCurrentScope.value) {
      return `当前有效范围：${formatImportedGpuLabel(currentContext.value?.imported_gpu_indexes || [])}`
    }
    return '控制台只治理本次导入选中的卡'
  })
  const footerMessage = computed(() => {
    if (activeStage.value === 'saved') {
      return savedHosts.loading.value
        ? '正在读取已保存主机，请稍候。'
        : '可以先复用已保存主机，也可以切换到“连接来源”手动新建连接。'
    }
    if (scanBusy.value) return '正在扫描目标机器，请稍候。'
    if (!scanResult.value?.success) {
      return currentReason.value || '先完成一次扫描，再继续验机和选卡。'
    }
    if (selectedGpuIndexes.value.length <= 0) {
      return '至少选择 1 张 GPU，才能导入并进入控制台。'
    }
    return '导入后控制台只显示和治理本次选中的卡。'
  })
  const canSubmitImport = computed(() => Boolean(scanResult.value?.success) && selectedGpuIndexes.value.length > 0)

  function payloadBase() {
    if (selectedSavedHostId.value) {
      return { saved_host_id: selectedSavedHostId.value }
    }
    return {
      provider: buildImportProviderPayload({ providerType: providerType.value, agentLabel: agentLabel.value, agentUrl: agentUrl.value, authType: authType.value, hostFingerprint: hostFingerprint.value, sshForm }),
      credentials: buildImportCredentialPayload({ providerType: providerType.value, authType: authType.value, sshForm }),
    }
  }

  function applyTarget(target) {
    syncingSavedHost.value = true
    providerType.value = target.provider_type || providerType.value
    agentLabel.value = target.label || agentLabel.value
    agentUrl.value = target.agent_url || ''
    authType.value = target.auth_type || 'password'
    hostFingerprint.value = target.host_fingerprint || ''
    sshForm.host = target.host || ''
    sshForm.port = target.port || DEFAULT_SSH_PORT
    sshForm.username = target.username || ''
    sshForm.sudoEnabled = Boolean(target.sudo_enabled)
    syncingSavedHost.value = false
  }

  function applyScanResponse(data) {
    scanResult.value = data
    applyTarget(responseTarget(data))
    hostFingerprint.value = data?.provider?.host_fingerprint || data?.capabilities?.host_fingerprint || ''
    selectedGpuIndexes.value = data.success ? data.gpus.map((gpu) => Number(gpu.index)) : []
    feedback.value = { tone: data.success ? 'ok' : 'warning', text: data.message || (data.success ? '扫描完成，已更新候选硬件列表。' : '扫描失败') }
    if (data.success) {
      activeStage.value = 'hardware'
    }
  }

  async function refreshContext() {
    const { data } = await getImportContext()
    store.setImportContext(data)
    applyTarget({ provider_type: data?.provider_type || (data?.source_mode === 'remote' ? 'http_remote' : 'http_local'), label: data?.agent_label || '', agent_url: data?.agent_url || '' })
    selectedGpuIndexes.value = (data?.imported_gpu_indexes || []).map((value) => Number(value))
  }

  async function refreshSavedHosts(scope = savedHosts.scope.value) {
    try {
      await savedHosts.loadHosts(scope)
    } catch {}
  }

  async function scanTarget(payload, host = null) {
    scanBusy.value = true
    feedback.value = null
    try {
      const { data } = await scanImportContext(payload)
      applyScanResponse(data)
    } catch (error) {
      clearScanState(scanResult, selectedGpuIndexes)
      const result = resolveSavedHostScanFailure({
        detail: errorDetail(error, '扫描失败'),
        host,
      })
      if (result.shouldRecoverSavedHost) {
        applySavedHostRecovery({
          host,
          feedbackText: result.feedbackText,
          applyTarget,
          sshForm,
          scanResult,
          selectedGpuIndexes,
          activeStage,
          feedback,
          selectedSavedHostId,
        })
      } else {
        feedback.value = { tone: 'error', text: result.feedbackText }
      }
    } finally {
      scanBusy.value = false
    }
  }

  async function handleScan() {
    selectedSavedHostId.value = null
    await scanTarget(payloadBase())
  }

  async function handleSavedHostScan(hostId) {
    const host = findSavedHost(savedHosts.hosts.value, hostId)
    selectedSavedHostId.value = Number(hostId)
    const result = resolveSavedHostScanFailure({ host })
    if (result.shouldRecoverSavedHost && host) {
      applySavedHostRecovery({
        host,
        feedbackText: result.feedbackText,
        applyTarget,
        sshForm,
        scanResult,
        selectedGpuIndexes,
        activeStage,
        feedback,
        selectedSavedHostId,
      })
      return
    }
    await scanTarget(payloadBase(), host)
  }

  function handleSavedHostEdit(hostId) {
    const host = findSavedHost(savedHosts.hosts.value, hostId)
    if (!host) return
    applySavedHostRecovery({
      host,
      feedbackText: '已载入主机记录，请补充密码或私钥后重新扫描。',
      applyTarget,
      sshForm,
      scanResult,
      selectedGpuIndexes,
      activeStage,
      feedback,
      selectedSavedHostId,
    })
  }

  async function handleDeleteSavedHost(hostId) {
    if (selectedSavedHostId.value === Number(hostId)) {
      selectedSavedHostId.value = null
    }
    await savedHosts.deleteHost(hostId)
  }

  async function handleImport() {
    importBusy.value = true
    feedback.value = null
    try {
      const { data } = await commitImportContext({
        ...payloadBase(),
        gpu_indexes: selectedGpuIndexes.value,
      })
      store.setImportContext(data.import_context)
      store.setWorkspaceReady(true)
      await refreshSavedHosts()
      await router.replace('/')
    } catch (error) {
      const host = findSavedHost(savedHosts.hosts.value, selectedSavedHostId.value)
      const result = resolveSavedHostScanFailure({
        detail: errorDetail(error, '导入失败'),
        host,
      })
      if (result.shouldRecoverSavedHost && host) {
        applySavedHostRecovery({
          host,
          feedbackText: result.feedbackText,
          applyTarget,
          sshForm,
          scanResult,
          selectedGpuIndexes,
          activeStage,
          feedback,
          selectedSavedHostId,
        })
      } else {
        feedback.value = { tone: 'error', text: result.feedbackText }
        activeStage.value = 'selection'
      }
    } finally {
      importBusy.value = false
    }
  }

  watch([providerType, agentUrl, agentLabel, authType], () => {
    if (syncingSavedHost.value) return
    selectedSavedHostId.value = null
  })
  watch(() => sshForm.sudoEnabled, (enabled) => {
    if (!enabled) sshForm.sudoPassword = ''
  })
  watch([() => sshForm.host, () => sshForm.port, () => sshForm.username], () => {
    if (syncingSavedHost.value) return
    selectedSavedHostId.value = null
  })
  watch(authType, (value) => {
    if (value === 'password') {
      sshForm.privateKey = ''
      sshForm.privateKeyPassphrase = ''
      return
    }
    sshForm.password = ''
  })

  onMounted(() => {
    void refreshContext().catch(() => {})
    void refreshSavedHosts()
  })

  return {
    activeStage, agentLabel, agentUrl, authType, canSubmitImport, canViewAllSavedHosts, connectionSummary, currentAgentUrl,
    feedback, footerMessage, heroDescription, heroTitle, hostFingerprint, importBusy, providerType,
    savedHostDeleteBusyId: savedHosts.deletingId,
    savedHostErrorText: savedHosts.errorText,
    savedHostList: savedHosts.hosts,
    savedHostLoading: savedHosts.loading,
    savedHostScope: savedHosts.scope,
    scanBusy, scanResult, selectedGpuIndexes, selectedSavedHostId, sidebarScopeSummary, sidebarSelectedSummary, sshForm,
    tabs: IMPORT_STAGE_TABS,
    handleDeleteSavedHost, handleImport, handleSavedHostEdit, handleSavedHostScan, handleScan, refreshSavedHosts,
  }
}

import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { healthCheck, resetImportContext } from '../services/api.js'
import { formatImportSourceLabel, formatImportedGpuLabel, hasValidImportContext } from '../lib/importContext.js'
import { useAppStore } from '../stores/app.js'
import { useAuthStore } from '../stores/auth.js'
import { useWebSocket } from './useWebSocket.js'

const UPDATE_NOTICE_OK_MS = 4200
const UPDATE_NOTICE_ERROR_MS = 6500
const WORKSPACE_REFRESH_MS = 15000
const HOME_ROUTE = '/'
const IMPORT_ROUTE = '/import'

const NAV_ITEMS = Object.freeze([
  { path: '/', label: '总览', icon: '览', desc: '本次导入 GPU 总览', group: 'governance' },
  { path: '/governance/actions', matchPrefix: '/governance', label: '治理', icon: '治', desc: '统一治理入口与三段工作流', group: 'governance' },
  { path: '/energy', label: '能耗', icon: '能', desc: '节能复盘与测算', group: 'analysis' },
  { path: '/monitor', label: '观察', icon: '观', desc: '画像与过程观察', group: 'analysis' },
  { path: '/alerts', label: '告警', icon: '警', desc: '风险台与异常确认', group: 'analysis' },
  { path: '/ai', label: '智能', icon: '智', desc: 'AI 解释与问答', group: 'support' },
])

const GROUP_META = Object.freeze({
  governance: {
    eyebrow: 'Governance Workspace',
    desc: '预算、调度、风险和任务治理在同一工作区内收口。',
  },
  analysis: {
    eyebrow: 'Analysis Workspace',
    desc: '围绕已导入 GPU 做观测、复盘和风险回看。',
  },
  support: {
    eyebrow: 'Support Workspace',
    desc: '把 AI 辅助、解释和建议放在同一层完成。',
  },
})

function baseAppInfo() {
  const webDev = Boolean(import.meta.env.DEV)
  return {
    name: 'GPU 共享治理平台',
    version: '',
    updateSupported: false,
    releasesUrl: '',
    runtimeMode: webDev ? 'web-dev' : 'web-release',
    runtimeModeLabel: webDev ? '网页开发模式' : '网页正式模式',
    connectionMode: 'local',
    connectionModeLabel: '导入模式待识别',
    agentSourceLabel: '由导入层决定（本机 Agent / 远程 Agent / SSH Linux）',
  }
}

function compactSidebarModeLabel(label = '') {
  if (label.includes('SSH Linux')) return 'SSH Linux'
  if (label.includes('远程 Agent')) return '远程 Agent'
  if (label.includes('本机 Agent')) return '本机 Agent'
  return '导入待确认'
}

function getDesktopShellBridge() {
  if (typeof window === 'undefined') return null
  return window.desktopShell || null
}

export function useConsoleShell() {
  const route = useRoute()
  const router = useRouter()
  const store = useAppStore()
  const auth = useAuthStore()
  const appInfo = ref(baseAppInfo())
  const sidebarCollapsed = ref(false)
  const updateState = ref(null)
  const updateBusy = ref(false)
  const switchServerBusy = ref(false)
  const closeDialog = ref(null)
  const closeBusy = ref(false)
  let workspaceTimer = null
  let updateStateTimer = null
  let removeCloseListener = null

  const { connected: wsConnected, connect, disconnect } = useWebSocket({
    onRealtimeMessage: (payload) => {
      store.applyRealtimePayload(payload)
    },
    onConnectionChange: (connected) => {
      store.wsConnected = connected
    },
    getToken: () => auth.token,
    shouldReconnect: () => auth.isAuthenticated && !auth.mustChangePassword,
  })

  const isDesktop = computed(() => typeof window !== 'undefined' && Boolean(window.desktopShell))
  const workspaceLocked = computed(() => store.workspaceStatusChecked && !store.workspaceReady)
  const activeNavItem = computed(() =>
    NAV_ITEMS.find((item) => {
      const prefix = item.matchPrefix || item.path
      return route.path === item.path || (prefix !== HOME_ROUTE && route.path.startsWith(prefix))
    }) || NAV_ITEMS[0])
  const currentWorkspaceMeta = computed(() => GROUP_META[activeNavItem.value.group] || GROUP_META.governance)
  const sidebarSummary = computed(() => {
    const modeLabel = compactSidebarModeLabel(appInfo.value.connectionModeLabel || '')
    const importedLabel = formatImportedGpuLabel(store.importContext?.imported_gpu_indexes || [])
    return `${modeLabel} · ${importedLabel}`
  })
  const chromeMetrics = computed(() => [
    { label: '导入 GPU', value: `${store.gpus.length}` },
    { label: '活跃任务', value: `${store.processes.length}` },
    { label: '累计告警', value: `${store.alerts.length}` },
  ])
  const runtimeBanner = computed(() => {
    const status = store.runtimeStatus?.status || 'idle'
    if (status === 'reconnecting') {
      const failures = Number(store.runtimeStatus?.reconnectFailures || 0)
      return failures > 0
        ? `当前导入目标正在自动重连，已尝试 ${failures} 次。`
        : '当前导入目标正在自动重连，请稍候。'
    }
    if (status === 'invalid') {
      return '当前导入目标已失效，需要重新进入导入层确认连接与选卡范围。'
    }
    return ''
  })

  function applyConnectionSummary(connection, importContext) {
    const connectionMode = importContext?.source_mode || connection?.mode || appInfo.value.connectionMode || 'local'
    const importedLabel = formatImportedGpuLabel(importContext?.imported_gpu_indexes || [])
    const scopeReady = hasValidImportContext(importContext)
    const agentLabel = importContext?.agent_label || connection?.agent_label || '本机 Agent'
    const providerLabel = formatImportSourceLabel(importContext || connection)
    appInfo.value = {
      ...appInfo.value,
      connectionMode,
      connectionModeLabel: scopeReady ? providerLabel : `${providerLabel}（待确认）`,
      agentSourceLabel: scopeReady ? `${agentLabel} · ${importedLabel}` : importedLabel,
    }
  }

  async function syncAppInfo() {
    const shellBridge = getDesktopShellBridge()
    if (!shellBridge?.getAppInfo) {
      const nextAppInfo = {
        ...baseAppInfo(),
        version: appInfo.value.version || '',
        updateSupported: Boolean(appInfo.value.updateSupported),
        connectionMode: appInfo.value.connectionMode || 'local',
        connectionModeLabel: appInfo.value.connectionModeLabel || '导入模式待识别',
        agentSourceLabel: appInfo.value.agentSourceLabel || '由导入层决定（本机 Agent / 远程 Agent / SSH Linux）',
      }
      appInfo.value = nextAppInfo
      return
    }
    try {
      const nextAppInfo = {
        ...baseAppInfo(),
        ...await shellBridge.getAppInfo(),
      }
      appInfo.value = nextAppInfo
      if (!nextAppInfo.updateSupported) {
        clearUpdateNotice()
      }
    } catch {}
  }

  function clearUpdateNotice() {
    clearTimeout(updateStateTimer)
    updateStateTimer = null
    updateState.value = null
  }

  function applyUpdateNotice(nextState) {
    clearUpdateNotice()
    if (!appInfo.value.updateSupported) {
      return
    }
    updateState.value = nextState
    if (!nextState || (nextState.ok && nextState.available)) return
    updateStateTimer = setTimeout(() => {
      updateState.value = null
      updateStateTimer = null
    }, nextState.ok ? UPDATE_NOTICE_OK_MS : UPDATE_NOTICE_ERROR_MS)
  }

  async function refreshWorkspaceStatus() {
    try {
      const { data } = await healthCheck()
      store.applyRealtimePayload(data || {})
      store.setWorkspaceReady(Boolean(data?.workspace_ready))
      store.markWorkspaceStatusChecked(true)
      applyConnectionSummary(data?.connection, data?.import_context)
    } catch {
      store.markWorkspaceStatusChecked(true)
      store.applyRealtimePayload({
        runtime: {
          ...store.runtimeStatus,
          status: store.runtimeStatus?.status === 'invalid' ? 'invalid' : 'reconnecting',
          connected: false,
        },
      })
    } finally {
      if (!store.workspaceReady && route.path !== IMPORT_ROUTE) {
        await router.replace(IMPORT_ROUTE)
      }
      void syncAppInfo()
    }
  }

  function navigateTo(item) {
    if (workspaceLocked.value && item.path !== HOME_ROUTE) {
      void router.replace(IMPORT_ROUTE)
      return
    }
    if (route.path !== item.path) {
      void router.push(item.path)
    }
  }

  function toggleSidebarCollapsed() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  async function switchServer() {
    if (switchServerBusy.value) return
    if (typeof window !== 'undefined') {
      const confirmed = window.confirm('切换服务器会退出当前导入范围，并返回导入层重新选择机器和 GPU。是否继续？')
      if (!confirmed) return
    }

    switchServerBusy.value = true
    try {
      const { data } = await resetImportContext()
      store.setImportContext(data?.import_context || null)
      store.setWorkspaceReady(false)
      store.markWorkspaceStatusChecked(true)
      await router.replace(IMPORT_ROUTE)
    } catch (error) {
      console.error('Failed to switch server', error)
    } finally {
      switchServerBusy.value = false
    }
  }

  async function loadDesktopInfo() {
    const shellBridge = getDesktopShellBridge()
    await syncAppInfo()
    if (!shellBridge?.onCloseRequest) return
    removeCloseListener?.()
    removeCloseListener = shellBridge.onCloseRequest((payload) => {
      closeBusy.value = false
      closeDialog.value = payload || {
        title: '关闭桌面平台',
        message: '你可以选择退出并关闭服务，或者最小化到后台继续运行。',
        detail: '最小化到后台会保留桌面程序和本机托管服务。',
      }
    })
  }

  async function checkForUpdates() {
    const shellBridge = getDesktopShellBridge()
    if (!appInfo.value.updateSupported || !shellBridge?.checkForUpdates) return
    updateBusy.value = true
    try {
      applyUpdateNotice(await shellBridge.checkForUpdates())
    } catch (error) {
      applyUpdateNotice({
        ok: false,
        error: error instanceof Error ? error.message : String(error),
      })
    } finally {
      updateBusy.value = false
    }
  }

  async function openUpdateTarget(url) {
    const target = String(url || '').trim()
    if (!target) return
    const shellBridge = getDesktopShellBridge()
    if (shellBridge?.openExternal) {
      await shellBridge.openExternal(target)
      return
    }
    window.open(target, '_blank', 'noopener,noreferrer')
  }

  async function resolveCloseAction(action) {
    const shellBridge = getDesktopShellBridge()
    closeBusy.value = true
    try {
      if (shellBridge?.resolveCloseRequest) {
        await shellBridge.resolveCloseRequest(action)
      }
      closeDialog.value = null
    } finally {
      closeBusy.value = false
    }
  }

  watch(
    () => auth.token,
    (nextToken) => {
      if (nextToken && !auth.mustChangePassword) {
        connect()
        return
      }
      disconnect()
    },
    { immediate: true },
  )

  onMounted(() => {
    void refreshWorkspaceStatus()
    workspaceTimer = setInterval(() => {
      void refreshWorkspaceStatus()
    }, WORKSPACE_REFRESH_MS)
    void loadDesktopInfo()
  })

  onUnmounted(() => {
    clearInterval(workspaceTimer)
    clearTimeout(updateStateTimer)
    removeCloseListener?.()
    disconnect()
  })

  return {
    appInfo,
    activeNavItem,
    checkForUpdates,
    chromeMetrics,
    clearUpdateNotice,
    closeBusy,
    closeDialog,
    currentWorkspaceMeta,
    isDesktop,
    navItems: NAV_ITEMS,
    navigateTo,
    openUpdateTarget,
    resolveCloseAction,
    route,
    runtimeBanner,
    sidebarSummary,
    sidebarCollapsed,
    switchServer,
    switchServerBusy,
    toggleSidebarCollapsed,
    updateBusy,
    updateState,
    workspaceLocked,
    wsConnected,
  }
}

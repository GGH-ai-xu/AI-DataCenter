/**
 * Pinia全局状态管理
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  buildDashboardSummary,
  buildTaskSummary,
  normalizeProcesses,
} from '../lib/realtimeSummaries.js'
import { hasValidImportContext } from '../lib/importContext.js'

const ALERT_LIMIT = 100

function requestState() {
  return {
    loading: false,
    error: null,
    lastUpdatedAt: 0,
    inFlight: false,
    data: null,
  }
}

function createDomainState() {
  return {
    dashboard: {
      governance: requestState(),
      connection: requestState(),
      desktop: requestState(),
    },
    scheduler: {
      status: requestState(),
      carbon: requestState(),
      audit: requestState(),
      evaluation: requestState(),
    },
    tasks: {
      governance: requestState(),
    },
    monitor: {
      system: requestState(),
      training: requestState(),
      users: requestState(),
      timeline: requestState(),
    },
    energy: {
      overview: requestState(),
      prediction: requestState(),
      ai: requestState(),
    },
  }
}

function normalizeRuntimeStatus(payload = null) {
  return {
    status: payload?.status || 'idle',
    connected: Boolean(payload?.connected),
    providerType: payload?.provider_type || payload?.providerType || '',
    lastError: payload?.last_error || payload?.lastError || '',
    reconnectFailures: Number(payload?.reconnect_failures || payload?.reconnectFailures || 0),
  }
}

export const useAppStore = defineStore('app', () => {
  const gpus = ref([])
  const system = ref(null)
  const processes = ref([])
  const alerts = ref([])
  const wsConnected = ref(false)
  const workspaceReady = ref(false)
  const workspaceStatusChecked = ref(false)
  const importContext = ref(null)
  const runtimeStatus = ref(normalizeRuntimeStatus())
  const dataSourceStatus = ref({ connected: false, gpu_count: 0 })
  const domains = ref(createDomainState())

  const dataSourceLabel = computed(() => {
    if (!dataSourceStatus.value.connected) {
      return { text: '数据源离线', level: 'offline', color: '#999' }
    }
    if ((dataSourceStatus.value.gpu_count || 0) <= 0) {
      return { text: '无真实GPU', level: 'warning', color: '#B8860B' }
    }
    return { text: '真实采集', level: 'real', color: '#2E8B57' }
  })
  const schedulerAuto = ref(false)
  const timePeriod = ref('normal')
  const totalPower = computed(() =>
    gpus.value.reduce((sum, g) => sum + (g.power_usage || 0), 0)
  )

  const avgTemperature = computed(() => {
    if (!gpus.value.length) return 0
    return Math.round(gpus.value.reduce((sum, g) => sum + (g.temperature || 0), 0) / gpus.value.length)
  })

  const totalMemoryUsed = computed(() =>
    gpus.value.reduce((sum, g) => sum + (g.memory_used || 0), 0)
  )

  const totalMemoryTotal = computed(() =>
    gpus.value.reduce((sum, g) => sum + (g.memory_total || 0), 0)
  )

  const avgUtilization = computed(() => {
    if (!gpus.value.length) return 0
    return Math.round(gpus.value.reduce((sum, g) => sum + (g.gpu_utilization || 0), 0) / gpus.value.length)
  })

  const normalizedProcesses = computed(() => normalizeProcesses(processes.value))
  const dashboardSummary = computed(() => buildDashboardSummary({
    gpus: gpus.value,
    processes: normalizedProcesses.value,
    alerts: alerts.value,
  }))
  const taskSummary = computed(() => buildTaskSummary(normalizedProcesses.value))

  function domainEntry(section, key = null) {
    return key ? domains.value[section][key] : domains.value[section]
  }

  function beginDomainRequest(section, key = null) {
    Object.assign(domainEntry(section, key), {
      loading: true,
      error: null,
      inFlight: true,
    })
  }

  function completeDomainRequest(section, key = null, data = null, lastUpdatedAt = Date.now()) {
    Object.assign(domainEntry(section, key), {
      loading: false,
      error: null,
      inFlight: false,
      lastUpdatedAt,
      data,
    })
  }

  function failDomainRequest(section, key = null, error) {
    Object.assign(domainEntry(section, key), {
      loading: false,
      error: error instanceof Error ? error.message : String(error),
      inFlight: false,
    })
  }

  function replaceProcesses(nextProcesses) {
    processes.value = nextProcesses || []
  }

  function applyRealtimePayload(data) {
    const hasWorkspaceState = Object.prototype.hasOwnProperty.call(data, 'import_context')
      || Object.prototype.hasOwnProperty.call(data, 'workspace_ready')
    if (Object.prototype.hasOwnProperty.call(data, 'import_context')) {
      setImportContext(data.import_context)
    }
    if (Object.prototype.hasOwnProperty.call(data, 'workspace_ready')) {
      setWorkspaceReady(data.workspace_ready)
    }
    if (Object.prototype.hasOwnProperty.call(data, 'runtime')) {
      runtimeStatus.value = normalizeRuntimeStatus(data.runtime)
    } else if (Object.prototype.hasOwnProperty.call(data, 'connection')) {
      runtimeStatus.value = normalizeRuntimeStatus(data.connection)
    }
    if (data.gpus) {
      gpus.value = data.gpus
      dataSourceStatus.value.connected = true
      dataSourceStatus.value.gpu_count = data.gpus.length
    }
    if (data.system) system.value = data.system
    if (data.processes) processes.value = data.processes
    if (data.alerts?.length) {
      alerts.value = [...data.alerts, ...alerts.value].slice(0, ALERT_LIMIT)
    }
    if (hasWorkspaceState) {
      workspaceStatusChecked.value = true
    }
  }

  function updateFromWs(data) {
    applyRealtimePayload(data)
  }

  function setWorkspaceReady(value) {
    workspaceReady.value = Boolean(value)
  }

  function setImportContext(value) {
    importContext.value = value || null
    workspaceReady.value = hasValidImportContext(importContext.value)
  }

  function markWorkspaceStatusChecked(value = true) {
    workspaceStatusChecked.value = Boolean(value)
  }

  function resetRuntimeState() {
    gpus.value = []
    system.value = null
    processes.value = []
    alerts.value = []
    wsConnected.value = false
    workspaceReady.value = false
    workspaceStatusChecked.value = false
    importContext.value = null
    runtimeStatus.value = normalizeRuntimeStatus()
    dataSourceStatus.value = { connected: false, gpu_count: 0 }
    domains.value = createDomainState()
  }

  return {
    gpus, system, processes, alerts, wsConnected, workspaceReady, workspaceStatusChecked,
    importContext, runtimeStatus,
    schedulerAuto, timePeriod,
    dataSourceStatus, dataSourceLabel, domains,
    totalPower, avgTemperature, totalMemoryUsed, totalMemoryTotal, avgUtilization,
    normalizedProcesses, dashboardSummary, taskSummary,
    beginDomainRequest, completeDomainRequest, failDomainRequest,
    replaceProcesses, applyRealtimePayload, updateFromWs, setWorkspaceReady, setImportContext,
    markWorkspaceStatusChecked, resetRuntimeState,
  }
})

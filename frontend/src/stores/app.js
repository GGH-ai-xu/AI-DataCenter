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

export const useAppStore = defineStore('app', () => {
  const gpus = ref([])
  const system = ref(null)
  const processes = ref([])
  const alerts = ref([])
  const wsConnected = ref(false)
  const workspaceReady = ref(false)
  const dataSourceStatus = ref({ connected: false, simulated: false, gpu_count: 0 })
  const domains = ref(createDomainState())

  const dataSourceLabel = computed(() => {
    if (!dataSourceStatus.value.connected) {
      return { text: '数据源离线', level: 'offline', color: '#999' }
    }
    if (dataSourceStatus.value.simulated) {
      return { text: '模拟演示', level: 'simulated', color: '#B8860B' }
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
    if (data.gpus) {
      gpus.value = data.gpus
      dataSourceStatus.value.connected = true
      dataSourceStatus.value.gpu_count = data.gpus.length
    }
    if (data.agent_info?.simulated !== undefined) {
      dataSourceStatus.value.simulated = Boolean(data.agent_info.simulated)
    }
    if (data.system) system.value = data.system
    if (data.processes) processes.value = data.processes
    if (data.alerts?.length) {
      alerts.value = [...data.alerts, ...alerts.value].slice(0, ALERT_LIMIT)
    }
  }

  function updateFromWs(data) {
    applyRealtimePayload(data)
  }

  function setWorkspaceReady(value) {
    workspaceReady.value = Boolean(value)
  }

  return {
    gpus, system, processes, alerts, wsConnected, workspaceReady,
    schedulerAuto, timePeriod,
    dataSourceStatus, dataSourceLabel, domains,
    totalPower, avgTemperature, totalMemoryUsed, totalMemoryTotal, avgUtilization,
    normalizedProcesses, dashboardSummary, taskSummary,
    beginDomainRequest, completeDomainRequest, failDomainRequest,
    replaceProcesses, applyRealtimePayload, updateFromWs, setWorkspaceReady,
  }
})

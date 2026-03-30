/**
 * Pinia全局状态管理
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAppStore = defineStore('app', () => {
  // 实时数据
  const gpus = ref([])
  const system = ref(null)
  const processes = ref([])
  const alerts = ref([])
  const wsConnected = ref(false)
  const workspaceReady = ref(false)

  // 数据源可信度状态
  const dataSourceStatus = ref({ connected: false, simulated: false, gpu_count: 0 })

  const dataSourceLabel = computed(() => {
    if (!dataSourceStatus.value.connected) {
      return { text: '数据源离线', level: 'offline', color: '#999' }
    }
    if (dataSourceStatus.value.simulated) {
      return { text: '模拟演示', level: 'simulated', color: '#B8860B' }
    }
    return { text: '真实采集', level: 'real', color: '#2E8B57' }
  })

  // 调度器状态
  const schedulerAuto = ref(false)
  const timePeriod = ref('normal')

  // 统计计算
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

  function updateFromWs(data) {
    if (data.gpus) {
      gpus.value = data.gpus
      dataSourceStatus.value.connected = true
      dataSourceStatus.value.gpu_count = data.gpus.length
    }
    if (data.system) system.value = data.system
    if (data.processes) processes.value = data.processes
    if (data.alerts?.length) {
      alerts.value = [...data.alerts, ...alerts.value].slice(0, 100)
    }
  }

  function setWorkspaceReady(value) {
    workspaceReady.value = Boolean(value)
  }

  return {
    gpus, system, processes, alerts, wsConnected, workspaceReady,
    schedulerAuto, timePeriod,
    dataSourceStatus, dataSourceLabel,
    totalPower, avgTemperature, totalMemoryUsed, totalMemoryTotal, avgUtilization,
    updateFromWs, setWorkspaceReady,
  }
})

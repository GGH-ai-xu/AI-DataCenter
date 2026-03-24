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
    if (data.gpus) gpus.value = data.gpus
    if (data.system) system.value = data.system
    if (data.processes) processes.value = data.processes
    if (data.alerts?.length) {
      alerts.value = [...data.alerts, ...alerts.value].slice(0, 100)
    }
  }

  return {
    gpus, system, processes, alerts, wsConnected,
    schedulerAuto, timePeriod,
    totalPower, avgTemperature, totalMemoryUsed, totalMemoryTotal, avgUtilization,
    updateFromWs,
  }
})

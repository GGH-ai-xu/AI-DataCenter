import {
  getAiAnomalies,
  getAiInsight,
  getCarbonData,
  getEnergyMetrics,
  getGpuEfficiency,
  getHistoryComparison,
  getPowerPrediction,
  getScheduleHistory,
  getSchedulerStatus,
  getTimeBreakdown,
  healthCheck,
} from '../services/api.js'
import { useDomainRefresh } from './useDomainRefresh.js'

async function loadOverviewData() {
  const [
    { data: metrics },
    { data: breakdown },
    { data: efficiency },
    { data: scheduler },
    { data: carbon },
    { data: health },
  ] = await Promise.all([
    getEnergyMetrics(24),
    getTimeBreakdown(24),
    getGpuEfficiency(),
    getSchedulerStatus(),
    getCarbonData(24),
    healthCheck(),
  ])

  return { metrics, breakdown, efficiency, scheduler, carbon, health }
}

async function loadPredictionData() {
  const [
    { data: prediction },
    { data: scheduleHistory },
    { data: historyComparison },
  ] = await Promise.all([
    getPowerPrediction(24),
    getScheduleHistory(72),
    getHistoryComparison(72),
  ])

  return { prediction, scheduleHistory, historyComparison }
}

async function loadAiData() {
  const { data: health } = await healthCheck()
  if (!health?.llm_available) {
    return { health, insight: null, anomalies: null }
  }

  const [{ data: insight }, { data: anomalies }] = await Promise.all([
    getAiInsight(),
    getAiAnomalies(),
  ])

  return { health, insight, anomalies }
}

function createEnergyLoader(activeTab) {
  return async () => {
    const currentTab = activeTab.value
    if (currentTab === 'prediction') {
      return loadPredictionData()
    }
    if (currentTab === 'ai') {
      return loadAiData()
    }
    return loadOverviewData()
  }
}

export function useEnergyData(activeTab, options = {}) {
  return useDomainRefresh({
    section: 'energy',
    key: () => activeTab.value,
    intervalMs: 30000,
    staleTime: 15000,
    enabled: () => Boolean(activeTab.value),
    loader: createEnergyLoader(activeTab),
    applyData: (payload, result, key) => {
      options.onData?.(key, payload, result)
    },
  })
}

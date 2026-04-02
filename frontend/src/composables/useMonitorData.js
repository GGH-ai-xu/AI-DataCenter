import {
  getSystemDetail,
  getTaskHistory,
  getTrainingProgress,
  getUserStats,
} from '../services/api.js'
import { useDomainRefresh } from './useDomainRefresh.js'

function createMonitorLoader(activeTab, timelineHours) {
  return async () => {
    const currentTab = activeTab.value
    if (currentTab === 'system') {
      return (await getSystemDetail()).data
    }
    if (currentTab === 'training') {
      return (await getTrainingProgress()).data.training || []
    }
    if (currentTab === 'users') {
      return (await getUserStats()).data.users || []
    }
    return (await getTaskHistory(timelineHours.value)).data.timeline || []
  }
}

export function useMonitorData(activeTab, timelineHours, options = {}) {
  return useDomainRefresh({
    section: 'monitor',
    key: () => activeTab.value,
    intervalMs: 10000,
    staleTime: 10000,
    enabled: () => Boolean(activeTab.value),
    loader: createMonitorLoader(activeTab, timelineHours),
    applyData: (payload, result, key) => {
      options.onData?.(key, payload, result)
    },
  })
}

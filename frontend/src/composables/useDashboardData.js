import { computed } from 'vue'
import {
  getFairnessGovernance,
  getSchedulerStatus,
  getSystemSelfCheck,
  healthCheck,
} from '../services/api.js'
import { createDashboardLoaders } from '../lib/dashboardLoaders.js'
import { useAppStore } from '../stores/app.js'
import { useDomainRefresh } from './useDomainRefresh.js'

export function useDashboardData(options = {}) {
  const store = useAppStore()
  const activeTab = options.activeTab || null
  const refreshEnabled = (tabKey) => !activeTab || activeTab.value === tabKey
  const loaders = createDashboardLoaders({
    getSchedulerStatus,
    healthCheck,
    getFairnessGovernance,
    getSystemSelfCheck,
  })

  const overviewRefresh = useDomainRefresh({
    section: 'dashboard',
    key: 'overview',
    intervalMs: 8000,
    staleTime: 4000,
    enabled: () => refreshEnabled('overview'),
    loader: loaders.loadOverviewBundle,
    applyData: (payload) => {
      options.onOverviewData?.(payload)
      options.onGovernanceData?.(payload)
    },
  })

  const healthRefresh = useDomainRefresh({
    section: 'dashboard',
    key: 'health',
    intervalMs: 8000,
    staleTime: 4000,
    enabled: () => refreshEnabled('health'),
    loader: loaders.loadHealthBundle,
    applyData: (payload) => {
      options.onHealthData?.(payload)
      options.onGovernanceData?.(payload)
    },
  })

  return {
    dashboardSummary: computed(() => store.dashboardSummary),
    overviewDomain: computed(() => store.domains.dashboard.overview),
    liveDomain: computed(() => store.domains.dashboard.live),
    healthDomain: computed(() => store.domains.dashboard.health),
    refreshOverview: overviewRefresh.refresh,
    refreshHealth: healthRefresh.refresh,
    refreshGovernance: overviewRefresh.refresh,
  }
}

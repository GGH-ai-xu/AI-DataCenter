import { computed } from 'vue'
import {
  getFairnessGovernance,
  getSchedulerStatus,
  getSystemSelfCheck,
  healthCheck,
} from '../services/api.js'
import { useAppStore } from '../stores/app.js'
import { useDomainRefresh } from './useDomainRefresh.js'

async function loadGovernanceBundle() {
  const [{ data: scheduler }, { data: health }, { data: fairness }, { data: selfCheck }] = await Promise.all([
    getSchedulerStatus(),
    healthCheck(),
    getFairnessGovernance(),
    getSystemSelfCheck(),
  ])

  return { scheduler, health, fairness, selfCheck }
}

export function useDashboardData(options = {}) {
  const store = useAppStore()
  const governanceRefresh = useDomainRefresh({
    section: 'dashboard',
    key: 'governance',
    intervalMs: 8000,
    staleTime: 4000,
    loader: loadGovernanceBundle,
    applyData: (payload) => {
      options.onGovernanceData?.(payload)
    },
  })

  return {
    dashboardSummary: computed(() => store.dashboardSummary),
    governanceDomain: computed(() => store.domains.dashboard.governance),
    refreshGovernance: governanceRefresh.refresh,
  }
}

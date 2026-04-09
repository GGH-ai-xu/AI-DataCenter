import { computed } from 'vue'

import {
  getAuditLogs,
  getCarbonBudget,
  getFairnessGovernance,
  getGovernanceRules,
  getScheduleEvaluation,
  getSchedulerStatus,
  getTasks,
} from '../services/api.js'
import { createGovernanceLoaders } from '../lib/governanceLoaders.js'
import { useAppStore } from '../stores/app.js'
import { useDomainRefresh } from './useDomainRefresh.js'

const DEFAULT_ACTIONS = {
  processes: [],
  fairness: {
    overview: {},
    yield_candidates: [],
    recommendations: [],
  },
}

const DEFAULT_POLICIES = {
  scheduler: {},
  carbon: {},
  fairness: {
    users: [],
  },
  rules: [],
}

const DEFAULT_REVIEW = {
  auditLogs: [],
  evaluation: null,
}

export function useGovernanceData(options = {}) {
  const store = useAppStore()
  const activeSection = options.activeSection || null
  const refreshEnabled = (key) => !activeSection || activeSection.value === key
  const loaders = createGovernanceLoaders({
    getTasks,
    getFairnessGovernance,
    getSchedulerStatus,
    getCarbonBudget,
    getGovernanceRules,
    getAuditLogs,
    getScheduleEvaluation,
  })

  const actionsRefresh = useDomainRefresh({
    section: 'governance',
    key: 'actions',
    intervalMs: 12000,
    staleTime: 8000,
    enabled: () => refreshEnabled('actions'),
    loader: loaders.loadActionsBundle,
    applyData: (payload) => {
      store.replaceProcesses(payload.processes)
      options.onActionsData?.(payload)
    },
  })

  const policiesRefresh = useDomainRefresh({
    section: 'governance',
    key: 'policies',
    intervalMs: 20000,
    staleTime: 12000,
    enabled: () => refreshEnabled('policies'),
    loader: loaders.loadPoliciesBundle,
    applyData: (payload) => {
      options.onPoliciesData?.(payload)
    },
  })

  const reviewRefresh = useDomainRefresh({
    section: 'governance',
    key: 'review',
    intervalMs: 30000,
    staleTime: 16000,
    enabled: () => refreshEnabled('review'),
    loader: loaders.loadReviewBundle,
    applyData: (payload) => {
      options.onReviewData?.(payload)
    },
  })

  return {
    actionsDomain: computed(() => store.domains.governance.actions),
    policiesDomain: computed(() => store.domains.governance.policies),
    reviewDomain: computed(() => store.domains.governance.review),
    actionsState: computed(() => store.domains.governance.actions.data || DEFAULT_ACTIONS),
    policiesState: computed(() => store.domains.governance.policies.data || DEFAULT_POLICIES),
    reviewState: computed(() => store.domains.governance.review.data || DEFAULT_REVIEW),
    refreshActions: actionsRefresh.refresh,
    refreshPolicies: policiesRefresh.refresh,
    refreshReview: reviewRefresh.refresh,
  }
}

import { computed, onUnmounted, ref, watch } from 'vue'
import { getFairnessGovernance, getTasks } from '../services/api.js'
import {
  filterProcesses,
  selectVisibleProcesses,
} from '../lib/realtimeSummaries.js'
import { useDomainRefresh } from './useDomainRefresh.js'
import { useAppStore } from '../stores/app.js'

const KEYWORD_DEBOUNCE_MS = 160
const DEFAULT_FAIRNESS_STATE = {
  overview: { fairness_index: 100, level: 'balanced', summary: '当前共享较均衡。' },
  users: [],
  yield_candidates: [],
  recommendations: [],
}

export function useTaskManagerData(keyword, selectedPriority, showAllProcesses) {
  const store = useAppStore()
  const debouncedKeyword = ref('')
  let keywordTimer = null

  watch(keyword, (value) => {
    if (keywordTimer) {
      clearTimeout(keywordTimer)
    }
    keywordTimer = setTimeout(() => {
      debouncedKeyword.value = value
    }, KEYWORD_DEBOUNCE_MS)
  }, { immediate: true })

  onUnmounted(() => {
    if (keywordTimer) {
      clearTimeout(keywordTimer)
    }
  })

  const governanceRefresh = useDomainRefresh({
    section: 'tasks',
    key: 'governance',
    intervalMs: 30000,
    staleTime: 10000,
    loader: async () => {
      const [{ data: taskData }, { data: fairnessData }] = await Promise.all([
        getTasks(),
        getFairnessGovernance(),
      ])
      return {
        processes: taskData?.processes || [],
        fairness: fairnessData || DEFAULT_FAIRNESS_STATE,
      }
    },
    applyData: (payload) => {
      store.replaceProcesses(payload.processes)
    },
  })

  const filteredProcesses = computed(() => filterProcesses(
    store.normalizedProcesses,
    {
      keyword: debouncedKeyword.value,
      priority: selectedPriority.value,
      includeAll: showAllProcesses.value,
    },
  ))
  const visibleProcesses = computed(() => selectVisibleProcesses(
    store.normalizedProcesses,
    showAllProcesses.value,
  ))

  return {
    filteredProcesses,
    visibleProcesses,
    fairnessState: computed(() => store.domains.tasks.governance.data?.fairness || DEFAULT_FAIRNESS_STATE),
    taskSummary: computed(() => store.taskSummary),
    refreshTaskGovernance: governanceRefresh.refresh,
  }
}

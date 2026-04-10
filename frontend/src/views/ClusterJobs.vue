<script setup>
import { computed, onMounted, ref } from 'vue'

import ClusterAllocationPanel from '../components/cluster/ClusterAllocationPanel.vue'
import ClusterJobLedger from '../components/cluster/ClusterJobLedger.vue'
import ClusterQueueBoard from '../components/cluster/ClusterQueueBoard.vue'
import { buildClusterConsoleModel } from '../lib/clusterConsoleModels.js'
import {
  listClusterAllocations,
  listClusterJobs,
  listClusterQueues,
} from '../services/api.js'
import { useAuthStore } from '../stores/auth.js'

const loading = ref(false)
const submitBusy = ref(false)
const errorMessage = ref('')
const submitAnchor = ref(null)
const auth = useAuthStore()
const payload = ref({
  queues: [],
  jobs: [],
  allocations: [],
})

const viewModel = computed(() => buildClusterConsoleModel(payload.value))

const props = defineProps({
  control: {
    type: Object,
    default: () => ({}),
  },
})

async function refresh() {
  loading.value = true
  errorMessage.value = ''
  try {
    const [queues, jobs, allocations] = await Promise.all([
      listClusterQueues(),
      listClusterJobs(),
      listClusterAllocations(),
    ])
    payload.value = {
      queues: queues.data?.queues || [],
      jobs: jobs.data?.jobs || [],
      allocations: allocations.data?.allocations || [],
    }
  } catch (error) {
    errorMessage.value = error?.response?.data?.detail || '集群控制台数据加载失败'
  } finally {
    loading.value = false
  }
}

async function handleSubmitJob(jobPayload) {
  submitBusy.value = true
  errorMessage.value = ''
  try {
    await props.control.submitBuiltinCommand?.(
      'job.submit',
      jobPayload,
      { section: 'cluster' },
    )
    await refresh()
  } catch (error) {
    errorMessage.value = error?.response?.data?.detail || '作业提交失败'
  } finally {
    submitBusy.value = false
  }
}

function jumpToSubmit() {
  submitAnchor.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function openClusterDrawer() {
  props.control.openDrawer?.('cluster')
}

onMounted(() => {
  void refresh()
})
</script>

<template>
  <div class="cluster-console-view">
    <div class="cluster-console-view__toolbar">
      <button type="button" class="btn-tech btn-tech--primary" @click="jumpToSubmit">
        提交作业
      </button>
      <button type="button" class="btn-tech" @click="openClusterDrawer">
        高级集群操作
      </button>
    </div>

    <div v-if="errorMessage" class="tech-card cluster-console-view__notice cluster-console-view__notice--warning">
      {{ errorMessage }}
    </div>
    <div v-else-if="loading" class="tech-card cluster-console-view__notice">
      正在加载集群队列、作业与 allocation 快照...
    </div>

    <div class="cluster-console-view__top">
      <ClusterQueueBoard :queues="viewModel.queues" />
      <ClusterAllocationPanel :allocations-by-node="viewModel.allocationsByNode" />
    </div>

    <div ref="submitAnchor">
      <ClusterJobLedger
        :jobs="viewModel.jobs"
        :submitter-id="auth.currentUser?.username || 'console-user'"
        :submit-busy="submitBusy"
        @submit="handleSubmitJob"
      />
    </div>
  </div>
</template>

<style scoped>
.cluster-console-view {
  display: grid;
  gap: 16px;
}

.cluster-console-view__toolbar {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.cluster-console-view__top {
  display: grid;
  grid-template-columns: minmax(280px, 0.95fr) minmax(0, 1.05fr);
  gap: 16px;
}

.cluster-console-view__notice {
  padding: 14px 16px;
  color: var(--text-secondary);
}

.cluster-console-view__notice--warning {
  border-color: var(--state-warning-border);
  background: var(--state-warning-bg);
  color: var(--state-warning-text);
}

@media (max-width: 1100px) {
  .cluster-console-view__top {
    grid-template-columns: 1fr;
  }

  .cluster-console-view__toolbar {
    justify-content: stretch;
    flex-wrap: wrap;
  }
}
</style>

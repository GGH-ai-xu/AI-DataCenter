<script setup>
import { computed, onMounted, ref } from 'vue'
import ClusterAllocationPanel from '../components/cluster/ClusterAllocationPanel.vue'
import ClusterConsoleToolbar from '../components/cluster/ClusterConsoleToolbar.vue'
import ClusterJobLedger from '../components/cluster/ClusterJobLedger.vue'
import ClusterQueueBoard from '../components/cluster/ClusterQueueBoard.vue'
import {
  actionBusyKey,
  capabilityForJobAction,
  confirmJobAction,
  jobActionLabel,
} from '../lib/clusterConsoleActions.js'
import { buildClusterConsoleModel } from '../lib/clusterConsoleModels.js'
import {
  configureClusterController,
  getClusterControllerStatus,
  listClusterNodes,
  listClusterAllocations,
  listClusterJobs,
  listClusterQueues,
} from '../services/api.js'
import { useAuthStore } from '../stores/auth.js'
const loading = ref(false)
const submitBusy = ref(false)
const errorMessage = ref('')
const actionBusy = ref({})
const notice = ref({ tone: '', text: '' })
const submitAnchor = ref(null)
const controllerBusy = ref(false)
const auth = useAuthStore()
const payload = ref({
  controller: {},
  queues: [],
  nodes: [],
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
    const [controller, queues, nodes, jobs, allocations] = await Promise.all([
      getClusterControllerStatus(),
      listClusterQueues(),
      listClusterNodes(),
      listClusterJobs(),
      listClusterAllocations(),
    ])
    payload.value = {
      controller: controller.data || {},
      queues: queues.data?.queues || [],
      nodes: nodes.data?.nodes || [],
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
function setActionBusy(jobId, action, loadingState) {
  const key = actionBusyKey(jobId, action)
  if (loadingState) {
    actionBusy.value = { ...actionBusy.value, [key]: true }
    return
  }
  const next = { ...actionBusy.value }
  delete next[key]
  actionBusy.value = next
}
const reconcileBusy = computed(() => Boolean(actionBusy.value['queue-reconcile:queue.reconcile']))
function setNotice(tone, text) {
  notice.value = { tone, text }
}
async function handleJobAction(payload) {
  const { jobId, action } = payload || {}
  if (!jobId || !action) return
  if (!confirmJobAction(jobId, action)) return
  setActionBusy(jobId, action, true)
  errorMessage.value = ''
  try {
    const command = await props.control.submitBuiltinCommand?.(
      capabilityForJobAction(action),
      { job_id: jobId },
      {
        section: 'cluster',
        acknowledgeRisk: action !== 'cancel',
      },
    )
    const label = jobActionLabel(action)
    if (command?.execution_state === 'awaiting_approval') {
      setNotice('warning', `作业 ${jobId} 的${label}命令已进入待审批队列。`)
    } else {
      setNotice('ok', `作业 ${jobId} 已执行${label}。`)
    }
    await refresh()
  } catch (error) {
    errorMessage.value = error?.response?.data?.detail || error?.message || '作业操作失败'
  } finally {
    setActionBusy(jobId, action, false)
  }
}
async function runClusterObjectCommand(key, capabilityName, argumentsPayload, successText, options = {}) {
  setActionBusy(key, capabilityName, true)
  errorMessage.value = ''
  try {
    const command = await props.control.submitBuiltinCommand?.(
      capabilityName,
      argumentsPayload,
      {
        section: 'cluster',
        acknowledgeRisk: true,
      },
    )
    if (command?.execution_state === 'awaiting_approval') {
      setNotice('warning', `${successText}命令已进入待审批队列。`)
    } else {
      setNotice('ok', `${successText}已提交。`)
    }
    await refresh()
  } catch (error) {
    errorMessage.value = error?.response?.data?.detail || error?.message || options.fallbackError || '集群对象操作失败'
  } finally {
    setActionBusy(key, capabilityName, false)
  }
}
async function handleAllocationRelease(allocationId) {
  if (!allocationId) return
  if (!window.confirm(`将释放 allocation ${allocationId}，是否继续？`)) return
  await runClusterObjectCommand(
    allocationId,
    'allocation.release',
    { allocation_id: allocationId },
    `allocation ${allocationId} 释放`,
    { fallbackError: '释放 allocation 失败' },
  )
}
async function handleNodeDrainToggle(payload) {
  const nodeId = payload?.nodeId
  const drainState = payload?.drainState
  if (!nodeId) return
  const nextCapability = drainState === 'drained' ? 'node.undrain' : 'node.drain'
  const verb = drainState === 'drained' ? '恢复节点' : '排空节点'
  if (!window.confirm(`将${verb} ${nodeId}，是否继续？`)) return
  await runClusterObjectCommand(
    nodeId,
    nextCapability,
    { node_id: nodeId },
    `${verb} ${nodeId}`,
    { fallbackError: `${verb}失败` },
  )
}
async function handleQueueReconcile() {
  await runClusterObjectCommand(
    'queue-reconcile',
    'queue.reconcile',
    {},
    '队列调和',
    { fallbackError: '执行队列调和失败' },
  )
}
async function handleControllerToggle() {
  controllerBusy.value = true
  errorMessage.value = ''
  try {
    const nextEnabled = !viewModel.value.controller.enabled
    const { data } = await configureClusterController({
      enabled: nextEnabled,
      interval_seconds: viewModel.value.controller.intervalSeconds || 15,
    })
    payload.value = {
      ...payload.value,
      controller: data || {},
    }
    setNotice('ok', nextEnabled ? '自动调和已开启。' : '自动调和已关闭。')
  } catch (error) {
    errorMessage.value = error?.response?.data?.detail || '更新自动调和状态失败'
  } finally {
    controllerBusy.value = false
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
    <ClusterConsoleToolbar
      :reconcile-busy="reconcileBusy"
      :toggle-busy="controllerBusy"
      :controller="viewModel.controller"
      @reconcile="handleQueueReconcile"
      @toggle-auto="handleControllerToggle"
      @jump-submit="jumpToSubmit"
      @open-drawer="openClusterDrawer"
    />
    <div v-if="errorMessage" class="tech-card cluster-console-view__notice cluster-console-view__notice--warning">
      {{ errorMessage }}
    </div>
    <div v-else-if="notice.text" class="tech-card cluster-console-view__notice" :class="`cluster-console-view__notice--${notice.tone}`">
      {{ notice.text }}
    </div>
    <div v-else-if="loading" class="tech-card cluster-console-view__notice">
      正在加载集群队列、作业与 allocation 快照...
    </div>
    <div class="cluster-console-view__top">
      <ClusterQueueBoard :queues="viewModel.queues" />
      <ClusterAllocationPanel
        :allocations-by-node="viewModel.allocationsByNode"
        :nodes="viewModel.nodes"
        @release="handleAllocationRelease"
        @toggle-drain="handleNodeDrainToggle"
      />
    </div>
    <div ref="submitAnchor">
      <ClusterJobLedger
        :jobs="viewModel.jobs"
        :submitter-id="auth.currentUser?.username || 'console-user'"
        :submit-busy="submitBusy"
        :action-busy="actionBusy"
        @submit="handleSubmitJob"
        @action="handleJobAction"
      />
    </div>
  </div>
</template>
<style scoped>
.cluster-console-view {
  display: grid;
  gap: 16px;
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
.cluster-console-view__notice--ok {
  border-color: var(--state-ok-border);
  background: var(--state-ok-bg);
  color: var(--state-ok-text);
}
@media (max-width: 1100px) {
  .cluster-console-view__top {
    grid-template-columns: 1fr;
  }
}
</style>

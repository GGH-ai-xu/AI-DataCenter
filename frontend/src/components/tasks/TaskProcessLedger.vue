<script setup>
import { ref, watch } from 'vue'

import TaskProcessLedgerRow from './TaskProcessLedgerRow.vue'
import { syncExpandedPid, toggleExpandedPid } from '../../lib/governanceTaskLedgerUi.js'

const props = defineProps({
  processes: {
    type: Array,
    required: true,
  },
  showAllProcesses: {
    type: Boolean,
    default: false,
  },
  priorityColors: {
    type: Object,
    required: true,
  },
  helpers: {
    type: Object,
    required: true,
  },
  handlers: {
    type: Object,
    required: true,
  },
})

const expandedPid = ref(null)

const priorityOptions = [
  { value: 'urgent', label: '紧急' },
  { value: 'normal', label: '普通' },
  { value: 'deferrable', label: '可延迟' },
]

function priorityTone(priority = 'normal') {
  return props.priorityColors[priority] || props.priorityColors.normal
}

function priorityStyle(priority = 'normal') {
  const tone = priorityTone(priority)
  return {
    color: tone.color,
    background: tone.bg,
  }
}

function isExpanded(proc) {
  return Number(expandedPid.value) === Number(proc.pid)
}

function toggleDetails(proc) {
  expandedPid.value = toggleExpandedPid(expandedPid.value, proc.pid)
}

watch(
  () => props.processes,
  (processes) => {
    expandedPid.value = syncExpandedPid(expandedPid.value, processes)
  },
)
</script>

<template>
  <div class="task-process-ledger">
    <TaskProcessLedgerRow
      v-for="proc in props.processes"
      :key="proc.pid"
      :proc="proc"
      :expanded="isExpanded(proc)"
      :priority-options="priorityOptions"
      :priority-style="priorityStyle"
      :helpers="props.helpers"
      :handlers="props.handlers"
      @toggle-details="toggleDetails(proc)"
    />

    <div v-if="!props.processes.length" class="task-process-ledger__empty">
      {{ props.showAllProcesses ? '暂无匹配的 GPU 相关进程。' : '当前没有可治理任务，可切换到“全部 GPU 相关进程”查看背景与系统进程。' }}
    </div>
  </div>
</template>

<style scoped>
.task-process-ledger {
  display: grid;
  gap: 10px;
}

.task-process-ledger__empty {
  padding: 42px 18px;
  text-align: center;
  color: var(--text-muted);
  border-radius: var(--radius-lg);
  border: 1px dashed rgba(0, 212, 170, 0.16);
  background: rgba(255, 255, 255, 0.02);
}
</style>

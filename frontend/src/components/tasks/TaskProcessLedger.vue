<script setup>
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
</script>

<template>
  <div class="task-process-ledger">
    <article
      v-for="proc in props.processes"
      :key="proc.pid"
      class="task-process-ledger__row"
    >
      <div class="task-process-ledger__identity">
        <div class="task-process-ledger__headline">
          <span class="task-process-ledger__pid stat-value">PID {{ proc.pid }}</span>
          <span class="task-process-ledger__gpu">GPU {{ proc.gpu_index }}</span>
          <span class="status-badge" :class="props.helpers.getCategoryClass(proc)">
            {{ props.helpers.getCategoryLabel(proc) }}
          </span>
        </div>
        <div class="task-process-ledger__name">{{ proc.name || '未命名进程' }}</div>
        <div class="task-process-ledger__meta">
          <span>用户 {{ proc.username || '-' }}</span>
          <span :title="props.helpers.gpuMetricTitle(proc)">显存 {{ props.helpers.displayGpuMemory(proc) }}</span>
          <span :title="props.helpers.cpuMetricTitle(proc)">CPU {{ props.helpers.displayCpuPercent(proc) }}</span>
        </div>
      </div>

      <div class="task-process-ledger__governance">
        <label class="task-process-ledger__field">
          <span class="task-process-ledger__label">优先级</span>
          <select
            class="priority-select"
            :disabled="!props.helpers.isManageable(proc)"
            :value="proc.priority || 'normal'"
            :style="priorityStyle(proc.priority || 'normal')"
            @change="props.handlers.changePriority(proc, $event.target.value)"
          >
            <option
              v-for="option in priorityOptions"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </option>
          </select>
        </label>

        <div class="task-process-ledger__field">
          <span class="task-process-ledger__label">治理说明</span>
          <div class="task-process-ledger__text" :title="props.helpers.getManageableReason(proc)">
            {{ props.helpers.getReasonSummary(proc) }}
          </div>
        </div>

        <div class="task-process-ledger__field">
          <span class="task-process-ledger__label">命令</span>
          <div class="task-process-ledger__text" :title="proc.command || '-'">
            {{ props.helpers.getCommandPreview(proc) }}
          </div>
        </div>
      </div>

      <div class="task-process-ledger__actions">
        <template v-if="props.helpers.isManageable(proc)">
          <div class="task-process-ledger__buttons">
            <button
              class="btn-tech"
              :disabled="props.handlers.isActionDisabled(proc, 'pause')"
              @click="props.handlers.doAction(proc, 'pause')"
            >
              暂停
            </button>
            <button
              class="btn-tech"
              :disabled="props.handlers.isActionDisabled(proc, 'resume')"
              @click="props.handlers.doAction(proc, 'resume')"
            >
              恢复
            </button>
            <button
              class="btn-tech btn-tech--danger"
              :disabled="props.handlers.isActionDisabled(proc, 'terminate')"
              @click="props.handlers.doAction(proc, 'terminate')"
            >
              终止
            </button>
          </div>
          <div class="task-process-ledger__hint">
            {{ props.helpers.getActionHint(proc) }}
          </div>
        </template>
        <div
          v-else
          class="task-process-ledger__hint task-process-ledger__hint--readonly"
          :title="props.helpers.getManageableReason(proc)"
        >
          该类进程只做观测，不提供暂停或终止。
        </div>
      </div>
    </article>

    <div v-if="!props.processes.length" class="task-process-ledger__empty">
      {{ props.showAllProcesses ? '暂无匹配的 GPU 相关进程。' : '当前没有可治理任务，可切换到“全部 GPU 相关进程”查看背景与系统进程。' }}
    </div>
  </div>
</template>

<style scoped>
.task-process-ledger {
  display: grid;
  gap: 12px;
}

.task-process-ledger__row {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(0, 1.4fr) minmax(250px, 0.95fr);
  gap: 16px;
  padding: 18px 20px;
  border-radius: 22px;
  border: 1px solid rgba(26, 26, 26, 0.06);
  background: rgba(255, 252, 247, 0.82);
  box-shadow: 0 16px 36px rgba(79, 59, 22, 0.05);
}

.task-process-ledger__identity,
.task-process-ledger__governance,
.task-process-ledger__actions {
  min-width: 0;
}

.task-process-ledger__headline,
.task-process-ledger__meta,
.task-process-ledger__buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.task-process-ledger__pid,
.task-process-ledger__gpu {
  font-size: 0.82rem;
}

.task-process-ledger__gpu,
.task-process-ledger__meta {
  color: var(--text-muted);
}

.task-process-ledger__name {
  margin-top: 10px;
  font-size: 1rem;
  color: var(--text-primary);
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.task-process-ledger__meta {
  margin-top: 10px;
  font-size: 0.76rem;
  line-height: 1.6;
}

.task-process-ledger__governance {
  display: grid;
  gap: 12px;
}

.task-process-ledger__field {
  display: grid;
  gap: 6px;
}

.priority-select {
  padding: 8px 10px;
  border-radius: 10px;
  border: 1px solid rgba(26, 26, 26, 0.08);
  background: rgba(255, 255, 255, 0.82);
  color: var(--text-primary);
  font-size: 0.8rem;
}

.priority-select:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.task-process-ledger__label {
  font-size: 0.72rem;
  color: var(--text-muted);
  letter-spacing: 0.04em;
}

.task-process-ledger__text,
.task-process-ledger__hint {
  font-size: 0.8rem;
  color: var(--text-secondary);
  line-height: 1.65;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.task-process-ledger__actions {
  display: grid;
  align-content: start;
  gap: 10px;
  padding: 14px 16px;
  border-radius: 18px;
  background: rgba(248, 245, 240, 0.92);
  border: 1px dashed rgba(58, 95, 75, 0.14);
}

.task-process-ledger__buttons {
  justify-content: flex-start;
}

.task-process-ledger__hint {
  font-size: 0.74rem;
  color: var(--text-muted);
}

.task-process-ledger__hint--readonly {
  color: #7B5D15;
}

.status-badge--background {
  color: #666666;
  background: rgba(153, 153, 153, 0.12);
}

.status-badge--system {
  color: #7A4B14;
  background: rgba(212, 175, 55, 0.14);
}

.task-process-ledger__empty {
  padding: 42px 18px;
  text-align: center;
  color: var(--text-muted);
  border-radius: 22px;
  border: 1px dashed rgba(58, 95, 75, 0.14);
  background: rgba(255, 252, 247, 0.72);
}

@media (max-width: 1280px) {
  .task-process-ledger__row {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  }

  .task-process-ledger__actions {
    grid-column: 1 / -1;
  }
}

@media (max-width: 820px) {
  .task-process-ledger__row {
    grid-template-columns: 1fr;
    padding: 16px;
  }

  .task-process-ledger__actions {
    padding: 12px 14px;
  }

  .task-process-ledger__buttons {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>

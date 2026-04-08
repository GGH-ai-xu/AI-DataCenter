<script setup>
const props = defineProps({
  proc: {
    type: Object,
    required: true,
  },
  expanded: {
    type: Boolean,
    default: false,
  },
  priorityOptions: {
    type: Array,
    required: true,
  },
  priorityStyle: {
    type: Function,
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

defineEmits(['toggle-details'])
</script>

<template>
  <article class="task-process-ledger-row">
    <div class="task-process-ledger-row__head">
      <div class="task-process-ledger-row__identity">
        <div class="task-process-ledger-row__name">
          {{ props.proc.name || '未命名进程' }}
        </div>
        <div class="task-process-ledger-row__chips">
          <span class="task-process-ledger-row__pid stat-value">PID {{ props.proc.pid }}</span>
          <span class="task-process-ledger-row__gpu">GPU {{ props.proc.gpu_index }}</span>
          <span class="status-badge" :class="props.helpers.getCategoryClass(props.proc)">
            {{ props.helpers.getCategoryLabel(props.proc) }}
          </span>
        </div>
      </div>
      <div class="task-process-ledger-row__controls">
        <label
          v-if="props.helpers.isManageable(props.proc)"
          class="task-process-ledger-row__priority"
        >
          <span class="task-process-ledger-row__label">优先级</span>
          <select
            class="priority-select"
            :value="props.proc.priority || 'normal'"
            :style="props.priorityStyle(props.proc.priority || 'normal')"
            @change="props.handlers.changePriority(props.proc, $event.target.value)"
          >
            <option
              v-for="option in props.priorityOptions"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </option>
          </select>
        </label>
        <span
          v-else
          class="status-badge task-process-ledger-row__readonly"
          :class="props.helpers.getCategoryClass(props.proc)"
        >
          仅观测
        </span>
        <div
          v-if="props.helpers.isManageable(props.proc)"
          class="task-process-ledger-row__buttons"
        >
          <button
            class="btn-tech"
            :disabled="props.handlers.isActionDisabled(props.proc, 'pause')"
            @click="props.handlers.doAction(props.proc, 'pause')"
          >
            暂停
          </button>
          <button
            class="btn-tech"
            :disabled="props.handlers.isActionDisabled(props.proc, 'resume')"
            @click="props.handlers.doAction(props.proc, 'resume')"
          >
            恢复
          </button>
          <button
            class="btn-tech btn-tech--danger"
            :disabled="props.handlers.isActionDisabled(props.proc, 'terminate')"
            @click="props.handlers.doAction(props.proc, 'terminate')"
          >
            终止
          </button>
        </div>
      </div>
    </div>
    <div class="task-process-ledger-row__summary">
      <div class="task-process-ledger-row__meta">
        <span>用户 {{ props.proc.username || '-' }}</span>
        <span :title="props.helpers.gpuMetricTitle(props.proc)">显存 {{ props.helpers.displayGpuMemory(props.proc) }}</span>
        <span :title="props.helpers.cpuMetricTitle(props.proc)">CPU {{ props.helpers.displayCpuPercent(props.proc) }}</span>
      </div>

      <div
        class="task-process-ledger-row__summary-copy"
        :title="props.helpers.getManageableReason(props.proc)"
      >
        {{ props.helpers.getReasonSummary(props.proc) }}
      </div>
      <button
        type="button"
        class="btn-tech task-process-ledger-row__detail-toggle"
        @click="$emit('toggle-details')"
      >
        {{ props.expanded ? '收起详情' : '查看详情' }}
      </button>
    </div>
    <div v-if="props.expanded" class="task-process-ledger-row__details">
      <div class="task-process-ledger-row__detail-field">
        <span class="task-process-ledger-row__label">治理说明</span>
        <div class="task-process-ledger-row__detail-text">
          {{ props.helpers.getManageableReason(props.proc) }}
        </div>
      </div>
      <div class="task-process-ledger-row__detail-field">
        <span class="task-process-ledger-row__label">命令</span>
        <div class="task-process-ledger-row__detail-text">
          {{ props.helpers.getCommandPreview(props.proc) }}
        </div>
      </div>
      <div class="task-process-ledger-row__detail-field">
        <span class="task-process-ledger-row__label">
          {{ props.helpers.isManageable(props.proc) ? '动作提示' : '只读原因' }}
        </span>
        <div class="task-process-ledger-row__detail-text">
          {{
            props.helpers.isManageable(props.proc)
              ? props.helpers.getActionHint(props.proc)
              : props.helpers.getManageableReason(props.proc)
          }}
        </div>
      </div>
    </div>
  </article>
</template>

<style scoped>
.task-process-ledger-row {
  display: grid;
  gap: 12px;
  padding: 14px 16px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
  background: rgba(255, 255, 255, 0.03);
  box-shadow: var(--shadow-card);
}

.task-process-ledger-row__head,
.task-process-ledger-row__summary {
  display: grid;
  gap: 10px;
}
.task-process-ledger-row__head {
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: start;
}

.task-process-ledger-row__identity {
  display: grid;
  gap: 8px;
  min-width: 0;
}
.task-process-ledger-row__chips,
.task-process-ledger-row__meta,
.task-process-ledger-row__buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.task-process-ledger-row__name {
  font-size: 0.98rem;
  line-height: 1.45;
  color: var(--text-primary);
  overflow-wrap: anywhere;
}

.task-process-ledger-row__pid,
.task-process-ledger-row__gpu,
.task-process-ledger-row__meta {
  font-size: 0.76rem;
  line-height: 1.5;
  color: var(--text-muted);
}

.task-process-ledger-row__controls {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: flex-start;
  justify-content: flex-end;
}

.task-process-ledger-row__priority {
  display: grid;
  gap: 4px;
}

.task-process-ledger-row__label {
  font-size: 0.7rem;
  letter-spacing: 0.04em;
  color: var(--text-muted);
}

.priority-select {
  padding: 7px 10px;
  border-radius: 10px;
  border: 1px solid var(--border-color);
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-primary);
  font-size: 0.8rem;
}

.task-process-ledger-row__summary {
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
}

.task-process-ledger-row__summary-copy,
.task-process-ledger-row__detail-text {
  font-size: 0.8rem;
  line-height: 1.6;
  color: var(--text-secondary);
  overflow-wrap: anywhere;
  word-break: break-word;
}

.task-process-ledger-row__detail-toggle {
  justify-self: end;
}

.task-process-ledger-row__details {
  display: grid;
  gap: 10px;
  padding-top: 10px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.task-process-ledger-row__detail-field {
  display: grid;
  gap: 4px;
}

.task-process-ledger-row__readonly {
  white-space: nowrap;
}
.status-badge--background {
  color: var(--text-secondary);
  background: rgba(160, 170, 190, 0.12);
}
.status-badge--system {
  color: var(--accent-warning);
  background: rgba(245, 158, 11, 0.12);
}
@media (max-width: 1180px) {
  .task-process-ledger-row__head,
  .task-process-ledger-row__summary {
    grid-template-columns: 1fr;
  }

  .task-process-ledger-row__controls {
    justify-content: flex-start;
  }

  .task-process-ledger-row__detail-toggle {
    justify-self: start;
  }
}

@media (max-width: 720px) {
  .task-process-ledger-row {
    padding: 14px;
  }

  .task-process-ledger-row__buttons {
    width: 100%;
  }
}
</style>

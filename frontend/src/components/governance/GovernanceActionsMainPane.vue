<script setup>
const props = defineProps({
  keyword: {
    type: String,
    required: true,
  },
  selectedPriority: {
    type: String,
    required: true,
  },
  showAllProcesses: {
    type: Boolean,
    required: true,
  },
  exporting: {
    type: Boolean,
    default: false,
  },
  filteredProcesses: {
    type: Array,
    required: true,
  },
  visibleCount: {
    type: Number,
    required: true,
  },
  priorityColors: {
    type: Object,
    required: true,
  },
  ledgerComponent: {
    type: Object,
    required: true,
  },
  ledgerHelpers: {
    type: Object,
    required: true,
  },
  ledgerHandlers: {
    type: Object,
    required: true,
  },
})

const emit = defineEmits([
  'update:keyword',
  'update:selectedPriority',
  'update:showAllProcesses',
  'export',
])
</script>

<template>
  <div class="governance-actions-main">
    <section class="tech-card toolbar-card">
      <div class="toolbar-card__cluster toolbar-card__cluster--filters">
        <label class="toolbar-field toolbar-field--search">
          <span class="toolbar-field__label">检索任务</span>
          <input
            :value="props.keyword"
            class="task-input"
            placeholder="PID / 用户 / 进程名 / 命令"
            @input="emit('update:keyword', $event.target.value)"
          />
        </label>
        <label class="toolbar-field toolbar-field--priority">
          <span class="toolbar-field__label">优先级</span>
          <select
            :value="props.selectedPriority"
            class="task-select"
            @change="emit('update:selectedPriority', $event.target.value)"
          >
            <option value="all">全部</option>
            <option value="urgent">紧急</option>
            <option value="normal">普通</option>
            <option value="deferrable">可延迟</option>
          </select>
        </label>
      </div>

      <div class="toolbar-card__cluster toolbar-card__cluster--switch">
        <div class="toolbar-segment" role="tablist" aria-label="任务视图切换">
          <button
            type="button"
            class="toolbar-segment__item"
            :class="{ 'toolbar-segment__item--active': !props.showAllProcesses }"
            @click="emit('update:showAllProcesses', false)"
          >
            治理任务
          </button>
          <button
            type="button"
            class="toolbar-segment__item"
            :class="{ 'toolbar-segment__item--active': props.showAllProcesses }"
            @click="emit('update:showAllProcesses', true)"
          >
            全部 GPU 进程
          </button>
        </div>
      </div>

      <div class="toolbar-card__cluster toolbar-card__cluster--meta">
        <div class="toolbar-card__summary">
          <span class="toolbar-card__summary-label">当前显示</span>
          <span class="toolbar-card__summary-value">{{ props.filteredProcesses.length }} / {{ props.visibleCount }}</span>
        </div>
        <button
          type="button"
          class="toolbar-export"
          :disabled="props.exporting"
          @click="emit('export')"
        >
          {{ props.exporting ? '导出中...' : '导出报告' }}
        </button>
      </div>
    </section>

    <section class="tech-card ledger-panel">
      <div class="ledger-panel__head">
        <div class="panel-card__title">任务账本</div>
        <div class="ledger-panel__hint">即时处置页只承接筛选、分级和对象动作，不承担预算和策略配置。</div>
      </div>
      <component
        :is="props.ledgerComponent"
        :processes="props.filteredProcesses"
        :show-all-processes="props.showAllProcesses"
        :priority-colors="props.priorityColors"
        :helpers="props.ledgerHelpers"
        :handlers="props.ledgerHandlers"
      />
    </section>
  </div>
</template>

<style scoped>
.toolbar-card,
.ledger-panel {
  margin-bottom: 14px;
}

.toolbar-card {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 12px 16px;
  padding: 12px 14px;
  border-radius: 18px;
  background: var(--bg-card);
  box-shadow: var(--shadow-card);
}

.toolbar-card::before {
  left: 18px;
  right: 18px;
}

.toolbar-card__cluster {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.toolbar-card__cluster--filters {
  flex: 1 1 420px;
  display: grid;
  grid-template-columns: minmax(220px, 1fr) 120px;
  gap: 10px;
  align-items: end;
}

.toolbar-card__cluster--switch {
  flex: 0 0 auto;
  justify-content: flex-start;
}

.toolbar-card__cluster--meta {
  margin-left: auto;
  flex: 0 0 auto;
  justify-content: flex-end;
}

.toolbar-field {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.toolbar-field__label,
.toolbar-card__summary-label,
.ledger-panel__hint {
  font-size: 0.68rem;
  color: var(--text-muted);
  line-height: 1.3;
  letter-spacing: 0.04em;
}

.task-input,
.task-select {
  min-height: 40px;
  padding: 9px 12px;
  border-radius: 12px;
  border: 1px solid var(--field-border);
  background: var(--field-background);
  color: var(--text-primary);
  font-size: 0.84rem;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.task-input::placeholder {
  color: var(--text-muted);
}

.toolbar-segment {
  display: inline-flex;
  align-items: center;
  padding: 4px;
  border-radius: 14px;
  border: 1px solid var(--border-color);
  background: var(--bg-surface);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
  gap: 4px;
}

.toolbar-segment__item {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 38px;
  padding: 0 16px;
  border-radius: 10px;
  background: transparent;
  color: var(--text-muted);
  font-size: 0.82rem;
  font-weight: 700;
  letter-spacing: 0.02em;
  transition:
    background 180ms ease,
    color 180ms ease,
    box-shadow 180ms ease,
    transform 180ms ease;
  cursor: pointer;
  white-space: nowrap;
}

.toolbar-segment__item:hover {
  color: var(--text-primary);
}

.toolbar-segment__item--active {
  color: var(--state-ok-text);
  background: var(--state-ok-bg);
  box-shadow:
    0 8px 20px rgba(127, 142, 255, 0.18),
    inset 0 1px 0 rgba(255, 255, 255, 0.22);
}

.toolbar-card__summary {
  display: grid;
  justify-items: end;
  gap: 2px;
  padding: 0 2px;
  white-space: nowrap;
}

.toolbar-card__summary-value {
  font-size: 1.02rem;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: 0.02em;
}

.toolbar-export {
  min-height: 38px;
  padding: 0 14px;
  border-radius: 12px;
  border: 1px solid var(--border-color);
  background: var(--bg-surface);
  color: var(--text-secondary);
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.03em;
  cursor: pointer;
  white-space: nowrap;
  transition:
    border-color 180ms ease,
    background 180ms ease,
    color 180ms ease,
    transform 180ms ease;
}

.toolbar-export:hover {
  color: var(--text-primary);
  border-color: var(--state-ok-border);
  background: var(--state-ok-bg);
  transform: translateY(-1px);
}

.toolbar-export:disabled {
  opacity: 0.48;
  cursor: not-allowed;
  transform: none;
}

.ledger-panel {
  padding: 18px;
}

.panel-card__title {
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 12px;
}

.ledger-panel__head {
  display: grid;
  gap: 6px;
  margin-bottom: 14px;
}

@media (max-width: 1160px) {
  .toolbar-card__cluster--meta {
    margin-left: 0;
  }
}

@media (max-width: 760px) {
  .toolbar-card {
    padding: 12px;
  }

  .toolbar-card__cluster--filters {
    grid-template-columns: 1fr;
  }

  .toolbar-card__cluster--switch,
  .toolbar-card__cluster--meta {
    width: 100%;
    flex-direction: row;
    justify-content: space-between;
    align-items: stretch;
  }

  .toolbar-segment {
    width: 100%;
    justify-content: stretch;
  }

  .toolbar-segment__item {
    flex: 1 1 0;
    justify-content: center;
  }

  .toolbar-card__cluster--meta {
    flex-wrap: wrap;
    gap: 10px;
  }

  .toolbar-card__summary {
    justify-items: start;
  }

  .toolbar-export {
    margin-left: auto;
  }
}
</style>

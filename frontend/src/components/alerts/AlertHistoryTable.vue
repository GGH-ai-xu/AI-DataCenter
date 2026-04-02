<script setup>
const props = defineProps({
  alerts: {
    type: Array,
    required: true,
  },
  loading: {
    type: Boolean,
    required: true,
  },
  severityConfig: {
    type: Object,
    required: true,
  },
  fmtTime: {
    type: Function,
    required: true,
  },
  formatAlertType: {
    type: Function,
    required: true,
  },
})

const emit = defineEmits(['ack'])

function severityLabel(severity = 'warning') {
  return props.severityConfig[severity]?.label || severity
}
</script>

<template>
  <div class="alert-history-table alert-history-table--archive">
    <div class="alert-history-table__head">
      <span>级别</span>
      <span>GPU</span>
      <span>类型</span>
      <span>告警内容</span>
      <span>数值</span>
      <span>阈值</span>
      <span>时间</span>
      <span>状态</span>
    </div>

    <article
      v-for="alert in props.alerts"
      :key="alert.id"
      class="alert-history-table__row"
    >
      <div class="alert-history-table__cell" data-label="级别">
        <span class="status-badge" :class="alert.severity === 'critical' ? 'status-badge--critical' : 'status-badge--warning'">
          {{ severityLabel(alert.severity) }}
        </span>
      </div>
      <div class="alert-history-table__cell" data-label="GPU">
        <span class="gpu-tag">GPU {{ alert.gpu_index }}</span>
      </div>
      <div class="alert-history-table__cell alert-history-table__type" data-label="类型">
        {{ props.formatAlertType(alert.alert_type) }}
      </div>
      <div class="alert-history-table__cell alert-history-table__message" data-label="告警内容">
        {{ alert.message }}
      </div>
      <div class="alert-history-table__cell stat-value" data-label="数值">
        {{ alert.value?.toFixed(1) ?? '—' }}
      </div>
      <div class="alert-history-table__cell stat-value alert-history-table__muted" data-label="阈值">
        {{ alert.threshold ?? '—' }}
      </div>
      <div class="alert-history-table__cell alert-history-table__time" data-label="时间">
        {{ props.fmtTime(alert.timestamp) }}
      </div>
      <div class="alert-history-table__cell" data-label="状态">
        <button
          v-if="!alert.acknowledged"
          class="btn-tech alert-history-table__ack"
          @click="emit('ack', alert.id)"
        >
          确认
        </button>
        <span v-else class="alert-history-table__muted">已确认</span>
      </div>
    </article>

    <div v-if="!props.alerts.length && !props.loading" class="alert-history-table__empty">
      暂无告警记录
    </div>
  </div>
</template>

<style scoped>
.alert-history-table {
  display: grid;
  gap: 10px;
}

.alert-history-table--archive {
  align-content: start;
}

.alert-history-table__head,
.alert-history-table__row {
  display: grid;
  grid-template-columns: minmax(88px, 0.7fr) minmax(84px, 0.65fr) minmax(94px, 0.8fr) minmax(0, 2.2fr) minmax(86px, 0.7fr) minmax(86px, 0.7fr) minmax(140px, 1fr) minmax(88px, 0.75fr);
  gap: 12px;
  align-items: start;
}

.alert-history-table__head {
  padding: 0 16px 2px;
  font-size: 0.74rem;
  color: var(--text-muted);
  letter-spacing: 0.04em;
}

.alert-history-table__row {
  padding: 14px 16px;
  border-radius: 18px;
  border: 1px solid rgba(26, 26, 26, 0.06);
  background: rgba(255, 252, 247, 0.82);
}

.alert-history-table__cell {
  min-width: 0;
  font-size: 0.8125rem;
  line-height: 1.65;
  color: var(--text-secondary);
  overflow-wrap: anywhere;
}

.gpu-tag {
  font-size: 0.6875rem;
  font-weight: 600;
  color: var(--accent-primary);
  background: rgba(58, 95, 75, 0.1);
  padding: 2px 8px;
  border-radius: 4px;
}

.alert-history-table__message {
  color: var(--text-primary);
}

.alert-history-table__type,
.alert-history-table__time,
.alert-history-table__muted {
  color: var(--text-muted);
}

.alert-history-table__ack {
  padding: 3px 10px;
  font-size: 0.72rem;
}

.alert-history-table__empty {
  padding: 42px 18px;
  text-align: center;
  border-radius: 20px;
  border: 1px dashed rgba(58, 95, 75, 0.14);
  color: var(--text-muted);
}

@media (max-width: 1200px) {
  .alert-history-table__head {
    display: none;
  }

  .alert-history-table__row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .alert-history-table__cell::before {
    content: attr(data-label);
    display: block;
    margin-bottom: 4px;
    font-size: 0.7rem;
    color: var(--text-muted);
    letter-spacing: 0.04em;
  }

  .alert-history-table__message {
    grid-column: 1 / -1;
  }
}

@media (max-width: 720px) {
  .alert-history-table__row {
    grid-template-columns: 1fr;
    gap: 10px;
    padding: 14px;
  }
}
</style>

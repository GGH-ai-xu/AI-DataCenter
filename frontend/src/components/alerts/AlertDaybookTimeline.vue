<script setup>
defineProps({
  sections: {
    type: Array,
    default: () => [],
  },
  loading: {
    type: Boolean,
    default: false,
  },
  severityConfig: {
    type: Object,
    default: () => ({}),
  },
  formatAlertType: {
    type: Function,
    default: (value) => value,
  },
  fmtTime: {
    type: Function,
    default: (value) => String(value ?? ''),
  },
})

const emit = defineEmits(['ack'])
</script>

<template>
  <section class="tech-card alert-daybook-timeline">
    <div class="alert-daybook-timeline__header">
      <div class="section-title" style="font-size: 1rem">今日告警簿</div>
      <div class="alert-daybook-timeline__hint">按时间节点复盘当天告警，正文与状态分层展示，不再依赖横向表格扫描。</div>
    </div>

    <div v-if="!sections.length && !loading" class="alert-daybook-timeline__empty">
      今日暂无告警记录。
    </div>

    <section
      v-for="section in sections"
      :key="section.key"
      class="daybook-section"
    >
      <header class="daybook-section__head">
        <div class="daybook-section__title">{{ section.label }}</div>
        <div class="daybook-section__count">{{ section.items.length }} 条</div>
      </header>

      <article
        v-for="alert in section.items"
        :key="alert.id"
        class="daybook-entry"
      >
        <div class="daybook-entry__meta">
          <span class="status-badge" :class="alert.severity === 'critical' ? 'status-badge--critical' : 'status-badge--warning'">
            {{ severityConfig[alert.severity]?.label || alert.severity }}
          </span>
          <span class="gpu-tag">GPU {{ alert.gpu_index }}</span>
          <span class="daybook-entry__type">{{ formatAlertType(alert.alert_type) }}</span>
          <span class="daybook-entry__time">{{ fmtTime(alert.timestamp) }}</span>
        </div>

        <div class="daybook-entry__message">{{ alert.message }}</div>

        <div class="daybook-entry__footer">
          <span class="stat-value">{{ alert.value?.toFixed(1) ?? '—' }}</span>
          <span class="daybook-entry__threshold">阈值 {{ alert.threshold ?? '—' }}</span>
          <button
            v-if="!alert.acknowledged"
            type="button"
            class="btn-tech daybook-entry__ack"
            @click="emit('ack', alert.id)"
          >
            确认
          </button>
          <span v-else class="daybook-entry__state">已确认</span>
        </div>
      </article>
    </section>
  </section>
</template>

<style scoped>
.alert-daybook-timeline {
  padding: 20px 22px;
  display: grid;
  gap: 18px;
}

.alert-daybook-timeline__header {
  display: grid;
  gap: 6px;
}

.alert-daybook-timeline__hint {
  font-size: 0.8125rem;
  line-height: 1.7;
  color: var(--text-muted);
}

.alert-daybook-timeline__empty {
  padding: 40px 18px;
  border-radius: 18px;
  border: 1px dashed rgba(0, 212, 170, 0.16);
  text-align: center;
  color: var(--text-muted);
  font-size: 0.82rem;
}

.daybook-section {
  display: grid;
  gap: 10px;
  position: relative;
  padding-left: 18px;
}

.daybook-section::before {
  content: '';
  position: absolute;
  left: 4px;
  top: 34px;
  bottom: 0;
  width: 2px;
  background: rgba(0, 212, 170, 0.12);
}

.daybook-section__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.daybook-section__title {
  font-size: 0.96rem;
  font-weight: 600;
  color: var(--text-primary);
}

.daybook-section__count {
  font-size: 0.74rem;
  color: var(--text-muted);
}

.daybook-entry {
  position: relative;
  display: grid;
  gap: 10px;
  padding: 16px 18px;
  border-radius: 18px;
  border: 1px solid var(--border-color);
  background: rgba(255, 255, 255, 0.03);
}

.daybook-entry::before {
  content: '';
  position: absolute;
  left: -18px;
  top: 18px;
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: var(--accent-primary);
  border: 2px solid rgba(0, 212, 170, 0.16);
}

.daybook-entry__meta,
.daybook-entry__footer {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.daybook-entry__type,
.daybook-entry__time,
.daybook-entry__threshold,
.daybook-entry__state {
  font-size: 0.74rem;
  color: var(--text-muted);
}

.daybook-entry__message {
  font-size: 0.84rem;
  line-height: 1.72;
  color: var(--text-primary);
  overflow-wrap: anywhere;
}

.daybook-entry__ack {
  margin-left: auto;
  min-height: 32px;
  padding: 0 12px;
  font-size: 0.72rem;
}

@media (max-width: 720px) {
  .alert-daybook-timeline {
    padding: 18px 16px;
  }

  .daybook-section__head {
    flex-direction: column;
    align-items: flex-start;
  }

  .daybook-entry__ack {
    margin-left: 0;
  }
}
</style>

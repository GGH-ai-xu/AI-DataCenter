<script setup>
import AlertRealtimeSidebar from './AlertRealtimeSidebar.vue'
import WorkspacePaneLayout from '../workspace/WorkspacePaneLayout.vue'

defineProps({
  buckets: {
    type: Array,
    default: () => [],
  },
  loading: {
    type: Boolean,
    default: false,
  },
  selectedType: {
    type: String,
    default: 'all',
  },
  filterItems: {
    type: Array,
    default: () => [],
  },
  summaryItems: {
    type: Array,
    default: () => [],
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

const emit = defineEmits(['ack', 'update:selectedType'])
</script>

<template>
  <WorkspacePaneLayout>
    <template #main>
      <section class="tech-card alert-realtime-stream">
        <div class="alert-realtime-stream__header">
          <div>
            <div class="section-title" style="font-size: 1rem">实时流</div>
            <div class="alert-realtime-stream__hint">默认只展示未确认告警，主区按时间分段，避免历史信息打断值守节奏。</div>
          </div>
        </div>

        <div v-if="!buckets.length && !loading" class="alert-realtime-stream__empty">
          当前没有未确认的实时告警。
        </div>

        <section
          v-for="bucket in buckets"
          :key="bucket.key"
          class="realtime-bucket"
        >
          <header class="realtime-bucket__head">
            <div class="realtime-bucket__title">{{ bucket.label }}</div>
            <div class="realtime-bucket__desc">{{ bucket.desc }}</div>
          </header>

          <article
            v-for="alert in bucket.items"
            :key="alert.id"
            class="realtime-alert-card"
          >
            <div class="realtime-alert-card__meta">
              <span class="status-badge" :class="alert.severity === 'critical' ? 'status-badge--critical' : 'status-badge--warning'">
                {{ severityConfig[alert.severity]?.label || alert.severity }}
              </span>
              <span class="gpu-tag">GPU {{ alert.gpu_index }}</span>
              <span class="realtime-alert-card__type">{{ formatAlertType(alert.alert_type) }}</span>
              <span class="realtime-alert-card__time">{{ fmtTime(alert.timestamp) }}</span>
            </div>

            <div class="realtime-alert-card__message">{{ alert.message }}</div>

            <div class="realtime-alert-card__footer">
              <span class="stat-value">{{ alert.value?.toFixed(1) ?? '—' }}</span>
              <span class="realtime-alert-card__threshold">阈值 {{ alert.threshold ?? '—' }}</span>
              <button
                type="button"
                class="btn-tech alert-realtime-stream__ack"
                @click="emit('ack', alert.id)"
              >
                确认
              </button>
            </div>
          </article>
        </section>
      </section>
    </template>

    <template #side>
      <AlertRealtimeSidebar
        :model-value="selectedType"
        :items="filterItems"
        :summary-items="summaryItems"
        @update:modelValue="emit('update:selectedType', $event)"
      />
    </template>
  </WorkspacePaneLayout>
</template>

<style scoped>
.alert-realtime-stream {
  padding: 20px 22px;
  display: grid;
  gap: 18px;
}

.alert-realtime-stream__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.alert-realtime-stream__hint {
  margin-top: 6px;
  font-size: 0.8125rem;
  line-height: 1.7;
  color: var(--text-muted);
}

.alert-realtime-stream__empty {
  padding: 36px 18px;
  border-radius: 18px;
  border: 1px dashed rgba(0, 212, 170, 0.16);
  color: var(--text-muted);
  text-align: center;
  font-size: 0.82rem;
}

.realtime-bucket {
  display: grid;
  gap: 10px;
}

.realtime-bucket__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.realtime-bucket__title {
  font-size: 0.96rem;
  font-weight: 600;
  color: var(--text-primary);
}

.realtime-bucket__desc {
  font-size: 0.74rem;
  color: var(--text-muted);
}

.realtime-alert-card {
  display: grid;
  gap: 10px;
  padding: 16px 18px;
  border-radius: 18px;
  border: 1px solid var(--border-color);
  background: rgba(255, 255, 255, 0.03);
}

.realtime-alert-card__meta,
.realtime-alert-card__footer {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.realtime-alert-card__type,
.realtime-alert-card__time,
.realtime-alert-card__threshold {
  font-size: 0.74rem;
  color: var(--text-muted);
}

.realtime-alert-card__message {
  font-size: 0.84rem;
  line-height: 1.7;
  color: var(--text-primary);
  overflow-wrap: anywhere;
}

.alert-realtime-stream__ack {
  margin-left: auto;
  min-height: 32px;
  padding: 0 12px;
  font-size: 0.72rem;
}

@media (max-width: 720px) {
  .alert-realtime-stream {
    padding: 18px 16px;
  }

  .realtime-bucket__head {
    flex-direction: column;
    align-items: flex-start;
  }

  .alert-realtime-stream__ack {
    margin-left: 0;
  }
}
</style>

<script setup>
import { computed } from 'vue'
import AlertArchiveTypeTabs from './AlertArchiveTypeTabs.vue'
import AlertHistoryTable from './AlertHistoryTable.vue'

const props = defineProps({
  typeKey: {
    type: String,
    required: true,
  },
  groups: {
    type: Array,
    default: () => [],
  },
  loading: {
    type: Boolean,
    default: false,
  },
  severityConfig: {
    type: Object,
    required: true,
  },
  formatAlertType: {
    type: Function,
    required: true,
  },
  fmtTime: {
    type: Function,
    required: true,
  },
})

const emit = defineEmits(['ack', 'update:typeKey'])

const selectedGroup = computed(() => (
  props.groups.find((group) => group.key === props.typeKey) || props.groups[0] || null
))

const archiveSnapshot = computed(() => {
  if (!selectedGroup.value) {
    return []
  }

  const latestTime = selectedGroup.value.latest?.timestamp
    ? props.fmtTime(selectedGroup.value.latest.timestamp)
    : '暂无记录'

  return [
    {
      key: 'count',
      label: '历史记录',
      value: `${selectedGroup.value.count} 条`,
      detail: '按类型集中回看历史样本',
    },
    {
      key: 'latest',
      label: '最近一次',
      value: latestTime,
      detail: '帮助快速定位上次出现时间',
    },
    {
      key: 'status',
      label: '归档口径',
      value: selectedGroup.value.label,
      detail: selectedGroup.value.desc,
    },
  ]
})
</script>

<template>
  <section class="alert-archive-board">
    <section class="tech-card archive-summary">
      <div class="archive-summary__head">
        <div class="section-title">历史归档</div>
        <div class="archive-summary__hint">按类型集中回看已进入历史账页的告警，切换类型时不会牵动其他区域布局。</div>
      </div>

      <AlertArchiveTypeTabs
        :model-value="typeKey"
        :items="groups"
        @update:modelValue="emit('update:typeKey', $event)"
      />
    </section>

    <section class="tech-card archive-detail">
      <div class="archive-detail__head">
        <div>
          <div class="section-title">{{ selectedGroup?.label || '归档明细' }}</div>
          <div class="archive-detail__hint">{{ selectedGroup?.desc || '按类型查看历史告警。' }}</div>
        </div>
        <div class="archive-detail__meta">
          <article
            v-for="item in archiveSnapshot"
            :key="item.key"
            class="archive-detail__metric"
          >
            <span class="archive-detail__metric-label">{{ item.label }}</span>
            <strong class="archive-detail__metric-value">{{ item.value }}</strong>
            <span class="archive-detail__metric-detail">{{ item.detail }}</span>
          </article>
        </div>
      </div>

      <AlertHistoryTable
        :alerts="selectedGroup?.alerts || []"
        :loading="loading"
        :severity-config="severityConfig"
        :fmt-time="fmtTime"
        :format-alert-type="formatAlertType"
        @ack="emit('ack', $event)"
      />
    </section>
  </section>
</template>

<style scoped>
.alert-archive-board {
  display: grid;
  gap: 16px;
}

.archive-summary,
.archive-detail {
  display: grid;
  gap: 16px;
  padding: 20px 22px;
}

.archive-summary__head,
.archive-detail__head {
  display: grid;
  gap: 12px;
}

.archive-summary__hint,
.archive-detail__hint {
  font-size: 0.8125rem;
  line-height: 1.7;
  color: var(--text-muted);
}

.archive-detail__meta {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.archive-detail__metric {
  display: grid;
  gap: 4px;
  padding: 14px 16px;
  border-radius: 18px;
  background: rgba(250, 246, 239, 0.9);
  border: 1px solid rgba(58, 95, 75, 0.1);
}

.archive-detail__metric-label,
.archive-detail__metric-detail {
  font-size: 0.74rem;
  line-height: 1.6;
  color: var(--text-muted);
}

.archive-detail__metric-value {
  font-size: 0.94rem;
  line-height: 1.4;
  color: var(--text-primary);
  overflow-wrap: anywhere;
}

@media (max-width: 720px) {
  .archive-summary,
  .archive-detail {
    padding: 18px 16px;
  }
}
</style>

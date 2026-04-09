<script setup>
import WorkspaceSummary from '../workspace/WorkspaceSummary.vue'

defineProps({
  activeTabLabel: {
    type: String,
    default: '系统全貌',
  },
  activeUserCount: {
    type: Number,
    default: 0,
  },
  loading: {
    type: Boolean,
    default: false,
  },
})
</script>

<template>
  <WorkspaceSummary title="系统观察">
    <template #meta>
      <div class="ink-inline-meta">
        <span class="status-badge status-badge--ok">{{ activeTabLabel }}</span>
        <span class="status-badge status-badge--warning">{{ activeUserCount }} 个活跃用户</span>
        <span class="status-badge" :class="loading ? 'status-badge--warning' : 'status-badge--ok'">
          {{ loading ? '数据刷新中' : '观察就绪' }}
        </span>
      </div>
    </template>
  </WorkspaceSummary>
</template>

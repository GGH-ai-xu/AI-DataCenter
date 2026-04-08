<script setup>
defineProps({
  modelValue: {
    type: String,
    default: 'all',
  },
  items: {
    type: Array,
    default: () => [],
  },
  summaryItems: {
    type: Array,
    default: () => [],
  },
})

defineEmits(['update:modelValue'])
</script>

<template>
  <aside class="tech-card alert-realtime-sidebar">
    <section class="alert-realtime-sidebar__group">
      <div class="section-title" style="font-size: 1rem">类型过滤</div>
      <div class="alert-realtime-sidebar__filters">
        <button
          v-for="item in items"
          :key="item.key"
          type="button"
          class="alert-realtime-sidebar__filter"
          :class="{ 'alert-realtime-sidebar__filter--active': modelValue === item.key }"
          @click="$emit('update:modelValue', item.key)"
        >
          {{ item.label }}
        </button>
      </div>
    </section>

    <section class="alert-realtime-sidebar__group">
      <div class="section-title" style="font-size: 1rem">风险摘要</div>
      <div class="alert-realtime-sidebar__summary">
        <div
          v-for="item in summaryItems"
          :key="item.key"
          class="alert-realtime-sidebar__summary-item"
        >
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </div>
      </div>
    </section>

    <section class="alert-realtime-sidebar__group">
      <div class="section-title" style="font-size: 1rem">处置提示</div>
      <p class="alert-realtime-sidebar__hint">
        实时流只保留未确认告警。先按类型聚焦当前风险，再在主区逐条确认，避免历史记录干扰值守判断。
      </p>
    </section>
  </aside>
</template>

<style scoped>
.alert-realtime-sidebar {
  padding: 18px 20px;
  display: grid;
  gap: 18px;
}

.alert-realtime-sidebar__group {
  display: grid;
  gap: 10px;
}

.alert-realtime-sidebar__filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.alert-realtime-sidebar__filter {
  border: 1px solid var(--border-color);
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-secondary);
  border-radius: 999px;
  padding: 8px 12px;
  font-size: 0.75rem;
  line-height: 1.2;
}

.alert-realtime-sidebar__filter--active {
  border-color: rgba(0, 212, 170, 0.24);
  background: rgba(0, 212, 170, 0.08);
  color: var(--text-primary);
}

.alert-realtime-sidebar__summary {
  display: grid;
  gap: 8px;
}

.alert-realtime-sidebar__summary-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--border-color);
  font-size: 0.78rem;
  color: var(--text-secondary);
}

.alert-realtime-sidebar__summary-item strong {
  font-size: 0.92rem;
  color: var(--text-primary);
}

.alert-realtime-sidebar__hint {
  font-size: 0.78rem;
  line-height: 1.7;
  color: var(--text-muted);
  margin: 0;
}
</style>

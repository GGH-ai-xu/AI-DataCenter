<script setup>
defineProps({
  items: {
    type: Array,
    default: () => [],
  },
})
</script>

<template>
  <div class="alert-summary-strip">
    <div
      v-for="item in items"
      :key="item.key"
      class="alert-summary-strip__item"
      :class="`alert-summary-strip__item--${item.tone || 'neutral'}`"
    >
      <div class="alert-summary-strip__label">{{ item.label }}</div>
      <div class="alert-summary-strip__value">{{ item.value }}</div>
      <div class="alert-summary-strip__detail">{{ item.detail }}</div>
    </div>
  </div>
</template>

<style scoped>
.alert-summary-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.alert-summary-strip__item {
  padding: 12px 14px;
  border-radius: 16px;
  border: 1px solid rgba(58, 95, 75, 0.08);
  background: rgba(255, 252, 247, 0.74);
}

.alert-summary-strip__item--critical {
  border-color: rgba(196, 30, 58, 0.16);
}

.alert-summary-strip__item--warning {
  border-color: rgba(184, 134, 11, 0.16);
}

.alert-summary-strip__item--ok {
  border-color: rgba(46, 139, 87, 0.16);
}

.alert-summary-strip__label,
.alert-summary-strip__detail {
  font-size: 0.72rem;
  line-height: 1.65;
  color: var(--text-muted);
}

.alert-summary-strip__value {
  margin: 4px 0;
  font-size: 1.35rem;
  font-weight: 700;
  color: var(--text-primary);
}

@media (max-width: 960px) {
  .alert-summary-strip {
    grid-template-columns: 1fr;
  }
}
</style>

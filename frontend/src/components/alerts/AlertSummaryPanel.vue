<script setup>
defineProps({
  criticalCount: {
    type: Number,
    default: 0,
  },
  pendingCount: {
    type: Number,
    default: 0,
  },
  realtimeCount: {
    type: Number,
    default: 0,
  },
})
</script>

<template>
  <div class="alert-summary-panel">
    <div class="alert-summary-card">
      <div class="alert-summary-card__label">严重告警</div>
      <div class="alert-summary-card__value">{{ criticalCount }}</div>
      <div class="alert-summary-card__hint">需要优先处理的高风险信号</div>
    </div>
    <div class="alert-summary-card">
      <div class="alert-summary-card__label">未确认</div>
      <div class="alert-summary-card__value">{{ pendingCount }}</div>
      <div class="alert-summary-card__hint">等待确认和闭环的历史记录</div>
    </div>
    <div class="alert-summary-card">
      <div class="alert-summary-card__label">实时波动</div>
      <div class="alert-summary-card__value">{{ realtimeCount }}</div>
      <div class="alert-summary-card__hint">来自当前实时流的近期告警</div>
    </div>
  </div>
</template>

<style scoped>
.alert-summary-panel {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.alert-summary-card {
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid rgba(58, 95, 75, 0.08);
  background: rgba(255, 252, 247, 0.66);
}

.alert-summary-card__label,
.alert-summary-card__hint {
  font-size: 0.74rem;
  color: var(--text-muted);
  line-height: 1.7;
}

.alert-summary-card__value {
  margin: 6px 0;
  font-size: 1.6rem;
  font-weight: 700;
  color: var(--text-primary);
}

@media (max-width: 960px) {
  .alert-summary-panel {
    grid-template-columns: 1fr;
  }
}
</style>

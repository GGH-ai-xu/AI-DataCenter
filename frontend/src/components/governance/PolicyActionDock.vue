<script setup>
const props = defineProps({
  advancedTitle: { type: String, required: true },
  autoEnabled: { type: Boolean, required: true },
  executionBanner: { type: Object, required: true },
  executionReady: { type: Boolean, required: true },
  riskAcknowledged: { type: Boolean, required: true },
  scheduleResult: { type: Object, default: null },
  showAdvanced: { type: Boolean, required: true },
  handlers: { type: Object, required: true },
})

const emit = defineEmits(['toggle-advanced'])
</script>

<template>
  <section class="tech-card policy-action-dock">
    <div class="policy-action-dock__section">
      <div class="policy-action-dock__title">调度控制</div>
      <div class="execution-banner" :class="`execution-banner--${props.executionBanner.tone}`">
        <strong>执行提示</strong>
        <span>{{ props.executionBanner.detail }}</span>
      </div>

      <label class="execution-check">
        <input
          :checked="props.riskAcknowledged"
          type="checkbox"
          @change="props.handlers.updateRiskAcknowledged($event.target.checked)"
        />
        <span>我已确认本次调度会直接执行真实治理动作</span>
      </label>

      <button
        type="button"
        class="action-card action-card--primary"
        :disabled="!props.executionReady"
        @click="props.handlers.runOnce"
      >
        <span class="action-card__icon">▶</span>
        <span class="action-card__body">
          <strong>执行一次调度</strong>
          <small>在当前预算策略下运行一次真实调度</small>
        </span>
      </button>

      <button type="button" class="action-card" @click="props.handlers.toggleAuto">
        <span class="action-card__icon">⏻</span>
        <span class="action-card__body">
          <strong>{{ props.autoEnabled ? '关闭自动调度' : '开启自动调度' }}</strong>
          <small>当前状态：{{ props.autoEnabled ? '已开启' : '已关闭' }}</small>
        </span>
      </button>

      <div v-if="props.scheduleResult" class="policy-action-dock__summary">
        最近一次调度已更新，完整结果请到治理复盘查看。
      </div>
    </div>

    <div class="policy-action-dock__section">
      <div class="policy-action-dock__title">{{ props.advancedTitle }}</div>
      <button type="button" class="action-card action-card--quiet" @click="emit('toggle-advanced')">
        <span class="action-card__icon">🛡</span>
        <span class="action-card__body">
          <strong>{{ props.showAdvanced ? '收起高级策略' : '展开高级策略' }}</strong>
          <small>查看 GPU 限功率与用户规则控制</small>
        </span>
      </button>
    </div>
  </section>
</template>

<style scoped>
.policy-action-dock {
  display: grid;
  gap: 16px;
  padding: 18px;
}

.policy-action-dock__section {
  display: grid;
  gap: 12px;
}

.policy-action-dock__title {
  font-size: 0.82rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.execution-banner,
.policy-action-dock__summary,
.execution-check {
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid var(--border-color);
  background: rgba(255, 255, 255, 0.04);
  font-size: 0.78rem;
  line-height: 1.7;
  color: var(--text-secondary);
}

.execution-banner {
  display: grid;
  gap: 4px;
}

.execution-check {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.execution-check input {
  margin-top: 2px;
}

.execution-banner strong {
  color: var(--text-primary);
}

.execution-banner--warning {
  border-color: rgba(244, 185, 93, 0.28);
  background: rgba(244, 185, 93, 0.1);
}

.execution-banner--critical {
  border-color: rgba(255, 111, 150, 0.28);
  background: rgba(255, 111, 150, 0.1);
}

.execution-banner--ok {
  border-color: rgba(0, 212, 170, 0.2);
}

.action-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid var(--border-color);
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-primary);
  text-align: left;
}

.action-card:disabled {
  opacity: 0.52;
  cursor: not-allowed;
}

.action-card--primary {
  border-color: rgba(127, 142, 255, 0.4);
  background: rgba(127, 142, 255, 0.15);
}

.action-card--quiet {
  opacity: 0.92;
}

.action-card__icon {
  width: 34px;
  height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.06);
}

.action-card__body {
  display: grid;
  gap: 4px;
}

.action-card__body small {
  font-size: 0.75rem;
  line-height: 1.6;
  color: var(--text-secondary);
}
</style>

<script setup>
const props = defineProps({
  advancedTitle: { type: String, required: true },
  rulesUsers: { type: Array, default: () => [] },
  gpuTargets: { type: Array, default: () => [] },
  powerInputs: { type: Object, required: true },
  executionReady: { type: Boolean, required: true },
  userRulesComponent: { type: Object, required: true },
  handlers: { type: Object, required: true },
})
</script>

<template>
  <section class="tech-card policy-advanced-panel">
    <div class="policy-advanced-panel__head">
      <div class="policy-advanced-panel__title">{{ props.advancedTitle }}</div>
      <div class="policy-advanced-panel__hint">默认折叠的高级控制，避免与预算主控区争抢首屏注意力。</div>
    </div>

    <section class="policy-advanced-panel__section">
      <div class="policy-advanced-panel__section-title">GPU 限功率</div>
      <div class="policy-advanced-panel__hint">写入限功率前需要先在右侧确认真实执行风险。</div>
      <div v-if="!props.gpuTargets.length" class="policy-advanced-panel__empty">当前没有可配置的 GPU。</div>
      <div v-for="gpuIndex in props.gpuTargets" :key="gpuIndex" class="policy-advanced-panel__gpu-line">
        <span class="policy-advanced-panel__gpu-label">GPU {{ gpuIndex }}</span>
        <input
          v-model.number="props.powerInputs[gpuIndex]"
          type="number"
          class="task-input"
          min="100"
          max="350"
          placeholder="输入功率上限"
        />
        <button
          type="button"
          class="action-card"
          :disabled="!props.executionReady"
          @click="props.handlers.setPower(gpuIndex)"
        >
          写入限功率
        </button>
      </div>
    </section>

    <section class="policy-advanced-panel__section">
      <div class="policy-advanced-panel__section-title">用户额度规则</div>
      <component
        :is="props.userRulesComponent"
        :users="props.rulesUsers"
        @save="props.handlers.saveRule"
        @reset="props.handlers.resetRule"
      />
    </section>
  </section>
</template>

<style scoped>
.policy-advanced-panel { display: grid; gap: 16px; padding: 18px; }
.policy-advanced-panel__head, .policy-advanced-panel__section { display: grid; gap: 10px; }
.policy-advanced-panel__title, .policy-advanced-panel__gpu-label { color: var(--text-primary); font-weight: 700; }
.policy-advanced-panel__hint, .policy-advanced-panel__empty { font-size: 0.78rem; line-height: 1.7; color: var(--text-secondary); }
.policy-advanced-panel__section-title { font-size: 0.8rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--text-muted); }
.policy-advanced-panel__gpu-line { display: grid; grid-template-columns: 96px minmax(0, 1fr) auto; gap: 10px; align-items: center; padding: 12px 14px; border-radius: 14px; background: rgba(255, 255, 255, 0.04); border: 1px solid var(--border-color); }
.task-input, .action-card { border-radius: 12px; }
.task-input { padding: 10px 12px; border: 1px solid var(--border-color); background: rgba(255, 255, 255, 0.04); color: var(--text-primary); }
.action-card { padding: 10px 14px; border: 1px solid var(--border-color); background: rgba(255, 255, 255, 0.05); color: var(--text-primary); }
.action-card:disabled { opacity: 0.52; cursor: not-allowed; }
@media (max-width: 760px) { .policy-advanced-panel__gpu-line { grid-template-columns: 1fr; } }
</style>

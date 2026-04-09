<script setup>
const props = defineProps({
  budgetTitle: { type: String, required: true },
  carbonTitle: { type: String, required: true },
  budget: { type: Object, required: true },
  budgetDraft: { type: Object, required: true },
  budgetCardState: { type: Object, required: true },
  carbonBudget: { type: Object, required: true },
  carbonDraft: { type: Object, required: true },
  carbonCardState: { type: Object, required: true },
  formatActionLabel: { type: Function, required: true },
  formatActionTarget: { type: Function, required: true },
  handlers: { type: Object, required: true },
})

function buildBarStyle(value) {
  const width = Math.max(0, Math.min(100, Number(value || 0)))
  return { width: `${width}%` }
}

function recentActions(actions = []) {
  return Array.isArray(actions) ? actions.slice(0, 3) : []
}
</script>

<template>
  <section class="policy-budget-console">
    <article class="tech-card policy-panel" :class="{ 'policy-panel--pending': props.budgetCardState.pending }">
      <div class="policy-panel__topline">
        <div>
          <p class="policy-panel__eyebrow">{{ props.budgetTitle }}</p>
          <h3 class="policy-panel__value">{{ Number(props.budget.total_power_budget || 0) }}W</h3>
        </div>
        <span class="policy-budget-console__badge policy-panel__badge" :class="`policy-panel__badge--${props.budgetCardState.badgeTone}`">
          {{ props.budgetCardState.badgeLabel || '待应用' }}
        </span>
      </div>

      <label class="policy-switch">
        <input v-model="props.budgetDraft.enabled" type="checkbox" />
        <span class="policy-switch__track">
          <span class="policy-switch__thumb" />
        </span>
        <span class="policy-switch__meta">
          <strong>启用总功率预算</strong>
          <small>{{ props.budgetDraft.enabled ? '当前策略参与调度约束' : '当前策略仅保留草稿，不参与调度' }}</small>
        </span>
      </label>

      <div class="policy-panel__meter">
        <div class="policy-panel__meter-head">
          <strong>当前功耗 {{ Number(props.budget.current_total_power || 0) }}W</strong>
          <span>剩余 {{ Number(props.budget.remaining_power || 0) }}W</span>
        </div>
        <div class="policy-panel__bar">
          <span class="policy-panel__fill" :class="{ 'policy-panel__fill--danger': props.budget.is_exceeded }" :style="buildBarStyle(props.budget.usage_pct)" />
        </div>
      </div>

      <div class="policy-panel__stats">
        <div>
          <span>受控 GPU</span>
          <strong>{{ Number(props.budget.managed_gpu_count || 0) }} 张</strong>
        </div>
        <div>
          <span>预算利用率</span>
          <strong>{{ Number(props.budget.usage_pct || 0).toFixed(1) }}%</strong>
        </div>
      </div>

      <label class="policy-panel__field">
        <span>预算值</span>
        <input v-model.number="props.budgetDraft.total_power_budget" type="number" min="100" step="10" />
      </label>

      <button type="button" class="action-card" :class="`action-card--${props.budgetCardState.actionTone}`" @click="props.handlers.saveBudget">
        <span class="action-card__icon">⚡</span>
        <span class="action-card__body">
          <strong>{{ props.budgetCardState.actionLabel }}</strong>
          <small>{{ props.budgetCardState.pending ? '草稿尚未写入，点击后立即提交。' : '当前配置已同步，可再次提交确认。' }}</small>
        </span>
      </button>

      <div v-if="recentActions(props.budget.last_actions).length" class="policy-panel__actions">
        <div class="policy-panel__section-title">最近调度动作</div>
        <div v-for="(action, index) in recentActions(props.budget.last_actions)" :key="`${action.action}-${index}`" class="policy-panel__action-line">
          <strong>{{ props.formatActionLabel(action) }}</strong>
          <span>{{ props.formatActionTarget(action) }}</span>
        </div>
      </div>
    </article>

    <article class="tech-card policy-panel" :class="{ 'policy-panel--pending': props.carbonCardState.pending }">
      <div class="policy-panel__topline">
        <div>
          <p class="policy-panel__eyebrow">{{ props.carbonTitle }}</p>
          <h3 class="policy-panel__value">{{ Number(props.carbonBudget.daily_budget_kg || 0) }} kgCO2</h3>
        </div>
        <span class="policy-budget-console__badge policy-panel__badge" :class="`policy-panel__badge--${props.carbonCardState.badgeTone}`">
          {{ props.carbonCardState.badgeLabel || '待应用' }}
        </span>
      </div>

      <label class="policy-switch">
        <input v-model="props.carbonDraft.enabled" type="checkbox" />
        <span class="policy-switch__track">
          <span class="policy-switch__thumb" />
        </span>
        <span class="policy-switch__meta">
          <strong>启用碳预算治理</strong>
          <small>{{ props.carbonDraft.enabled ? '调度会同步参考碳排压力' : '碳预算只保留监测，不会参与调度' }}</small>
        </span>
      </label>

      <div class="policy-panel__meter">
        <div class="policy-panel__meter-head">
          <strong>当前累计 {{ Number(props.carbonBudget.accumulated_carbon_kg || 0).toFixed(1) }} kg</strong>
          <span>预测全天 {{ Number(props.carbonBudget.projected_daily_carbon_kg || 0).toFixed(1) }} kg</span>
        </div>
        <div class="policy-panel__bar">
          <span class="policy-panel__fill" :class="{ 'policy-panel__fill--danger': props.carbonBudget.is_exceeded }" :style="buildBarStyle(props.carbonBudget.usage_pct)" />
        </div>
      </div>

      <div class="policy-panel__stats">
        <div>
          <span>累计耗电</span>
          <strong>{{ Number(props.carbonBudget.accumulated_kwh || 0).toFixed(1) }} kWh</strong>
        </div>
        <div>
          <span>当前功耗</span>
          <strong>{{ Number(props.carbonBudget.current_power_w || 0) }}W</strong>
        </div>
      </div>

      <label class="policy-panel__field">
        <span>每日上限</span>
        <input v-model.number="props.carbonDraft.daily_budget_kg" type="number" min="1" step="1" />
      </label>

      <button type="button" class="action-card" :class="`action-card--${props.carbonCardState.actionTone}`" @click="props.handlers.saveCarbon">
        <span class="action-card__icon">🌿</span>
        <span class="action-card__body">
          <strong>{{ props.carbonCardState.actionLabel }}</strong>
          <small>{{ props.carbonCardState.pending ? '待应用的碳预算草稿将立即写入。' : '当前碳预算已同步。' }}</small>
        </span>
      </button>
    </article>
  </section>
</template>

<style scoped>
.policy-budget-console { display: grid; gap: 16px; }
.policy-panel { display: grid; gap: 14px; padding: 20px; border: 1px solid rgba(127, 142, 255, 0.12); background: linear-gradient(180deg, rgba(13, 19, 43, 0.96), rgba(9, 13, 31, 0.96)); }
.policy-panel--pending { border-color: rgba(244, 185, 93, 0.4); box-shadow: 0 18px 42px rgba(244, 185, 93, 0.08); }
.policy-panel__topline, .policy-panel__meter-head, .policy-panel__stats, .policy-panel__action-line { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.policy-panel__eyebrow, .policy-panel__section-title, .policy-panel__field span, .policy-panel__stats span { font-size: 0.76rem; letter-spacing: 0.08em; text-transform: uppercase; color: var(--text-muted); }
.policy-panel__value, .policy-panel__stats strong, .policy-switch__meta strong, .policy-panel__action-line strong { color: var(--text-primary); }
.policy-panel__value { margin: 6px 0 0; font-size: clamp(1.8rem, 3vw, 2.6rem); }
.policy-panel__badge { padding: 7px 12px; border-radius: 999px; font-size: 0.78rem; color: var(--text-primary); background: rgba(255, 255, 255, 0.08); }
.policy-panel__badge--pending { background: rgba(244, 185, 93, 0.16); }
.policy-switch, .policy-panel__field { display: grid; grid-template-columns: auto auto minmax(0, 1fr); gap: 12px; align-items: center; padding: 14px; border-radius: 16px; border: 1px solid var(--border-color); background: rgba(255, 255, 255, 0.04); }
.policy-switch input { position: absolute; opacity: 0; pointer-events: none; }
.policy-switch__track { width: 52px; height: 30px; padding: 3px; display: inline-flex; align-items: center; border-radius: 999px; background: rgba(255, 255, 255, 0.1); }
.policy-switch input:checked + .policy-switch__track { justify-content: flex-end; background: rgba(0, 212, 170, 0.22); }
.policy-switch__thumb { width: 24px; height: 24px; border-radius: 50%; background: #fff; }
.policy-switch__meta, .action-card__body, .policy-panel__actions { display: grid; gap: 4px; }
.policy-switch__meta small, .action-card__body small, .policy-panel__meter-head span, .policy-panel__action-line span { color: var(--text-secondary); line-height: 1.6; }
.policy-panel__bar { height: 10px; overflow: hidden; border-radius: 999px; background: rgba(255, 255, 255, 0.08); }
.policy-panel__fill { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, #4fc3ff, #8a7dff); }
.policy-panel__fill--danger { background: linear-gradient(90deg, #ff8a65, #ff5e8a); }
.policy-panel__field { grid-template-columns: 96px minmax(0, 1fr); }
.policy-panel__field input, .action-card { width: 100%; border-radius: 14px; }
.policy-panel__field input { padding: 12px 14px; border: 1px solid var(--border-color); background: rgba(4, 8, 22, 0.8); color: var(--text-primary); }
.action-card { display: flex; align-items: center; gap: 12px; padding: 14px; border: 1px solid var(--border-color); background: rgba(255, 255, 255, 0.05); text-align: left; color: var(--text-primary); }
.action-card--primary { border-color: rgba(127, 142, 255, 0.42); background: rgba(127, 142, 255, 0.16); }
.action-card__icon { width: 38px; height: 38px; display: inline-flex; align-items: center; justify-content: center; border-radius: 12px; background: rgba(255, 255, 255, 0.08); }
@media (max-width: 720px) {
  .policy-switch, .policy-panel__field { grid-template-columns: 1fr; }
  .policy-panel__topline, .policy-panel__meter-head, .policy-panel__stats, .policy-panel__action-line { flex-direction: column; align-items: flex-start; }
}
</style>

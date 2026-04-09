<script setup>
import FairnessGaugeCard from '../tasks/FairnessGaugeCard.vue'

const DEFAULT_PRIORITY = 'normal'

const props = defineProps({
  execution: {
    type: Object,
    default: () => ({}),
  },
  executionSummary: {
    type: String,
    required: true,
  },
  fairnessTitle: {
    type: String,
    required: true,
  },
  yieldTitle: {
    type: String,
    required: true,
  },
  fairnessOverview: {
    type: Object,
    default: () => ({}),
  },
  fairnessUsers: {
    type: Array,
    default: () => [],
  },
  yieldCandidates: {
    type: Array,
    default: () => [],
  },
  fairnessRecommendations: {
    type: Array,
    default: () => [],
  },
  priorityColors: {
    type: Object,
    required: true,
  },
  yieldLimit: {
    type: Number,
    required: true,
  },
})

const emit = defineEmits(['update:riskAcknowledged'])

function priorityTone(priority = DEFAULT_PRIORITY) {
  return props.priorityColors[priority] || props.priorityColors.normal
}
</script>

<template>
  <div class="governance-actions-side">
    <section class="tech-card panel-card">
      <div class="panel-card__title">执行确认</div>
      <div class="mode-box">
        <div class="mode-box__mode">
          <span class="mode-box__badge">真实执行</span>
          <span class="mode-box__mode-hint">治理工作区当前只提供真实执行，不再提供演练路径。</span>
        </div>
        <label class="mode-box__ack">
          <input
            :checked="props.execution.riskAcknowledged"
            type="checkbox"
            @change="emit('update:riskAcknowledged', $event.target.checked)"
          />
          我已确认接下来的治理动作会直接作用于真实环境
        </label>
        <div class="mode-box__hint">{{ props.executionSummary }}</div>
      </div>
    </section>

    <section class="fairness-summary">
      <div class="fairness-summary__title">{{ props.fairnessTitle }}</div>
      <FairnessGaugeCard :overview="props.fairnessOverview" :users="props.fairnessUsers" />
    </section>

    <section class="tech-card panel-card">
      <div class="panel-card__title">{{ props.yieldTitle }}</div>
      <div class="yield-list">
        <div
          v-for="candidate in props.yieldCandidates.slice(0, props.yieldLimit)"
          :key="candidate.pid"
          class="yield-item"
        >
          <div class="yield-item__top">
            <span class="yield-item__pid">PID {{ candidate.pid }}</span>
            <span
              class="yield-item__priority"
              :style="{ color: priorityTone(candidate.priority).color, background: priorityTone(candidate.priority).bg }"
            >
              {{ priorityTone(candidate.priority).label }}
            </span>
          </div>
          <div class="yield-item__reason">{{ candidate.yield_reason || '暂无额外说明。' }}</div>
        </div>
        <div v-if="!props.yieldCandidates.length" class="panel-card__item">当前没有需要优先让路的任务。</div>
      </div>
    </section>

    <section class="tech-card panel-card">
      <div class="panel-card__title">治理建议</div>
      <div class="panel-card__list">
        <div v-for="(item, index) in props.fairnessRecommendations" :key="index" class="panel-card__item">
          {{ item }}
        </div>
        <div v-if="!props.fairnessRecommendations.length" class="panel-card__item">
          当前没有额外治理建议。
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.governance-actions-side,
.mode-box,
.yield-list,
.panel-card__list {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.governance-actions-side {
  flex-direction: column;
}

.panel-card {
  margin-bottom: 14px;
  padding: 18px;
}

.panel-card__title {
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 12px;
}

.panel-card__item,
.yield-item {
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--border-color);
  font-size: 0.78rem;
  line-height: 1.7;
  color: var(--text-secondary);
}

.fairness-summary {
  display: grid;
  gap: 8px;
  margin-bottom: 14px;
}

.fairness-summary__title,
.mode-box__ack,
.mode-box__hint {
  font-size: 0.75rem;
  color: var(--text-muted);
  line-height: 1.6;
}

.fairness-summary__title {
  padding-left: 6px;
  letter-spacing: 0.04em;
}

.yield-list,
.panel-card__list {
  flex-direction: column;
}

.yield-item__top {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}

.yield-item__pid {
  font-weight: 700;
  color: var(--accent-danger);
}

.yield-item__priority {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 0.6875rem;
  font-weight: 700;
}

.mode-box {
  flex-direction: column;
  align-items: flex-start;
}

.mode-box__mode {
  display: grid;
  gap: 6px;
}

.mode-box__badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 34px;
  padding: 0 12px;
  border-radius: 999px;
  border: 1px solid rgba(244, 185, 93, 0.24);
  background: rgba(244, 185, 93, 0.12);
  color: var(--text-primary);
  font-size: 0.74rem;
  font-weight: 700;
  letter-spacing: 0.05em;
}

.mode-box__mode-hint {
  font-size: 0.78rem;
  line-height: 1.6;
  color: var(--text-secondary);
}

.mode-box__hint {
  max-width: 360px;
  padding: 8px 12px;
  border-radius: 999px;
  color: var(--text-secondary);
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--border-color);
}
</style>

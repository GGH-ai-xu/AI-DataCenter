<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  model: {
    type: Object,
    required: true,
  },
})

const showHealthyChecks = ref(false)
const displayedPriorityChecks = computed(() => props.model.priorityChecks || [])
const displayedHealthyChecks = computed(() => props.model.healthyChecks || [])
const actionCheck = computed(() => props.model.primaryCheck || null)
const progressBadgeClass = computed(() => props.model.hasChecks ? 'status-badge--ok' : '')
const actionEyebrow = computed(() => actionCheck.value ? '当前需处理项' : '当前无待处理项')
const actionBadgeLabel = computed(() => {
  if (actionCheck.value) {
    return actionCheck.value.label
  }
  return props.model.hasChecks ? '状态正常' : '等待巡检'
})
const actionBadgeClass = computed(() => {
  if (!actionCheck.value) {
    return props.model.hasChecks ? 'status-badge--ok' : ''
  }
  return actionCheck.value.status === 'critical' ? 'status-badge--critical' : 'status-badge--warning'
})
const actionTitle = computed(() => {
  if (actionCheck.value) {
    return actionCheck.value.detail
  }
  if (!props.model.hasChecks) {
    return '等待首轮巡检完成后再查看明细。'
  }
  return '当前巡检未发现 critical 或 warning 项。'
})
</script>

<template>
  <section class="dashboard-health">
    <div class="dashboard-health__board">
      <header class="dashboard-health__board-head">
        <div class="dashboard-health__summary">
          <div class="section-title">主体巡检</div>
          <strong>{{ props.model.summary.title }}</strong>
          <p>{{ props.model.summary.message }}</p>
        </div>
        <span class="status-badge dashboard-health__progress" :class="progressBadgeClass">
          {{ props.model.healthProgressLabel }}
        </span>
      </header>

      <div class="dashboard-health__grid">
        <article
          v-for="item in props.model.factCards"
          :key="item.label"
          class="dashboard-health__item"
          :class="[
            item.tone === 'warning' ? 'dashboard-health__item--warning' : '',
            item.tone === 'ok' ? 'dashboard-health__item--ok' : '',
          ]"
        >
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </article>
      </div>

      <div class="dashboard-health__focus-grid">
        <article class="dashboard-health__focus-card dashboard-health__focus-card--signal">
          <span class="dashboard-health__eyebrow">{{ actionEyebrow }}</span>
          <div class="dashboard-health__focus-copy">
            <span class="status-badge" :class="actionBadgeClass">{{ actionBadgeLabel }}</span>
            <strong>{{ actionTitle }}</strong>
          </div>
          <p v-if="props.model.remainingPriorityCount > 0">
            另有 {{ props.model.remainingPriorityCount }} 项待关注。
          </p>
        </article>

        <article class="dashboard-health__focus-card dashboard-health__focus-card--control">
          <span class="dashboard-health__eyebrow">巡检明细</span>
          <div class="dashboard-health__focus-copy">
            <strong>{{ props.model.hasChecks ? '展开完整检查清单' : '等待巡检结果' }}</strong>
            <p>
              {{ props.model.hasChecks
                ? '查看全部异常项与健康项，不再把明细直接铺满首屏。'
                : '当前还没有可展开的检查结果。' }}
            </p>
          </div>
          <button
            v-if="props.model.hasChecks"
            type="button"
            class="dashboard-health__toggle"
            @click="showHealthyChecks = !showHealthyChecks"
          >
            {{ showHealthyChecks ? '收起健康项' : '查看全部健康项' }}
          </button>
        </article>
      </div>
    </div>

    <div v-if="showHealthyChecks && props.model.hasChecks" class="dashboard-health__details">
      <article
        v-for="item in displayedPriorityChecks"
        :key="item.key"
        class="dashboard-health__detail dashboard-health__detail--priority"
      >
        <span
          class="status-badge"
          :class="item.status === 'critical' ? 'status-badge--critical' : 'status-badge--warning'"
        >
          {{ item.label }}
        </span>
        <div>{{ item.detail }}</div>
      </article>

      <article
        v-for="item in displayedHealthyChecks"
        :key="item.key"
        class="dashboard-health__detail"
      >
        <span class="status-badge status-badge--ok">{{ item.label }}</span>
        <div>{{ item.detail }}</div>
      </article>
    </div>
  </section>
</template>

<style scoped>
.dashboard-health,
.dashboard-health__board,
.dashboard-health__summary,
.dashboard-health__grid,
.dashboard-health__focus-grid,
.dashboard-health__details,
.dashboard-health__focus-card {
  display: grid;
  gap: 16px;
}

.dashboard-health {
  gap: 14px;
}

.dashboard-health__board {
  gap: 18px;
  padding: 20px;
  border-radius: 24px;
  border: 1px solid var(--console-border, rgba(255, 255, 255, 0.08));
  background:
    var(--surface-overlay),
    var(--bg-strong);
}

.dashboard-health__board-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.dashboard-health__summary {
  gap: 10px;
}

.dashboard-health__summary strong {
  font-size: 1.26rem;
  color: var(--console-text, var(--text-primary));
}

.dashboard-health__summary p,
.dashboard-health__detail div {
  margin: 0;
  font-size: 0.9rem;
  line-height: 1.7;
  color: var(--console-text-secondary, var(--text-secondary));
}

.dashboard-health__progress {
  white-space: nowrap;
}

.dashboard-health__focus-copy > .status-badge,
.dashboard-health__detail > .status-badge {
  justify-self: start;
  width: fit-content;
  max-width: 100%;
}

.dashboard-health__grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.dashboard-health__item,
.dashboard-health__focus-card,
.dashboard-health__detail {
  border-radius: 18px;
  border: 1px solid var(--console-border, rgba(255, 255, 255, 0.08));
}

.dashboard-health__item {
  display: grid;
  gap: 8px;
  min-height: 108px;
  padding: 16px;
  background: var(--bg-card);
}

.dashboard-health__item span,
.dashboard-health__eyebrow {
  font-size: 0.76rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--console-text-muted, var(--text-muted));
}

.dashboard-health__item strong,
.dashboard-health__focus-card strong {
  font-size: 1.04rem;
  color: var(--console-text, var(--text-primary));
}

.dashboard-health__item--warning {
  background: var(--state-warning-bg);
  border-color: var(--state-warning-border);
}

.dashboard-health__item--ok {
  background: var(--state-ok-bg);
  border-color: var(--state-ok-border);
}

.dashboard-health__focus-grid {
  grid-template-columns: minmax(0, 1.15fr) minmax(260px, 0.85fr);
  gap: 12px;
}

.dashboard-health__focus-card {
  gap: 12px;
  padding: 16px;
  background: var(--bg-card);
}

.dashboard-health__focus-card--signal {
  background: var(--bg-card);
}

.dashboard-health__focus-card--control {
  align-content: start;
}

.dashboard-health__focus-copy {
  display: grid;
  gap: 10px;
}

.dashboard-health__focus-copy p {
  margin: 0;
  font-size: 0.9rem;
  line-height: 1.7;
  color: var(--console-text-secondary, var(--text-secondary));
}

.dashboard-health__toggle {
  justify-self: start;
  width: fit-content;
  min-width: 148px;
  border: 0;
  border-radius: 14px;
  padding: 12px 18px;
  font: inherit;
  color: var(--state-ok-text);
  background: var(--state-ok-bg);
  cursor: pointer;
}

.dashboard-health__toggle:hover {
  background: var(--bg-card-hover);
}

.dashboard-health__details {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.dashboard-health__detail {
  display: grid;
  gap: 10px;
  padding: 16px;
  background: var(--bg-card);
}

.dashboard-health__detail--priority {
  border-color: var(--state-warning-border);
}

@media (max-width: 980px) {
  .dashboard-health__board-head,
  .dashboard-health__focus-grid {
    display: grid;
  }

  .dashboard-health__grid,
  .dashboard-health__details {
    grid-template-columns: 1fr;
  }
}
</style>

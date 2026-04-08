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
</script>

<template>
  <section class="tech-card dashboard-health">
    <div class="dashboard-health__hero">
      <div class="section-title">主体巡检</div>
      <strong>{{ props.model.summary.title }}</strong>
      <p>{{ props.model.summary.message }}</p>
    </div>

    <div class="dashboard-health__grid">
      <div
        v-for="item in props.model.factCards"
        :key="item.label"
        class="dashboard-health__item"
      >
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </div>
    </div>

    <div class="dashboard-health__checks">
      <div
        v-for="item in displayedPriorityChecks"
        :key="item.key"
        class="dashboard-health__check"
      >
        <span
          class="status-badge"
          :class="item.status === 'critical' ? 'status-badge--critical' : 'status-badge--warning'"
        >
          {{ item.label }}
        </span>
        <div>{{ item.detail }}</div>
      </div>
      <div
        v-if="!displayedPriorityChecks.length"
        class="dashboard-health__check"
      >
        <span class="status-badge status-badge--ok">当前无异常项</span>
        <div>当前巡检未发现 critical 或 warning 项。</div>
      </div>
    </div>

    <button type="button" class="btn-tech" @click="showHealthyChecks = !showHealthyChecks">
      {{ showHealthyChecks ? '收起健康项' : '查看全部健康项' }}
    </button>

    <div v-if="showHealthyChecks" class="dashboard-health__checks">
      <div
        v-for="item in displayedHealthyChecks"
        :key="item.key"
        class="dashboard-health__check"
      >
        <span class="status-badge status-badge--ok">{{ item.label }}</span>
        <div>{{ item.detail }}</div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.dashboard-health,
.dashboard-health__grid,
.dashboard-health__checks {
  display: grid;
  gap: 16px;
}

.dashboard-health {
  padding: 22px 24px;
}

.dashboard-health__hero strong,
.dashboard-health__item strong {
  font-size: 1.08rem;
  color: var(--console-text, var(--text-primary));
}

.dashboard-health__hero p,
.dashboard-health__check div {
  font-size: 0.9rem;
  line-height: 1.8;
  color: var(--console-text-secondary, var(--text-secondary));
}

.dashboard-health__grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.dashboard-health__item,
.dashboard-health__check {
  display: grid;
  gap: 8px;
  padding: 16px;
  border-radius: 18px;
  border: 1px solid var(--console-border, rgba(255, 255, 255, 0.08));
  background: var(--console-surface, rgba(255, 255, 255, 0.04));
}

.dashboard-health__item span {
  font-size: 0.76rem;
  color: var(--console-text-muted, var(--text-muted));
}

@media (max-width: 980px) {
  .dashboard-health__grid {
    grid-template-columns: 1fr;
  }
}
</style>

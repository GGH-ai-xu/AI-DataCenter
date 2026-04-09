<script setup>
import { useRouter } from 'vue-router'

const props = defineProps({
  model: {
    type: Object,
    required: true,
  },
})

const router = useRouter()

function toneClass(tone) {
  return `dashboard-tone--${tone || 'ok'}`
}
</script>

<template>
  <div class="overview-layout">
    <section class="tech-card overview-card overview-card--wide">
      <div class="section-title">导入范围速记</div>
      <div class="overview-quick-strip">
        <article
          v-for="item in props.model.quickStats"
          :key="item.label"
          class="overview-quick-item"
        >
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
          <small>{{ item.hint }}</small>
        </article>
      </div>
    </section>

    <section class="tech-card overview-card">
      <div class="section-title">页面定位</div>
      <p class="overview-copy">{{ props.model.summaryLine }}</p>
      <div class="overview-note">
        首页只负责摘要和分流，详细治理与诊断请进入对应专页处理。
      </div>
    </section>

    <section class="tech-card overview-card">
      <div class="section-title">工作分流</div>
      <div class="overview-routes">
        <button
          v-for="item in props.model.routeCards"
          :key="item.path"
          type="button"
          class="overview-route"
          @click="router.push(item.path)"
        >
          <strong>{{ item.label }}</strong>
          <small>{{ item.desc }}</small>
        </button>
      </div>
    </section>

    <section class="tech-card overview-card overview-card--wide">
      <div class="section-title">异常优先</div>
      <div class="overview-signals">
        <article
          v-for="item in props.model.signalCards"
          :key="item.label"
          class="overview-signal"
        >
          <strong :class="toneClass(item.tone)">{{ item.label }}</strong>
          <p>{{ item.detail }}</p>
        </article>
      </div>
    </section>
  </div>
</template>

<style scoped>
.overview-layout,
.overview-quick-strip,
.overview-routes,
.overview-signals {
  display: grid;
  gap: 16px;
}

.overview-layout {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.overview-card {
  display: grid;
  gap: 16px;
  padding: 22px 24px;
}

.overview-card--wide {
  grid-column: 1 / -1;
}

.overview-copy,
.overview-note,
.overview-quick-item span,
.overview-quick-item small,
.overview-signal p {
  font-size: 0.9rem;
  line-height: 1.8;
  color: var(--console-text-secondary, var(--text-secondary));
}

.overview-note {
  color: var(--console-text-muted, var(--text-muted));
}

.overview-quick-strip,
.overview-routes {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.overview-quick-item,
.overview-route,
.overview-signal {
  display: grid;
  gap: 8px;
  padding: 16px;
  border-radius: 18px;
  border: 1px solid var(--console-border, rgba(255, 255, 255, 0.08));
  background: var(--console-surface, rgba(255, 255, 255, 0.04));
  text-align: left;
}

.overview-route strong,
.overview-quick-item strong,
.overview-signal strong {
  font-size: 0.98rem;
  color: var(--console-text, var(--text-primary));
}

.overview-quick-item span,
.overview-quick-item small,
.overview-route small {
  font-size: 0.78rem;
  line-height: 1.6;
  color: var(--console-text-muted, var(--text-muted));
}

.dashboard-tone--ok {
  color: #dbe0ff;
}

.dashboard-tone--warning {
  color: #f7d79d;
}

.dashboard-tone--critical {
  color: #ffd2de;
}

@media (max-width: 980px) {
  .overview-layout,
  .overview-quick-strip,
  .overview-routes {
    grid-template-columns: 1fr;
  }
}
</style>

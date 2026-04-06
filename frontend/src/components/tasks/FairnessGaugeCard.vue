<script setup>
/**
 * FairnessGaugeCard - 公平治理仪表盘卡片
 * 从 TaskManager.vue 提取，展示公平指数仪表盘、用户资源分布
 */
import { computed } from 'vue'

const props = defineProps({
  overview: { type: Object, default: () => ({}) },
  users: { type: Array, default: () => [] },
})

const fairnessIndex = computed(() => props.overview.fairness_index ?? 100)
const gaugeColor = computed(() => {
  const idx = fairnessIndex.value
  if (idx >= 70) return '#2E8B57'
  if (idx >= 40) return '#B8860B'
  return '#C41E3A'
})
const gaugeBg = computed(() => {
  const idx = fairnessIndex.value
  if (idx >= 70) return 'rgba(46,139,87,0.08)'
  if (idx >= 40) return 'rgba(184,134,11,0.08)'
  return 'rgba(196,30,58,0.08)'
})
const levelLabel = computed(() => {
  const level = props.overview.level || 'balanced'
  return { balanced: '均衡', moderate: '轻度倾斜', skewed: '显著倾斜', critical: '严重不均' }[level] || level
})

function barColor(pct) {
  if (pct > 60) return '#C41E3A'
  if (pct > 35) return '#B8860B'
  return '#3A5F4B'
}
</script>

<template>
  <div class="tech-card fairness-gauge-card">
    <div class="fairness-gauge-card__head">
      <div>
        <div class="fairness-gauge-card__eyebrow">多用户资源公平度量化</div>
        <div class="panel-card__title">公平治理仪表盘</div>
      </div>
      <div class="fairness-gauge-card__seal">衡</div>
    </div>
    <div class="fairness-gauge">
      <div class="fairness-gauge__ring">
        <svg viewBox="0 0 120 120" class="fairness-gauge__svg">
          <circle cx="60" cy="60" r="52" fill="none" stroke="rgba(0,0,0,0.04)" stroke-width="8" />
          <circle cx="60" cy="60" r="52" fill="none"
            :stroke="gaugeColor"
            stroke-width="8"
            stroke-linecap="round"
            :stroke-dasharray="`${fairnessIndex * 3.267} 326.7`"
            stroke-dashoffset="0"
            transform="rotate(-90 60 60)"
            style="transition: stroke-dasharray 1.2s ease"
          />
        </svg>
        <div class="fairness-gauge__value">
          <span class="fairness-gauge__number stat-value" :style="{ color: gaugeColor }">{{ fairnessIndex }}</span>
          <span class="fairness-gauge__label">公平指数</span>
        </div>
      </div>
      <div class="fairness-gauge__info">
        <div class="fairness-gauge__level" :style="{ color: gaugeColor, background: gaugeBg }">
          {{ levelLabel }}
        </div>
        <div class="fairness-gauge__summary">{{ overview.summary || '当前共享状态稳定。' }}</div>
      </div>
    </div>
    <div v-if="users.length" class="fairness-users-dist">
      <div class="fairness-users-dist__title">用户资源占比</div>
      <div class="fairness-bar-list">
        <div v-for="user in users.slice(0, 6)" :key="user.username" class="fairness-bar-item">
          <div class="fairness-bar-item__head">
            <span class="fairness-bar-item__name">{{ user.username }}</span>
            <span class="fairness-bar-item__pct">{{ user.memory_share_pct || 0 }}%</span>
          </div>
          <div class="fairness-bar-item__track">
            <div class="fairness-bar-item__fill" :style="{ width: Math.min(user.memory_share_pct || 0, 100) + '%', background: barColor(user.memory_share_pct || 0) }"></div>
          </div>
          <div class="fairness-bar-item__meta">{{ user.task_count }}任务 · {{ user.gpu_count }}卡</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.fairness-gauge-card { padding: 20px 22px; }
.fairness-gauge-card__head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 18px; }
.fairness-gauge-card__eyebrow { font-size: 0.6875rem; color: var(--text-muted); letter-spacing: 0.12em; margin-bottom: 4px; }
.fairness-gauge-card__seal { width: 36px; height: 36px; border: 2.5px solid var(--ink-vermillion, #C41E3A); border-radius: 4px; display: flex; align-items: center; justify-content: center; font-family: var(--font-seal); font-size: 0.85rem; color: var(--ink-vermillion, #C41E3A); transform: rotate(-5deg); opacity: 0.6; }
.fairness-gauge { display: flex; align-items: center; gap: 24px; margin-bottom: 20px; }
.fairness-gauge__ring { position: relative; width: 120px; height: 120px; flex-shrink: 0; }
.fairness-gauge__svg { width: 100%; height: 100%; }
.fairness-gauge__value { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; }
.fairness-gauge__number { font-size: 2rem; line-height: 1; }
.fairness-gauge__label { font-size: 0.625rem; color: var(--text-muted); margin-top: 4px; letter-spacing: 0.1em; }
.fairness-gauge__info { flex: 1; }
.fairness-gauge__level { display: inline-block; padding: 3px 12px; border-radius: 999px; font-size: 0.75rem; font-weight: 700; margin-bottom: 8px; }
.fairness-gauge__summary { font-size: 0.84rem; color: var(--text-secondary); line-height: 1.7; }
.fairness-users-dist { padding-top: 16px; border-top: 1px solid var(--border-color); }
.fairness-users-dist__title { font-size: 0.78rem; font-weight: 700; color: var(--text-primary); margin-bottom: 12px; }
.fairness-bar-list { display: flex; flex-direction: column; gap: 10px; }
.fairness-bar-item__head { display: flex; justify-content: space-between; margin-bottom: 4px; }
.fairness-bar-item__name { font-size: 0.75rem; color: var(--text-primary); font-weight: 600; }
.fairness-bar-item__pct { font-size: 0.75rem; color: var(--text-secondary); font-variant-numeric: tabular-nums; }
.fairness-bar-item__track { height: 6px; border-radius: 3px; background: rgba(0,0,0,0.04); overflow: hidden; }
.fairness-bar-item__fill { height: 100%; border-radius: 3px; transition: width 1s ease; }
.fairness-bar-item__meta { margin-top: 2px; font-size: 0.625rem; color: var(--text-muted); }
</style>

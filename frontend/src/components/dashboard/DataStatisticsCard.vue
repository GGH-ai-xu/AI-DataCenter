<script setup>
/**
 * DataStatisticsCard - 数据采集规模统计卡片
 * 展示平台历史数据总量、采集时长、吞吐量与分表明细
 */
import { onMounted, ref, computed } from 'vue'
import { getDataStatistics } from '../../services/api'

const stats = ref(null)
const loading = ref(false)
const error = ref(null)

const totalRecords = computed(() => stats.value?.total_records ?? 0)
const formattedTotal = computed(() => totalRecords.value.toLocaleString('zh-CN'))
const durationHours = computed(() => stats.value?.collection_duration_hours ?? 0)
const durationDisplay = computed(() => {
  const h = durationHours.value
  if (h <= 0) return '暂无数据'
  const days = Math.floor(h / 24)
  const hours = Math.round(h % 24)
  if (days > 0) return `${days} 天 ${hours} 小时`
  return `${hours} 小时`
})
const avgPerHour = computed(() => {
  const v = stats.value?.avg_records_per_hour ?? 0
  return v < 10 ? v.toFixed(1) : Math.round(v).toLocaleString('zh-CN')
})

const tableDetails = computed(() => {
  const tables = stats.value?.tables || {}
  return Object.entries(tables).map(([key, info]) => ({
    key,
    label: info.label,
    count: (info.count ?? 0).toLocaleString('zh-CN'),
    raw: info.count ?? 0,
  })).sort((a, b) => b.raw - a.raw)
})

async function load() {
  loading.value = true
  error.value = null
  try {
    const res = await getDataStatistics()
    stats.value = res.data
  } catch (e) {
    error.value = e?.message || '获取数据统计失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="tech-card data-stats-card">
    <div class="data-stats-card__head">
      <div>
        <div class="data-stats-card__eyebrow">大数据采集规模</div>
        <div class="data-stats-card__title">平台数据统计</div>
      </div>
      <button class="btn-tech" :disabled="loading" @click="load">
        {{ loading ? '刷新中...' : '刷新' }}
      </button>
    </div>

    <div v-if="error" class="data-stats-card__error">{{ error }}</div>

    <div v-else class="data-stats-card__body">
      <div class="data-stats-card__hero">
        <div class="data-stats-card__hero-copy">
          <div class="data-stats-card__total">
            <span class="data-stats-card__number stat-value">{{ formattedTotal }}</span>
            <span class="data-stats-card__unit">条记录</span>
          </div>
          <p class="data-stats-card__hero-desc">
            采集层已经累计沉淀监控、过程和训练运行数据，可直接作为复盘与预测分析的历史底座。
          </p>
        </div>
        <div class="data-stats-card__meta-grid">
          <div class="data-stats-card__meta-item">
            <span class="data-stats-card__meta-label">采集时长</span>
            <span class="data-stats-card__meta-value">{{ durationDisplay }}</span>
          </div>
          <div class="data-stats-card__meta-item">
            <span class="data-stats-card__meta-label">平均吞吐</span>
            <span class="data-stats-card__meta-value">{{ avgPerHour }} 条/小时</span>
          </div>
        </div>
      </div>

      <div v-if="tableDetails.length" class="data-stats-card__breakdown">
        <div class="data-stats-card__breakdown-title">分类明细</div>
        <div class="data-stats-card__table-list">
          <div v-for="t in tableDetails" :key="t.key" class="data-stats-card__table-row">
            <span class="data-stats-card__table-label">{{ t.label }}</span>
            <span class="data-stats-card__table-count">{{ t.count }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.data-stats-card {
  position: relative;
  overflow: hidden;
  padding: 22px 24px;
}

.data-stats-card::before {
  content: '';
  position: absolute;
  inset: auto -60px -100px auto;
  width: 220px;
  height: 220px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(127, 142, 255, 0.22) 0%, rgba(127, 142, 255, 0) 72%);
  pointer-events: none;
}

.data-stats-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 18px;
}

.data-stats-card__eyebrow {
  font-family: var(--font-seal);
  font-size: 0.68rem;
  color: var(--text-muted);
  letter-spacing: 0.2em;
  text-transform: uppercase;
  margin-bottom: 6px;
}

.data-stats-card__title {
  font-size: 1.18rem;
  font-weight: 600;
  color: var(--text-primary);
}

.data-stats-card__error {
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(255, 107, 129, 0.12);
  border: 1px solid rgba(255, 107, 129, 0.2);
  color: var(--accent-danger);
  font-size: 0.8rem;
}

.data-stats-card__body {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.data-stats-card__hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 220px;
  gap: 18px;
  align-items: stretch;
}

.data-stats-card__hero-copy,
.data-stats-card__meta-grid {
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: linear-gradient(180deg, rgba(127, 142, 255, 0.12), rgba(255, 255, 255, 0.045) 68%, rgba(255, 255, 255, 0.03));
}

.data-stats-card__hero-copy {
  display: grid;
  gap: 12px;
  padding: 18px;
}

.data-stats-card__total {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px;
}

.data-stats-card__number {
  font-size: clamp(2.6rem, 4vw, 3.6rem);
  line-height: 0.94;
  background: linear-gradient(180deg, #ffffff 0%, #dfe6ff 52%, #bac9ee 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.data-stats-card__unit {
  font-size: 0.86rem;
  color: var(--text-muted);
}

.data-stats-card__hero-desc {
  font-size: 0.86rem;
  line-height: 1.75;
  color: var(--text-secondary);
}

.data-stats-card__meta-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 10px;
  padding: 16px;
}

.data-stats-card__meta-item {
  display: grid;
  gap: 6px;
  padding: 12px 14px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.data-stats-card__meta-label {
  font-size: 0.68rem;
  color: var(--text-muted);
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.data-stats-card__meta-value {
  font-size: 0.96rem;
  font-weight: 700;
  color: var(--text-primary);
}

.data-stats-card__breakdown {
  padding-top: 18px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.data-stats-card__breakdown-title {
  font-family: var(--font-seal);
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: 0.18em;
  text-transform: uppercase;
  margin-bottom: 12px;
}

.data-stats-card__table-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.data-stats-card__table-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border-radius: 14px;
  background: linear-gradient(180deg, rgba(127, 142, 255, 0.1), rgba(255, 255, 255, 0.04) 68%, rgba(255, 255, 255, 0.025));
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.data-stats-card__table-label {
  font-size: 0.8rem;
  color: var(--text-secondary);
}

.data-stats-card__table-count {
  font-size: 0.84rem;
  font-weight: 700;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

@media (max-width: 880px) {
  .data-stats-card__hero {
    grid-template-columns: 1fr;
  }
}
</style>

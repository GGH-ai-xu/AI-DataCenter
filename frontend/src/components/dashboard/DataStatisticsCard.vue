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
        <div class="panel-card__title">平台数据统计</div>
      </div>
      <button class="btn-tech" :disabled="loading" @click="load">
        {{ loading ? '刷新中...' : '刷新' }}
      </button>
    </div>

    <div v-if="error" class="data-stats-card__error">{{ error }}</div>

    <div v-else class="data-stats-card__body">
      <div class="data-stats-card__hero">
        <div class="data-stats-card__total">
          <span class="data-stats-card__number stat-value">{{ formattedTotal }}</span>
          <span class="data-stats-card__unit">条记录</span>
        </div>
        <div class="data-stats-card__meta-row">
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
.data-stats-card { padding: 20px 22px; }
.data-stats-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}
.data-stats-card__eyebrow {
  font-size: 0.6875rem;
  color: var(--text-muted);
  letter-spacing: 0.12em;
  margin-bottom: 4px;
}
.data-stats-card__error {
  padding: 12px;
  border-radius: 10px;
  background: rgba(196,30,58,0.06);
  color: #C41E3A;
  font-size: 0.8rem;
}
.data-stats-card__body { display: flex; flex-direction: column; gap: 18px; }
.data-stats-card__hero { text-align: center; padding: 12px 0; }
.data-stats-card__total { margin-bottom: 12px; }
.data-stats-card__number { font-size: 2.4rem; line-height: 1; color: var(--ink-primary, #2C4A3B); }
.data-stats-card__unit { font-size: 0.85rem; color: var(--text-muted); margin-left: 6px; }
.data-stats-card__meta-row {
  display: flex;
  justify-content: center;
  gap: 28px;
}
.data-stats-card__meta-item { display: flex; flex-direction: column; align-items: center; gap: 2px; }
.data-stats-card__meta-label { font-size: 0.6875rem; color: var(--text-muted); }
.data-stats-card__meta-value { font-size: 0.92rem; font-weight: 700; color: var(--text-primary); }
.data-stats-card__breakdown {
  padding-top: 14px;
  border-top: 1px solid var(--border-color);
}
.data-stats-card__breakdown-title {
  font-size: 0.78rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 10px;
}
.data-stats-card__table-list { display: flex; flex-direction: column; gap: 6px; }
.data-stats-card__table-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 10px;
  border-radius: 8px;
  background: rgba(58,95,75,0.04);
  border: 1px solid rgba(58,95,75,0.06);
}
.data-stats-card__table-label { font-size: 0.78rem; color: var(--text-secondary); }
.data-stats-card__table-count {
  font-size: 0.82rem;
  font-weight: 700;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}
</style>

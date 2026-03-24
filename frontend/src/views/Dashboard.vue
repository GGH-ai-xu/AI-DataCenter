<script setup>
/**
 * Dashboard.vue - 主监控大屏
 * 展示4张GPU实时状态、总功耗、温度、利用率等核心指标
 */
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '../stores/app'
import PowerTrendChart from '../components/charts/PowerTrendChart.vue'
import UtilizationChart from '../components/charts/UtilizationChart.vue'

const router = useRouter()
const store = useAppStore()

// 格式化显存（字节→GB）
const fmtMem = (bytes) => (bytes / 1073741824).toFixed(1)

// GPU温度对应颜色
const tempColor = (t) => t >= 90 ? '#f87171' : t >= 80 ? '#fbbf24' : t >= 60 ? '#38bdf8' : '#34d399'

// GPU利用率对应颜色
const utilColor = (u) => u >= 90 ? '#f87171' : u >= 70 ? '#fbbf24' : u >= 40 ? '#38bdf8' : '#34d399'

// 功耗百分比
const powerPct = (usage, limit) => limit > 0 ? Math.round(usage / limit * 100) : 0

// 显存百分比
const memPct = (used, total) => total > 0 ? Math.round(used / total * 100) : 0

// 集群总功耗限制
const totalPowerLimit = computed(() =>
  store.gpus.reduce((sum, g) => sum + (g.power_limit || 350), 0)
)

// 时间段标签
const timePeriodInfo = computed(() => {
  const h = new Date().getHours()
  if (h >= 9 && h < 12 || h >= 14 && h < 18) return { label: '用电高峰', color: '#f87171', bg: 'rgba(248,113,113,0.12)' }
  if (h >= 22 || h < 6) return { label: '用电低谷', color: '#34d399', bg: 'rgba(52,211,153,0.12)' }
  return { label: '平峰时段', color: '#38bdf8', bg: 'rgba(56,189,248,0.12)' }
})
</script>

<template>
  <div class="dashboard">
    <!-- 顶部统计条 -->
    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-card__icon" style="background: linear-gradient(135deg, #0ea5e9, #6366f1)">⚡</div>
        <div class="stat-card__content">
          <div class="stat-card__label">集群总功耗</div>
          <div class="stat-card__value stat-value">
            <span class="text-3xl">{{ store.totalPower.toFixed(0) }}</span>
            <span class="stat-card__unit">W</span>
          </div>
          <div class="stat-card__sub">
            <div class="progress-bar" style="width: 100%">
              <div class="progress-bar__fill" :style="{ width: (store.totalPower / totalPowerLimit * 100) + '%', background: 'var(--gradient-blue)' }"></div>
            </div>
            <span class="text-xs mt-1" style="color: var(--text-muted)">/ {{ totalPowerLimit.toFixed(0) }}W</span>
          </div>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-card__icon" style="background: linear-gradient(135deg, #f59e0b, #fbbf24)">🌡</div>
        <div class="stat-card__content">
          <div class="stat-card__label">平均温度</div>
          <div class="stat-card__value stat-value">
            <span class="text-3xl" :style="{ color: tempColor(store.avgTemperature) }">{{ store.avgTemperature }}</span>
            <span class="stat-card__unit">°C</span>
          </div>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-card__icon" style="background: linear-gradient(135deg, #10b981, #34d399)">◈</div>
        <div class="stat-card__content">
          <div class="stat-card__label">平均利用率</div>
          <div class="stat-card__value stat-value">
            <span class="text-3xl" :style="{ color: utilColor(store.avgUtilization) }">{{ store.avgUtilization }}</span>
            <span class="stat-card__unit">%</span>
          </div>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-card__icon" style="background: linear-gradient(135deg, #8b5cf6, #a78bfa)">⬡</div>
        <div class="stat-card__content">
          <div class="stat-card__label">显存占用</div>
          <div class="stat-card__value stat-value">
            <span class="text-3xl">{{ fmtMem(store.totalMemoryUsed) }}</span>
            <span class="stat-card__unit">/ {{ fmtMem(store.totalMemoryTotal) }} GB</span>
          </div>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-card__icon" :style="{ background: timePeriodInfo.bg, color: timePeriodInfo.color, boxShadow: 'none' }">⏱</div>
        <div class="stat-card__content">
          <div class="stat-card__label">当前时段</div>
          <div class="stat-card__value">
            <span class="status-badge" :style="{ background: timePeriodInfo.bg, color: timePeriodInfo.color, border: '1px solid ' + timePeriodInfo.color + '33', fontSize: '0.875rem' }">
              {{ timePeriodInfo.label }}
            </span>
          </div>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-card__icon" style="background: linear-gradient(135deg, #06b6d4, #22d3ee)">☵</div>
        <div class="stat-card__content">
          <div class="stat-card__label">GPU数量</div>
          <div class="stat-card__value stat-value">
            <span class="text-3xl">{{ store.gpus.length }}</span>
            <span class="stat-card__unit">卡</span>
          </div>
        </div>
      </div>
    </div>

    <!-- GPU 卡片网格 -->
    <div class="section-title" style="margin: 20px 0 12px">GPU 实时状态</div>
    <div class="gpu-grid">
      <div
        v-for="gpu in store.gpus"
        :key="gpu.index"
        class="gpu-card tech-card"
        @click="router.push(`/gpu/${gpu.index}`)"
      >
        <!-- 卡片头 -->
        <div class="gpu-card__header">
          <div class="gpu-card__id">
            <span class="gpu-card__badge">GPU {{ gpu.index }}</span>
            <span class="gpu-card__name">{{ gpu.name }}</span>
          </div>
          <span
            class="status-badge"
            :class="gpu.temperature >= 85 ? 'status-badge--critical' : gpu.temperature >= 70 ? 'status-badge--warning' : 'status-badge--ok'"
          >
            {{ gpu.temperature >= 85 ? '高温' : gpu.temperature >= 70 ? '偏高' : '正常' }}
          </span>
        </div>

        <!-- 核心指标网格 -->
        <div class="gpu-card__metrics">
          <div class="metric-item">
            <div class="metric-item__label">温度</div>
            <div class="metric-item__value stat-value" :style="{ color: tempColor(gpu.temperature) }">
              {{ gpu.temperature }}<span class="metric-item__unit">°C</span>
            </div>
            <div class="metric-bar">
              <div class="metric-bar__fill" :style="{ width: Math.min(gpu.temperature / 100 * 100, 100) + '%', background: tempColor(gpu.temperature) }"></div>
            </div>
          </div>

          <div class="metric-item">
            <div class="metric-item__label">功耗</div>
            <div class="metric-item__value stat-value">
              {{ gpu.power_usage.toFixed(0) }}<span class="metric-item__unit">/ {{ gpu.power_limit.toFixed(0) }}W</span>
            </div>
            <div class="metric-bar">
              <div class="metric-bar__fill" :style="{ width: powerPct(gpu.power_usage, gpu.power_limit) + '%', background: 'var(--gradient-blue)' }"></div>
            </div>
          </div>

          <div class="metric-item">
            <div class="metric-item__label">GPU利用率</div>
            <div class="metric-item__value stat-value" :style="{ color: utilColor(gpu.gpu_utilization) }">
              {{ gpu.gpu_utilization }}<span class="metric-item__unit">%</span>
            </div>
            <div class="metric-bar">
              <div class="metric-bar__fill" :style="{ width: gpu.gpu_utilization + '%', background: utilColor(gpu.gpu_utilization) }"></div>
            </div>
          </div>

          <div class="metric-item">
            <div class="metric-item__label">显存</div>
            <div class="metric-item__value stat-value">
              {{ fmtMem(gpu.memory_used) }}<span class="metric-item__unit">/ {{ fmtMem(gpu.memory_total) }}G</span>
            </div>
            <div class="metric-bar">
              <div class="metric-bar__fill" :style="{ width: memPct(gpu.memory_used, gpu.memory_total) + '%', background: 'var(--gradient-green)' }"></div>
            </div>
          </div>
        </div>

        <!-- 底部副指标 -->
        <div class="gpu-card__footer">
          <span>风扇 {{ gpu.fan_speed }}%</span>
          <span>SM {{ gpu.clock_sm }} MHz</span>
          <span>MEM {{ gpu.clock_mem }} MHz</span>
        </div>
      </div>

      <!-- 无数据占位 -->
      <div v-if="!store.gpus.length" class="gpu-grid__empty tech-card">
        <div class="text-center" style="padding: 60px 20px; color: var(--text-muted)">
          <div style="font-size: 2.5rem; margin-bottom: 12px; opacity: 0.3">◉</div>
          <div style="font-size: 1rem; margin-bottom: 8px">等待GPU数据...</div>
          <div style="font-size: 0.8rem">请确保Agent服务已启动并建立SSH隧道连接</div>
        </div>
      </div>
    </div>

    <!-- 图表区域 -->
    <div class="charts-row" v-if="store.gpus.length">
      <div class="chart-panel tech-card">
        <div class="chart-panel__header">
          <div class="section-title">功耗趋势</div>
        </div>
        <div class="chart-panel__body">
          <PowerTrendChart :gpus="store.gpus" />
        </div>
      </div>
      <div class="chart-panel tech-card">
        <div class="chart-panel__header">
          <div class="section-title">利用率分布</div>
        </div>
        <div class="chart-panel__body">
          <UtilizationChart :gpus="store.gpus" />
        </div>
      </div>
    </div>

    <!-- 最近告警 -->
    <div class="alerts-strip" v-if="store.alerts.length">
      <div class="section-title" style="margin-bottom: 8px">最近告警</div>
      <div class="alerts-list">
        <div
          v-for="(alert, i) in store.alerts.slice(0, 5)"
          :key="i"
          class="alert-item"
          :class="alert.severity === 'critical' ? 'alert-item--critical' : 'alert-item--warning'"
        >
          <span class="alert-item__icon">{{ alert.severity === 'critical' ? '⚠' : '△' }}</span>
          <span class="alert-item__text">{{ alert.message }}</span>
          <span class="alert-item__time">{{ new Date(alert.timestamp * 1000).toLocaleTimeString('zh-CN') }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dashboard {
  max-width: 1600px;
  margin: 0 auto;
}

/* 顶部统计条 */
.stats-row {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
  margin-bottom: 8px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: var(--gradient-card);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  transition: all 0.25s;
}

.stat-card:hover {
  border-color: var(--border-glow);
  box-shadow: var(--shadow-glow-blue);
}

.stat-card__icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.1rem;
  flex-shrink: 0;
  box-shadow: 0 4px 12px rgba(0,0,0,0.2);
}

.stat-card__label {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-bottom: 2px;
}

.stat-card__value {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.stat-card__unit {
  font-size: 0.8rem;
  color: var(--text-muted);
  font-weight: 400;
}

.stat-card__sub {
  margin-top: 4px;
}

/* GPU卡片网格 */
.gpu-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}

.gpu-grid__empty {
  grid-column: 1 / -1;
}

.gpu-card {
  padding: 18px;
  cursor: pointer;
}

.gpu-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.gpu-card__id {
  display: flex;
  align-items: center;
  gap: 8px;
}

.gpu-card__badge {
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--accent-primary);
  background: rgba(56, 189, 248, 0.1);
  padding: 2px 8px;
  border-radius: 6px;
  font-family: 'JetBrains Mono', monospace;
}

.gpu-card__name {
  font-size: 0.75rem;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 120px;
}

.gpu-card__metrics {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.metric-item__label {
  font-size: 0.6875rem;
  color: var(--text-muted);
  margin-bottom: 2px;
}

.metric-item__value {
  font-size: 1.25rem;
  margin-bottom: 6px;
}

.metric-item__unit {
  font-size: 0.6875rem;
  color: var(--text-muted);
  font-weight: 400;
  margin-left: 2px;
}

.metric-bar {
  height: 4px;
  border-radius: 2px;
  background: rgba(255, 255, 255, 0.06);
  overflow: hidden;
}

.metric-bar__fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.8s cubic-bezier(0.25, 0.46, 0.45, 0.94);
}

.gpu-card__footer {
  display: flex;
  justify-content: space-between;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.04);
  font-size: 0.6875rem;
  color: var(--text-muted);
}

/* 图表区 */
.charts-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  margin-top: 16px;
}

.chart-panel {
  padding: 18px;
}

.chart-panel__header {
  margin-bottom: 12px;
}

.chart-panel__body {
  height: 240px;
}

/* 告警条 */
.alerts-strip {
  margin-top: 16px;
}

.alerts-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.alert-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 0.8125rem;
}

.alert-item--warning {
  background: rgba(251, 191, 36, 0.06);
  border: 1px solid rgba(251, 191, 36, 0.15);
  color: #fbbf24;
}

.alert-item--critical {
  background: rgba(248, 113, 113, 0.06);
  border: 1px solid rgba(248, 113, 113, 0.15);
  color: #f87171;
}

.alert-item__icon {
  font-size: 1rem;
}

.alert-item__text {
  flex: 1;
}

.alert-item__time {
  font-size: 0.75rem;
  color: var(--text-muted);
  font-family: monospace;
}

@media (max-width: 1400px) {
  .stats-row { grid-template-columns: repeat(3, 1fr); }
  .gpu-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>

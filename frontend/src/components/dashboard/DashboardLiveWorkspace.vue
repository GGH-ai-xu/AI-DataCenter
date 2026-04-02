<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import PowerTrendChart from '../charts/PowerTrendChart.vue'
import UtilizationChart from '../charts/UtilizationChart.vue'

const props = defineProps({
  store: { type: Object, required: true },
  summary: { type: Object, required: true },
  governance: { type: Object, required: true },
})

const router = useRouter()

const pulseCards = computed(() => [
  { label: '当前总功率', value: `${Number(props.store.totalPower || 0).toFixed(1)}W`, hint: `${props.store.gpus.length} 张 GPU`, tone: 'mountain' },
  { label: '剩余预算', value: `${Math.abs(Number(props.governance.budget?.remaining_power || 0)).toFixed(1)}W`, hint: props.governance.budget?.is_exceeded ? '预算已超限' : `预算上限 ${props.governance.budget?.total_power_budget || 0}W`, tone: props.governance.budget?.is_exceeded ? 'danger' : 'ok' },
  { label: '平均温度', value: `${props.store.avgTemperature}°C`, hint: `${props.summary.hotGpuCount || 0} 张高温 GPU`, tone: props.store.avgTemperature >= 80 ? 'danger' : 'amber' },
  { label: '活跃用户', value: `${props.summary.activeUsers || 0}`, hint: `${props.store.processes.length} 个 GPU 进程`, tone: 'ink' },
  { label: '紧急任务', value: `${props.summary.urgentTasks || 0}`, hint: `可延迟 ${props.summary.deferrableTasks || 0} / 普通 ${props.summary.normalTasks || 0}`, tone: 'vermillion' },
  { label: '严重告警', value: `${props.summary.criticalAlertCount || 0}`, hint: `${props.governance.yieldQueue?.length || 0} 个候选让路`, tone: 'purple' },
])

function fmtMem(bytes) {
  return (Number(bytes || 0) / 1073741824).toFixed(1)
}

function powerPct(usage, limit) {
  return limit > 0 ? Math.round((usage / limit) * 100) : 0
}

function memPct(used, total) {
  return total > 0 ? Math.round((used / total) * 100) : 0
}

function tempColor(temperature) {
  if (temperature >= 90) return '#C41E3A'
  if (temperature >= 80) return '#B8860B'
  if (temperature >= 60) return '#3A5F4B'
  return '#2E8B57'
}

function utilColor(utilization) {
  if (utilization >= 90) return '#C41E3A'
  if (utilization >= 70) return '#B8860B'
  if (utilization >= 40) return '#3A5F4B'
  return '#2E8B57'
}
</script>

<template>
  <div class="live-workspace">
    <section class="live-workspace__hero tech-card">
      <div class="live-workspace__intro">
        <span
          class="status-badge"
          :style="{ background: props.governance.boardTone.bg, color: props.governance.boardTone.color, border: '1px solid ' + props.governance.boardTone.border }"
        >
          {{ props.governance.boardTone.badge }}
        </span>
        <h2 class="live-workspace__title">{{ props.governance.boardTone.title }}</h2>
        <p class="live-workspace__desc">{{ props.governance.governanceTip }}</p>
        <div class="live-workspace__chip-row">
          <span class="governance-chip">公平指数 {{ props.governance.fairnessOverview?.fairness_index ?? 0 }}</span>
          <span class="governance-chip">规则违规 {{ props.governance.fairnessOverview?.violation_user_count || 0 }}</span>
          <span class="governance-chip">最高占用 {{ props.governance.fairnessOverview?.highest_share_pct || 0 }}%</span>
        </div>
      </div>

      <div class="live-workspace__pulse">
        <div
          v-for="card in pulseCards"
          :key="card.label"
          class="live-workspace__pulse-card"
          :class="`live-workspace__pulse-card--${card.tone}`"
        >
          <span class="live-workspace__pulse-label">{{ card.label }}</span>
          <strong class="live-workspace__pulse-value stat-value">{{ card.value }}</strong>
          <span class="live-workspace__pulse-hint">{{ card.hint }}</span>
        </div>
      </div>
    </section>

    <div class="live-workspace__body">
      <aside class="live-workspace__rail">
        <section class="tech-card live-workspace__panel">
          <div class="section-title">预算治理</div>
          <div class="live-workspace__panel-value">
            <span class="stat-value">{{ props.governance.budget?.usage_pct || 0 }}%</span>
            <span>预算占用</span>
          </div>
          <div class="live-workspace__bar">
            <div
              class="live-workspace__bar-fill"
              :style="{ width: Math.min(100, Math.max(0, props.governance.budget?.usage_pct || 0)) + '%', background: props.governance.budget?.is_exceeded ? 'var(--gradient-red)' : 'var(--gradient-green)' }"
            ></div>
          </div>
          <div class="live-workspace__panel-text">
            {{ props.governance.budget?.enabled ? '预算治理已启用' : '预算治理当前关闭' }}，已接管 {{ props.governance.budget?.managed_gpu_count || 0 }} 张 GPU。
          </div>
        </section>

        <section class="tech-card live-workspace__panel">
          <div class="section-title">治理建议</div>
          <div class="live-workspace__recommendations">
            <div
              v-for="(item, index) in props.governance.recommendationList"
              :key="index"
              class="live-workspace__recommendation"
            >
              {{ item }}
            </div>
          </div>
        </section>

        <section class="tech-card live-workspace__panel">
          <div class="section-title">公平与来源</div>
          <div class="live-workspace__panel-text">{{ props.governance.sourceState?.detail }}</div>
          <div class="live-workspace__chip-row">
            <span class="governance-chip" :style="{ color: props.governance.fairnessTone.color, background: props.governance.fairnessTone.bg }">
              {{ props.governance.fairnessTone.label }}
            </span>
            <span class="governance-chip">候选让路 {{ props.governance.yieldQueue?.length || 0 }}</span>
          </div>
          <button class="btn-tech" @click="router.push('/scheduler')">进入治理调度页</button>
        </section>
      </aside>

      <div class="live-workspace__main">
        <section class="tech-card live-workspace__gpu-surface">
          <div class="live-workspace__surface-head">
            <div>
              <div class="section-title">GPU 实时矩阵</div>
              <div class="live-workspace__surface-note">把算力卡片集中在同一层，避免治理卡与硬件卡交叉平铺。</div>
            </div>
            <div v-if="props.store.gpus.length" class="live-workspace__chip-row">
              <span class="governance-chip">{{ props.store.dataSourceLabel.text }}</span>
              <span class="governance-chip">{{ props.store.dataSourceStatus.gpu_count || props.store.gpus.length }} 卡</span>
            </div>
          </div>

          <div v-if="props.store.gpus.length" class="live-workspace__gpu-grid">
            <button
              v-for="gpu in props.store.gpus"
              :key="gpu.index"
              type="button"
              class="live-workspace__gpu-card"
              @click="router.push(`/gpu/${gpu.index}`)"
            >
              <div class="live-workspace__gpu-top">
                <div>
                  <span class="gpu-card__badge">GPU {{ gpu.index }}</span>
                  <div class="live-workspace__gpu-name">{{ gpu.name }}</div>
                </div>
                <span class="status-badge" :class="gpu.temperature >= 85 ? 'status-badge--critical' : gpu.temperature >= 70 ? 'status-badge--warning' : 'status-badge--ok'">
                  {{ gpu.temperature >= 85 ? '高温' : gpu.temperature >= 70 ? '偏高' : '正常' }}
                </span>
              </div>

              <div class="live-workspace__metric-grid">
                <div class="live-workspace__metric">
                  <span>温度</span>
                  <strong class="stat-value" :style="{ color: tempColor(gpu.temperature) }">{{ gpu.temperature }}°C</strong>
                  <div class="live-workspace__bar"><div class="live-workspace__bar-fill" :style="{ width: Math.min(gpu.temperature, 100) + '%', background: tempColor(gpu.temperature) }"></div></div>
                </div>
                <div class="live-workspace__metric">
                  <span>功耗</span>
                  <strong class="stat-value">{{ gpu.power_usage.toFixed(0) }}/{{ gpu.power_limit.toFixed(0) }}W</strong>
                  <div class="live-workspace__bar"><div class="live-workspace__bar-fill" :style="{ width: powerPct(gpu.power_usage, gpu.power_limit) + '%', background: 'var(--gradient-blue)' }"></div></div>
                </div>
                <div class="live-workspace__metric">
                  <span>利用率</span>
                  <strong class="stat-value" :style="{ color: utilColor(gpu.gpu_utilization) }">{{ gpu.gpu_utilization }}%</strong>
                  <div class="live-workspace__bar"><div class="live-workspace__bar-fill" :style="{ width: gpu.gpu_utilization + '%', background: utilColor(gpu.gpu_utilization) }"></div></div>
                </div>
                <div class="live-workspace__metric">
                  <span>显存</span>
                  <strong class="stat-value">{{ fmtMem(gpu.memory_used) }}/{{ fmtMem(gpu.memory_total) }}G</strong>
                  <div class="live-workspace__bar"><div class="live-workspace__bar-fill" :style="{ width: memPct(gpu.memory_used, gpu.memory_total) + '%', background: 'var(--gradient-green)' }"></div></div>
                </div>
              </div>
            </button>
          </div>

          <div v-else class="live-workspace__empty">
            请确保 Agent 服务已启动，并确认当前数据源是否为真实采集。
          </div>
        </section>

        <div v-if="props.store.gpus.length" class="live-workspace__charts">
          <section class="chart-panel tech-card">
            <div class="chart-panel__header"><div class="section-title">功耗趋势</div></div>
            <div class="chart-panel__body"><PowerTrendChart :gpus="props.store.gpus" /></div>
          </section>
          <section class="chart-panel tech-card">
            <div class="chart-panel__header"><div class="section-title">利用率分布</div></div>
            <div class="chart-panel__body"><UtilizationChart :gpus="props.store.gpus" /></div>
          </section>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.live-workspace,
.live-workspace__main,
.live-workspace__rail,
.live-workspace__pulse,
.live-workspace__gpu-grid,
.live-workspace__charts {
  display: grid;
  gap: 14px;
}

.live-workspace__hero,
.live-workspace__body {
  display: grid;
  gap: 16px;
}

.live-workspace__hero {
  grid-template-columns: minmax(0, 1.05fr) minmax(0, 1.3fr);
  padding: 22px 24px;
}

.live-workspace__title {
  margin-top: 12px;
  font-size: 1.42rem;
  line-height: 1.45;
}

.live-workspace__desc,
.live-workspace__panel-text,
.live-workspace__surface-note,
.live-workspace__recommendation,
.live-workspace__pulse-hint {
  color: var(--text-secondary);
  line-height: 1.7;
  overflow-wrap: anywhere;
}

.live-workspace__pulse {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.live-workspace__pulse-card,
.live-workspace__panel,
.live-workspace__gpu-card {
  border-radius: 22px;
  border: 1px solid rgba(26, 26, 26, 0.06);
  background: rgba(255, 252, 247, 0.82);
}

.live-workspace__pulse-card {
  padding: 14px 16px;
}

.live-workspace__pulse-card--danger {
  border-color: rgba(196, 30, 58, 0.16);
}

.live-workspace__pulse-card--ok,
.live-workspace__pulse-card--mountain {
  border-color: rgba(46, 139, 87, 0.14);
}

.live-workspace__pulse-card--amber {
  border-color: rgba(184, 134, 11, 0.16);
}

.live-workspace__pulse-card--purple {
  border-color: rgba(91, 75, 140, 0.16);
}

.live-workspace__pulse-label,
.live-workspace__metric span {
  font-size: 0.74rem;
  color: var(--text-muted);
}

.live-workspace__pulse-value,
.live-workspace__panel-value {
  display: block;
  margin: 8px 0 4px;
}

.live-workspace__panel-value {
  font-size: 1.3rem;
}

.live-workspace__body {
  grid-template-columns: 320px minmax(0, 1fr);
}

.live-workspace__panel {
  padding: 18px;
}

.live-workspace__recommendations {
  display: grid;
  gap: 10px;
  margin-top: 12px;
}

.live-workspace__recommendation {
  padding-left: 12px;
  border-left: 2px solid rgba(58, 95, 75, 0.12);
  font-size: 0.8rem;
}

.live-workspace__chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.governance-chip {
  font-size: 0.7rem;
  color: var(--accent-primary);
  background: rgba(58, 95, 75, 0.08);
  padding: 4px 8px;
  border-radius: 999px;
}

.live-workspace__gpu-surface {
  padding: 20px;
}

.live-workspace__surface-head,
.live-workspace__gpu-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.live-workspace__gpu-grid {
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  margin-top: 16px;
}

.live-workspace__gpu-card {
  display: grid;
  gap: 14px;
  padding: 18px;
  text-align: left;
}

.gpu-card__badge {
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--accent-primary);
  background: rgba(58, 95, 75, 0.1);
  padding: 2px 8px;
  border-radius: 6px;
  font-family: 'JetBrains Mono', monospace;
}

.live-workspace__gpu-name {
  margin-top: 8px;
  font-size: 0.92rem;
  color: var(--text-primary);
  line-height: 1.5;
}

.live-workspace__metric-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.live-workspace__metric {
  display: grid;
  gap: 6px;
}

.live-workspace__bar {
  height: 6px;
  border-radius: 999px;
  background: rgba(58, 95, 75, 0.08);
  overflow: hidden;
}

.live-workspace__bar-fill {
  height: 100%;
  border-radius: inherit;
}

.live-workspace__charts {
  grid-template-columns: repeat(2, minmax(0, 1fr));
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

.live-workspace__empty {
  margin-top: 16px;
  padding: 56px 18px;
  text-align: center;
  border-radius: 22px;
  border: 1px dashed rgba(58, 95, 75, 0.14);
  color: var(--text-muted);
}

@media (max-width: 1280px) {
  .live-workspace__hero,
  .live-workspace__body,
  .live-workspace__charts {
    grid-template-columns: 1fr;
  }

  .live-workspace__pulse {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 820px) {
  .live-workspace__hero,
  .live-workspace__gpu-surface {
    padding: 18px;
  }

  .live-workspace__pulse,
  .live-workspace__metric-grid {
    grid-template-columns: 1fr;
  }

  .live-workspace__surface-head,
  .live-workspace__gpu-top {
    flex-direction: column;
  }
}
</style>

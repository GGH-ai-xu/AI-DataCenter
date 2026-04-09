<script setup>
/**
 * MonitorCenter.vue - 观察中心
 * 四大功能：训练进度、用户统计、任务时间线、系统全貌
 */
import { ref, computed, watch } from 'vue'
import VChart from 'vue-echarts'
import MonitorWorkspaceSummary from '../components/monitor/MonitorWorkspaceSummary.vue'
import WorkspacePaneLayout from '../components/workspace/WorkspacePaneLayout.vue'
import WorkspaceTabs from '../components/workspace/WorkspaceTabs.vue'
import { useMonitorData } from '../composables/useMonitorData.js'
import { createPaletteProxy, readThemeVar } from '../lib/themeMode.js'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart, CustomChart, GaugeChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, TitleComponent } from 'echarts/components'

use([CanvasRenderer, LineChart, BarChart, CustomChart, GaugeChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, TitleComponent])

const activeTab = ref('system')
const loading = ref(true)
const monitorTabs = [
  { key: 'system', label: '系统全貌', desc: '底盘与资源' },
  { key: 'training', label: '训练进度', desc: '训练曲线与日志' },
  { key: 'users', label: '用户统计', desc: '占用结构与画像' },
  { key: 'timeline', label: '任务时间线', desc: '生命周期与回放' },
]

// 数据状态
const systemDetail = ref(null)
const trainingData = ref([])
const userStats = ref([])
const taskTimeline = ref([])
const timelineHours = ref(24)
const prevNetwork = ref(null)
const networkSpeed = ref({ sent: 0, recv: 0 })
const monitorRefresh = useMonitorData(activeTab, timelineHours, {
  onData: applyMonitorTabData,
})
const monitorPalette = computed(() => ({
  primary: readThemeVar('--accent-primary'),
  secondary: readThemeVar('--accent-tertiary'),
  warning: readThemeVar('--accent-warning'),
  danger: readThemeVar('--accent-danger'),
  text: readThemeVar('--text-primary'),
  textSecondary: readThemeVar('--text-secondary'),
  textMuted: readThemeVar('--text-tertiary'),
  line: readThemeVar('--border-color'),
  track: readThemeVar('--bg-surface'),
  border: readThemeVar('--border-strong'),
  panel: readThemeVar('--bg-strong'),
  inactive: readThemeVar('--text-muted'),
}))
const palette = createPaletteProxy(monitorPalette)
const monitorFontUi = "'PingFang SC','Microsoft YaHei','Noto Sans SC','Segoe UI',sans-serif"
const TIMELINE_RANGE_OPTIONS = Object.freeze([
  { hours: 1, label: '1小时' },
  { hours: 6, label: '6小时' },
  { hours: 24, label: '1天' },
  { hours: 72, label: '3天' },
])
const TIMELINE_CHART_LIMIT = 24
const TIMELINE_LEDGER_LIMIT = 28

// ===== 格式化工具 =====
const fmtBytes = (b) => {
  if (!b || b < 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0
  let v = b
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++ }
  return v.toFixed(i > 1 ? 1 : 0) + ' ' + units[i]
}
const fmtSpeed = (bps) => fmtBytes(bps) + '/s'
const fmtDuration = (seconds) => {
  if (!seconds || seconds <= 0) return '-'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (h > 24) return Math.floor(h / 24) + '天' + (h % 24) + '时'
  if (h > 0) return h + '时' + m + '分'
  return m + '分'
}
const fmtTime = (ts) => {
  if (!ts) return '-'
  return new Date(ts * 1000).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function usageColor(value, warning = 70, critical = 90, normal = palette.primary) {
  if (value >= critical) return palette.danger
  if (value >= warning) return palette.warning
  return normal
}

function timelineTaskCommand(task) {
  const command = task.command?.trim()
  return command || `PID ${task.pid}`
}

function timelineTaskName(task) {
  const command = timelineTaskCommand(task)
  const entry = command.split('/').pop() || command
  return entry.split(' ')[0] || `PID ${task.pid}`
}

function timelineTaskDuration(task) {
  const now = Date.now() / 1000
  const end = task.is_active ? now : task.last_seen
  return fmtDuration(end - task.first_seen)
}

function timelineTaskStatus(task) {
  return task.is_active ? '运行中' : '已结束'
}

// ===== 数据加载 =====
async function refreshActiveTab(force = false) {
  loading.value = true
  try {
    await monitorRefresh.refresh({ force })
  } finally {
    loading.value = false
  }
}

function applySystemDetail(data) {
  if (data.network && prevNetwork.value) {
    const dt = data.timestamp - (systemDetail.value?.timestamp || data.timestamp)
    if (dt > 0) {
      networkSpeed.value = {
        sent: (data.network.bytes_sent - prevNetwork.value.bytes_sent) / dt,
        recv: (data.network.bytes_recv - prevNetwork.value.bytes_recv) / dt,
      }
    }
  }
  if (data.network) {
    prevNetwork.value = { ...data.network }
  }
  systemDetail.value = data
}

function applyMonitorTabData(tab, payload) {
  loading.value = false
  if (tab === 'system') {
    applySystemDetail(payload)
    return
  }
  if (tab === 'training') {
    trainingData.value = payload || []
    return
  }
  if (tab === 'users') {
    userStats.value = payload || []
    return
  }
  taskTimeline.value = payload || []
}

const activeTimelineRangeLabel = computed(() =>
  TIMELINE_RANGE_OPTIONS.find(({ hours }) => hours === timelineHours.value)?.label || `${timelineHours.value}小时`
)
const timelineChartItems = computed(() => taskTimeline.value.slice(0, TIMELINE_CHART_LIMIT))
const timelineLedgerItems = computed(() => taskTimeline.value.slice(0, TIMELINE_LEDGER_LIMIT))

// ===== 图表配置 =====
const cpuCoreOption = computed(() => {
  const cores = systemDetail.value?.cpu_per_core || []
  return {
    tooltip: {
      trigger: 'axis',
      backgroundColor: palette.panel,
      borderColor: palette.border,
      textStyle: { color: palette.text, fontFamily: monitorFontUi },
    },
    grid: { top: 30, right: 16, bottom: 24, left: 40 },
    xAxis: {
      type: 'category',
      data: cores.map((_, i) => 'C' + i),
      axisLabel: { color: palette.textMuted, fontSize: 10, fontFamily: monitorFontUi },
      axisLine: { lineStyle: { color: palette.line } },
    },
    yAxis: {
      type: 'value',
      max: 100,
      axisLabel: { color: palette.textMuted, formatter: '{value}%', fontFamily: monitorFontUi },
      splitLine: { lineStyle: { color: palette.line } },
    },
    series: [{
      type: 'bar', data: cores.map(v => ({
        value: v,
        itemStyle: { color: usageColor(v, 50, 80) }
      })),
      barMaxWidth: 12, borderRadius: [3, 3, 0, 0],
    }],
  }
})

const trainingChartOption = computed(() => {
  if (!trainingData.value.length) return null
  // 选第一个有数据的训练任务
  const task = trainingData.value.find(t => t.has_metrics && t.metrics.length > 1)
  if (!task) return null

  const epochs = task.metrics.map(m => m.epoch)
  const losses = task.metrics.map(m => m.loss)
  const accs = task.metrics.map(m => m.accuracy).filter(a => a !== undefined)

  const series = [{
    name: 'Loss', type: 'line', data: losses, smooth: true,
    lineStyle: { color: palette.danger, width: 2 }, itemStyle: { color: palette.danger },
    symbol: 'none', yAxisIndex: 0,
  }]
  const yAxes = [{
    type: 'value', name: 'Loss', nameTextStyle: { color: palette.danger, fontFamily: monitorFontUi },
    axisLabel: { color: palette.textMuted, fontFamily: monitorFontUi }, splitLine: { lineStyle: { color: palette.line } },
  }]

  if (accs.length > 0) {
    series.push({
      name: 'Accuracy', type: 'line', data: task.metrics.map(m => m.accuracy),
      smooth: true, lineStyle: { color: palette.primary, width: 2 }, itemStyle: { color: palette.primary },
      symbol: 'none', yAxisIndex: 1,
    })
    yAxes.push({
      type: 'value', name: 'Acc', nameTextStyle: { color: palette.primary, fontFamily: monitorFontUi },
      axisLabel: { color: palette.textMuted, fontFamily: monitorFontUi }, splitLine: { show: false },
      max: 1, min: 0,
    })
  }

  return {
    tooltip: {
      trigger: 'axis',
      backgroundColor: palette.panel,
      borderColor: palette.border,
      textStyle: { color: palette.text, fontFamily: monitorFontUi },
    },
    legend: { textStyle: { color: palette.textSecondary, fontFamily: monitorFontUi }, top: 4 },
    grid: { top: 40, right: accs.length ? 60 : 16, bottom: 40, left: 60 },
    dataZoom: [{ type: 'inside' }],
    xAxis: {
      type: 'category',
      data: epochs,
      name: 'Epoch',
      nameTextStyle: { color: palette.textMuted, fontFamily: monitorFontUi },
      axisLabel: { color: palette.textMuted, fontFamily: monitorFontUi },
      axisLine: { lineStyle: { color: palette.line } },
    },
    yAxis: yAxes,
    series,
  }
})

const timelineOption = computed(() => {
  if (!taskTimeline.value.length) return null
  const now = Date.now() / 1000
  const items = timelineChartItems.value
  const categories = items.map((task) => `${task.username} · ${timelineTaskName(task)}`)

  return {
    tooltip: {
      backgroundColor: palette.panel, borderColor: palette.border, textStyle: { color: palette.text, fontFamily: monitorFontUi },
      formatter: (p) => {
        const t = items[p.dataIndex]
        return `<b>${t.username}</b><br/>PID: ${t.pid} | GPU ${t.gpu_index}<br/>命令: ${timelineTaskCommand(t)}<br/>时长: ${timelineTaskDuration(t)}<br/>显存: ${fmtBytes(t.gpu_memory_used)}<br/>状态: ${timelineTaskStatus(t)}`
      }
    },
    grid: { top: 18, right: 28, bottom: 26, left: 136 },
    xAxis: {
      type: 'time',
      axisLabel: { color: palette.textMuted, formatter: (v) => new Date(v).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }), fontFamily: monitorFontUi },
      axisLine: { lineStyle: { color: palette.line } }, splitLine: { lineStyle: { color: palette.line } },
    },
    yAxis: {
      type: 'category',
      data: categories,
      axisLabel: {
        color: palette.textSecondary,
        fontSize: 11,
        width: 124,
        overflow: 'truncate',
        fontFamily: monitorFontUi,
      },
      axisLine: { lineStyle: { color: palette.line } },
    },
    series: [{
      type: 'custom',
      renderItem: (params, api) => {
        const catIdx = api.value(0)
        const start = api.coord([api.value(1), catIdx])
        const end = api.coord([api.value(2), catIdx])
        const height = 18
        return {
          type: 'rect', shape: { x: start[0], y: start[1] - height / 2, width: Math.max(end[0] - start[0], 4), height },
          style: { fill: api.value(3) ? palette.primary : palette.inactive, opacity: 0.8 },
        }
      },
      encode: { x: [1, 2], y: 0 },
      data: items.map((t, i) => [i, t.first_seen * 1000, (t.is_active ? now : t.last_seen) * 1000, t.is_active]),
    }],
  }
})

const activeTabLabel = computed(() =>
  monitorTabs.find((tab) => tab.key === activeTab.value)?.label || '系统全貌'
)

// 系统概览的 uptime
const uptime = computed(() => {
  if (!systemDetail.value?.boot_time) return '-'
  return fmtDuration(Date.now() / 1000 - systemDetail.value.boot_time)
})

watch(activeTab, () => {
  void refreshActiveTab(true)
})

watch(timelineHours, () => {
  if (activeTab.value === 'timeline') {
    void refreshActiveTab(true)
  }
})
</script>

<template>
  <div class="monitor-page ink-page-shell">
    <MonitorWorkspaceSummary
      :active-tab-label="activeTabLabel"
      :active-user-count="userStats.length"
      :loading="loading"
    />

    <div class="workspace-nav-layout">
      <div class="workspace-nav-layout__nav">
        <WorkspaceTabs
          v-model="activeTab"
          :items="monitorTabs"
        />
      </div>

      <section class="workspace-nav-layout__content">
    <!-- ========== Tab: 系统全貌 ========== -->
    <div v-if="activeTab === 'system'" class="tab-content">
      <WorkspacePaneLayout v-if="systemDetail">
        <template #main>
          <div class="tech-card sys-info-card">
            <div class="sys-info-title">服务器概况</div>
            <div class="sys-info-items">
              <div class="sys-info-row"><span class="sys-label">运行时长</span><span class="stat-value">{{ uptime }}</span></div>
              <div class="sys-info-row"><span class="sys-label">CPU核心</span><span class="stat-value">{{ systemDetail.cpu_count_physical || '-' }}核 {{ systemDetail.cpu_count }}线程</span></div>
              <div class="sys-info-row"><span class="sys-label">系统负载</span><span class="stat-value">{{ (systemDetail.load_avg || []).map(v => v.toFixed(2)).join(' / ') }}</span></div>
              <div class="sys-info-row"><span class="sys-label">网络上传</span><span class="stat-value" style="color: var(--accent-secondary)">{{ fmtSpeed(networkSpeed.sent) }}</span></div>
              <div class="sys-info-row"><span class="sys-label">网络下载</span><span class="stat-value" style="color: var(--accent-primary)">{{ fmtSpeed(networkSpeed.recv) }}</span></div>
            </div>
          </div>

          <div class="tech-card disk-card">
            <div class="card-title">磁盘</div>
            <div class="disk-list">
              <div v-for="d in (systemDetail.disks || [])" :key="d.mountpoint" class="disk-item">
                <div class="disk-header">
                  <span class="disk-mount">{{ d.mountpoint }}</span>
                  <span class="disk-usage stat-value">{{ d.percent }}%</span>
                </div>
                <div class="progress-bar" style="height: 6px; margin-top: 4px">
                  <div class="progress-bar__fill" :style="{ width: d.percent + '%', background: usageColor(d.percent) }"></div>
                </div>
                <div class="disk-detail">{{ fmtBytes(d.used) }} / {{ fmtBytes(d.total) }} ({{ d.fstype }})</div>
              </div>
            </div>
          </div>
        </template>

        <template #side>
          <div class="tech-card resource-card">
            <div class="card-title">CPU 使用率 <span class="stat-value" :style="{ color: systemDetail.cpu_percent > 80 ? 'var(--accent-danger)' : 'var(--accent-primary)' }">{{ systemDetail.cpu_percent?.toFixed(1) }}%</span></div>
            <v-chart :option="cpuCoreOption" style="height: 200px" autoresize />
          </div>

          <div class="tech-card resource-card">
            <div class="card-title">内存</div>
            <div class="gauge-row">
              <div class="gauge-item">
                <div class="gauge-ring">
                  <svg viewBox="0 0 100 100">
                    <circle cx="50" cy="50" r="40" fill="none" :stroke="palette.line" stroke-width="8"/>
                    <circle cx="50" cy="50" r="40" fill="none" :stroke="usageColor(systemDetail.memory_percent, 60, 80)" stroke-width="8" stroke-linecap="round"
                      :stroke-dasharray="(systemDetail.memory_percent / 100 * 251.2) + ' 251.2'" stroke-dashoffset="0" transform="rotate(-90 50 50)"/>
                  </svg>
                  <span class="gauge-text stat-value">{{ systemDetail.memory_percent?.toFixed(0) }}%</span>
                </div>
                <div class="gauge-label">物理内存</div>
                <div class="gauge-sub">{{ fmtBytes(systemDetail.memory_used) }} / {{ fmtBytes(systemDetail.memory_total) }}</div>
              </div>
              <div class="gauge-item">
                <div class="gauge-ring">
                  <svg viewBox="0 0 100 100">
                    <circle cx="50" cy="50" r="40" fill="none" :stroke="palette.line" stroke-width="8"/>
                    <circle cx="50" cy="50" r="40" fill="none" :stroke="palette.secondary" stroke-width="8" stroke-linecap="round"
                      :stroke-dasharray="((systemDetail.swap_percent || 0) / 100 * 251.2) + ' 251.2'" stroke-dashoffset="0" transform="rotate(-90 50 50)"/>
                  </svg>
                  <span class="gauge-text stat-value">{{ (systemDetail.swap_percent || 0).toFixed(0) }}%</span>
                </div>
                <div class="gauge-label">Swap</div>
                <div class="gauge-sub">{{ fmtBytes(systemDetail.swap_used) }} / {{ fmtBytes(systemDetail.swap_total) }}</div>
              </div>
            </div>
          </div>
        </template>
      </WorkspacePaneLayout>
      <div v-else class="empty-state">系统数据加载中...</div>
    </div>

    <!-- ========== Tab: 训练进度 ========== -->
    <div v-if="activeTab === 'training'" class="tab-content">
      <div v-if="trainingData.length === 0" class="empty-state">
        <div class="empty-icon">训</div>
        <div>未检测到训练日志</div>
        <div class="text-sm" style="color: var(--text-muted)">Agent会自动扫描GPU进程工作目录下的日志文件</div>
      </div>
      <div v-else>
        <div v-for="task in trainingData" :key="task.pid" class="tech-card training-card">
          <div class="training-header">
            <div>
              <span class="training-user">{{ task.username }}</span>
              <span class="training-cmd">{{ task.command }}</span>
            </div>
            <div class="training-meta">
              <span class="status-badge status-badge--ok" v-if="task.has_metrics">有训练数据</span>
              <span class="status-badge status-badge--warning" v-else>未检测到指标</span>
              <span style="color: var(--text-muted)">GPU {{ task.gpu_index }} | PID {{ task.pid }}</span>
            </div>
          </div>
          <div v-if="task.has_metrics && task.latest" class="training-stats">
            <div class="training-stat">
              <span class="training-stat-label">当前Epoch</span>
              <span class="stat-value text-2xl">{{ task.latest.epoch }}</span>
              <span class="training-stat-sub">/ {{ task.total_epochs }} total</span>
            </div>
            <div class="training-stat">
              <span class="training-stat-label">最新Loss</span>
              <span class="stat-value text-2xl" style="color: var(--accent-danger)">{{ task.latest.loss?.toFixed(4) }}</span>
            </div>
            <div class="training-stat" v-if="task.latest.accuracy != null">
              <span class="training-stat-label">最新Accuracy</span>
              <span class="stat-value text-2xl" style="color: var(--accent-primary)">{{ (task.latest.accuracy * 100).toFixed(2) }}%</span>
            </div>
          </div>
          <v-chart v-if="trainingChartOption && task.has_metrics" :option="trainingChartOption" style="height: 300px" autoresize />
          <div v-if="task.working_dir" class="training-dir">工作目录: {{ task.working_dir }}</div>
        </div>
      </div>
    </div>

    <!-- ========== Tab: 用户统计 ========== -->
    <div v-if="activeTab === 'users'" class="tab-content">
      <div v-if="userStats.length === 0" class="empty-state">
        <div class="empty-icon">人</div>
        <div>当前无用户在使用GPU</div>
      </div>
      <div v-else class="user-grid">
        <div v-for="user in userStats" :key="user.username" class="tech-card user-card">
          <div class="user-header">
            <div class="user-avatar">{{ user.username.charAt(0).toUpperCase() }}</div>
            <div>
              <div class="user-name">{{ user.username }}</div>
              <div class="user-sub">{{ user.task_count }} 个任务 | {{ user.gpu_count }} 张GPU</div>
            </div>
          </div>
          <div class="user-stats-row">
            <div class="user-stat">
              <div class="user-stat-label">占用GPU</div>
              <div class="stat-value">{{ user.gpu_indices?.join(', ') }}</div>
            </div>
            <div class="user-stat">
              <div class="user-stat-label">总显存</div>
              <div class="stat-value">{{ fmtBytes(user.total_memory) }}</div>
            </div>
          </div>
          <div class="user-procs">
            <div v-for="proc in user.processes" :key="proc.pid" class="user-proc-item">
              <span class="proc-gpu">GPU{{ proc.gpu_index }}</span>
              <span class="proc-cmd">{{ proc.command || 'PID:' + proc.pid }}</span>
              <span class="proc-mem">{{ fmtBytes(proc.gpu_memory_used) }}</span>
              <span class="proc-time" v-if="proc.create_time">{{ fmtDuration(Date.now()/1000 - proc.create_time) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ========== Tab: 任务时间线 ========== -->
    <div v-if="activeTab === 'timeline'" class="tab-content">
      <WorkspacePaneLayout>
        <template #main>
          <div class="timeline-toolbar">
            <div class="timeline-toolbar__group">
              <span class="timeline-toolbar__label">时间范围</span>
              <div class="timeline-range-chips">
                <button
                  v-for="option in TIMELINE_RANGE_OPTIONS"
                  :key="option.hours"
                  class="timeline-range-chip"
                  :class="{ 'timeline-range-chip--active': timelineHours === option.hours }"
                  @click="timelineHours = option.hours"
                >
                  {{ option.label }}
                </button>
              </div>
            </div>
            <span class="timeline-toolbar__summary">近 {{ activeTimelineRangeLabel }} · {{ taskTimeline.length }} 条任务</span>
          </div>
          <div class="tech-card timeline-chart-card" v-if="timelineOption">
            <div class="timeline-panel-head">
              <div class="card-title">GPU任务占用时间线</div>
              <span class="timeline-panel-count">{{ timelineChartItems.length }} 条</span>
            </div>
            <v-chart :option="timelineOption" class="timeline-chart-card__chart" autoresize />
          </div>
          <div v-else class="empty-state">
            <div class="empty-icon">时</div>
            <div>暂无任务历史记录</div>
            <div class="text-sm" style="color: var(--text-muted)">系统启动后会自动追踪GPU进程的生命周期</div>
          </div>
        </template>

        <template #side>
          <div class="tech-card timeline-ledger-card">
            <div class="timeline-panel-head">
              <div class="card-title">时间线台账</div>
              <span class="timeline-panel-count">{{ taskTimeline.length }} 条</span>
            </div>
            <div v-if="timelineLedgerItems.length" class="timeline-ledger-list panel-scroll">
              <article
                v-for="task in timelineLedgerItems"
                :key="task.id || `${task.pid}-${task.first_seen}-${task.gpu_index}`"
                class="timeline-ledger-item"
              >
                <div class="timeline-ledger-item__head">
                  <div class="timeline-ledger-item__identity">
                    <span class="timeline-ledger-item__user">{{ task.username }}</span>
                    <span class="proc-gpu">GPU{{ task.gpu_index }}</span>
                    <span
                      class="status-badge timeline-ledger-item__status"
                      :class="{ 'status-badge--ok': task.is_active, 'timeline-ledger-item__status--ended': !task.is_active }"
                    >
                      {{ timelineTaskStatus(task) }}
                    </span>
                  </div>
                  <span class="timeline-ledger-item__memory stat-value">{{ fmtBytes(task.gpu_memory_used) }}</span>
                </div>
                <div class="timeline-ledger-item__meta">
                  <span class="stat-value">PID {{ task.pid }}</span>
                  <span>{{ fmtTime(task.first_seen) }}</span>
                  <span>{{ timelineTaskDuration(task) }}</span>
                </div>
                <div class="timeline-ledger-item__command" :title="timelineTaskCommand(task)">
                  {{ timelineTaskCommand(task) }}
                </div>
              </article>
            </div>
            <div v-else class="empty-state empty-state--compact">时间线明细会在这里持续累积。</div>
          </div>
        </template>
      </WorkspacePaneLayout>
    </div>
      </section>
    </div>

  </div>
</template>

<style scoped>
.monitor-page {
  max-width: 1400px;
  margin: 0 auto;
}

.tab-content { animation: fadeIn 0.2s ease; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }

/* ===== 系统全貌 ===== */
.sys-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.sys-info-card { grid-column: 1; padding: 18px 20px; }
.sys-info-title { font-size: 0.875rem; font-weight: 600; color: var(--accent-primary); margin-bottom: 12px; }
.sys-info-items { display: flex; flex-direction: column; gap: 10px; }
.sys-info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--border-color);
  background: var(--bg-surface);
}
.sys-label { color: var(--text-secondary); font-size: 0.8125rem; }
.card-title { font-size: 0.875rem; font-weight: 600; color: var(--text-primary); margin-bottom: 12px; display: flex; align-items: center; gap: 8px; }

.gauge-row { display: flex; gap: 32px; justify-content: center; padding: 8px 0; }
.gauge-item {
  min-width: 168px;
  text-align: center;
  padding: 14px 12px;
  border-radius: 12px;
  border: 1px solid var(--border-color);
  background: var(--bg-surface);
}
.gauge-ring { width: 100px; height: 100px; position: relative; margin: 0 auto 8px; }
.gauge-ring svg { width: 100%; height: 100%; }
.gauge-text { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; font-size: 1.25rem; }
.gauge-label { font-size: 0.8125rem; color: var(--text-secondary); }
.gauge-sub { font-size: 0.6875rem; color: var(--text-muted); margin-top: 2px; }

.disk-card { grid-column: 1 / -1; padding: 18px 20px; }
.resource-card { padding: 18px 20px; }
.disk-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }
.disk-item {
  padding: 12px;
  border-radius: 10px;
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  transition: background 0.24s ease, border-color 0.24s ease;
}
.disk-item:hover {
  background: rgba(255, 255, 255, 0.05);
  border-color: var(--border-strong);
}
.disk-header { display: flex; justify-content: space-between; }
.disk-mount { color: var(--text-primary); font-size: 0.8125rem; font-weight: 500; }
.disk-usage { font-size: 0.875rem; }
.disk-detail { font-size: 0.6875rem; color: var(--text-muted); margin-top: 4px; }

/* ===== 训练进度 ===== */
.training-card { margin-bottom: 16px; padding: 18px 20px; }
.training-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }
.training-user { font-weight: 600; color: var(--accent-primary); margin-right: 8px; }
.training-cmd { color: var(--text-secondary); font-size: 0.8125rem; font-family: 'JetBrains Mono', monospace; }
.training-meta { display: flex; gap: 8px; align-items: center; font-size: 0.75rem; }
.training-stats { display: flex; gap: 32px; margin-bottom: 16px; }
.training-stat { display: flex; flex-direction: column; gap: 2px; }
.training-stat-label { font-size: 0.6875rem; color: var(--text-muted); }
.training-stat-sub { font-size: 0.6875rem; color: var(--text-muted); }
.training-dir { font-size: 0.6875rem; color: var(--text-muted); margin-top: 8px; font-family: 'JetBrains Mono', monospace; }

/* ===== 用户统计 ===== */
.user-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(400px, 1fr)); gap: 16px; }
.user-card { padding: 18px 20px; }
.user-header { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
.user-avatar { width: 40px; height: 40px; border-radius: 10px; background: var(--gradient-blue); display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 1.125rem; color: white; }
.user-name { font-weight: 600; font-size: 1rem; }
.user-sub { font-size: 0.75rem; color: var(--text-muted); }
.user-stats-row { display: flex; gap: 24px; margin-bottom: 12px; }
.user-stat { }
.user-stat-label { font-size: 0.6875rem; color: var(--text-muted); margin-bottom: 2px; }
.user-procs { display: flex; flex-direction: column; gap: 6px; }
.user-proc-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  font-size: 0.75rem;
}
.proc-gpu { background: rgba(127, 142, 255, 0.14); color: var(--accent-primary); padding: 2px 6px; border-radius: 4px; font-size: 0.6875rem; font-weight: 600; white-space: nowrap; }
.proc-cmd { color: var(--text-secondary); flex: 1; min-width: 0; white-space: normal; overflow-wrap: anywhere; word-break: break-word; font-family: 'JetBrains Mono', monospace; line-height: 1.6; }
.proc-mem { color: var(--accent-primary); font-weight: 500; white-space: nowrap; }
.proc-time { color: var(--text-muted); white-space: nowrap; }

/* ===== 时间线 ===== */
.timeline-chart-card { padding: 18px 20px; }
.timeline-ledger-card { padding: 18px 20px; }
.timeline-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.timeline-toolbar__group {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.timeline-toolbar__label {
  color: var(--text-muted);
  font-size: 0.72rem;
  letter-spacing: 0.08em;
}
.timeline-range-chips {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px;
  border-radius: 999px;
  border: 1px solid var(--border-color);
  background: rgba(255, 255, 255, 0.02);
}
.timeline-range-chip {
  padding: 6px 12px;
  border-radius: 999px;
  border: 1px solid transparent;
  background: transparent;
  color: var(--text-secondary);
  font-size: 0.75rem;
  line-height: 1;
  transition: background 0.2s ease, border-color 0.2s ease, color 0.2s ease;
}
.timeline-range-chip:hover {
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.04);
}
.timeline-range-chip--active {
  background: linear-gradient(135deg, rgba(127, 142, 255, 0.2), rgba(110, 184, 255, 0.1));
  border-color: rgba(127, 142, 255, 0.32);
  color: var(--text-primary);
}
.timeline-toolbar__summary {
  color: var(--text-muted);
  font-size: 0.75rem;
}
.timeline-panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}
.timeline-panel-head .card-title {
  margin-bottom: 0;
}
.timeline-panel-count {
  padding: 4px 8px;
  border-radius: 999px;
  border: 1px solid rgba(127, 142, 255, 0.16);
  background: rgba(127, 142, 255, 0.08);
  color: var(--text-secondary);
  font-size: 0.72rem;
  white-space: nowrap;
}
.timeline-chart-card__chart {
  height: 428px;
}
.timeline-ledger-list {
  display: grid;
  gap: 10px;
  max-height: 528px;
  padding-right: 2px;
}
.timeline-ledger-item {
  display: grid;
  gap: 8px;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid var(--border-color);
  background: rgba(255, 255, 255, 0.025);
  transition: border-color 0.2s ease, background 0.2s ease, transform 0.2s ease;
}
.timeline-ledger-item:hover {
  border-color: rgba(127, 142, 255, 0.26);
  background: rgba(255, 255, 255, 0.04);
  transform: translateY(-1px);
}
.timeline-ledger-item__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.timeline-ledger-item__identity {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  min-width: 0;
}
.timeline-ledger-item__user {
  color: var(--text-primary);
  font-size: 0.875rem;
  font-weight: 600;
}
.timeline-ledger-item__status {
  white-space: nowrap;
}
.timeline-ledger-item__status--ended {
  color: var(--text-secondary);
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.08);
}
.timeline-ledger-item__memory {
  color: var(--accent-primary);
  font-size: 0.78rem;
  white-space: nowrap;
}
.timeline-ledger-item__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 12px;
  color: var(--text-muted);
  font-size: 0.72rem;
}
.timeline-ledger-item__command {
  color: var(--text-secondary);
  font-size: 0.74rem;
  line-height: 1.5;
  font-family: 'JetBrains Mono', monospace;
  display: -webkit-box;
  overflow: hidden;
  overflow-wrap: anywhere;
  word-break: break-word;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

@media (max-width: 900px) {
  .timeline-chart-card__chart {
    height: 360px;
  }

  .timeline-ledger-list {
    max-height: none;
  }
}

/* ===== 空状态 ===== */
.empty-state { text-align: center; padding: 60px 20px; color: var(--text-secondary); }
.empty-state--compact { padding: 24px 18px; }
.empty-icon {
  font-size: 2.5rem;
  margin-bottom: 12px;
  opacity: 0.5;
  color: var(--accent-secondary);
}

</style>

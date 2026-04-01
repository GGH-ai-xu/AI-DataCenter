<script setup>
/**
 * MonitorCenter.vue - 观察中心
 * 四大功能：训练进度、用户统计、任务时间线、系统全貌
 */
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useAppStore } from '../stores/app'
import { getSystemDetail, getTrainingProgress, getUserStats, getTaskHistory } from '../services/api'
import VChart from 'vue-echarts'
import WorkspacePaneLayout from '../components/workspace/WorkspacePaneLayout.vue'
import WorkspaceSummary from '../components/workspace/WorkspaceSummary.vue'
import WorkspaceTabs from '../components/workspace/WorkspaceTabs.vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart, CustomChart, GaugeChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, TitleComponent } from 'echarts/components'

use([CanvasRenderer, LineChart, BarChart, CustomChart, GaugeChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, TitleComponent])

const store = useAppStore()
const activeTab = ref('system')
const loading = ref(false)
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

let refreshTimer = null

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

// ===== 数据加载 =====
async function loadAll() {
  loading.value = true
  try {
    const tasks = []
    tasks.push(loadSystemDetail())
    tasks.push(loadTraining())
    tasks.push(loadUsers())
    tasks.push(loadTimeline())
    await Promise.allSettled(tasks)
  } finally {
    loading.value = false
  }
}

async function loadSystemDetail() {
  try {
    const { data } = await getSystemDetail()
    // 计算网络速率
    if (data.network && prevNetwork.value) {
      const dt = data.timestamp - (systemDetail.value?.timestamp || data.timestamp)
      if (dt > 0) {
        networkSpeed.value = {
          sent: (data.network.bytes_sent - prevNetwork.value.bytes_sent) / dt,
          recv: (data.network.bytes_recv - prevNetwork.value.bytes_recv) / dt,
        }
      }
    }
    if (data.network) prevNetwork.value = { ...data.network }
    systemDetail.value = data
  } catch (e) { /* 静默 */ }
}

async function loadTraining() {
  try {
    const { data } = await getTrainingProgress()
    trainingData.value = data.training || []
  } catch (e) { /* 静默 */ }
}

async function loadUsers() {
  try {
    const { data } = await getUserStats()
    userStats.value = data.users || []
  } catch (e) { /* 静默 */ }
}

async function loadTimeline() {
  try {
    const { data } = await getTaskHistory(timelineHours.value)
    taskTimeline.value = data.timeline || []
  } catch (e) { /* 静默 */ }
}

// ===== 图表配置 =====
const cpuCoreOption = computed(() => {
  const cores = systemDetail.value?.cpu_per_core || []
  return {
    tooltip: { trigger: 'axis', backgroundColor: 'rgba(248, 245, 240, 0.97)', borderColor: '#3A5F4B', textStyle: { color: '#2C2C2C' } },
    grid: { top: 30, right: 16, bottom: 24, left: 40 },
    xAxis: { type: 'category', data: cores.map((_, i) => 'C' + i), axisLabel: { color: '#999999', fontSize: 10 }, axisLine: { lineStyle: { color: '#1e293b' } } },
    yAxis: { type: 'value', max: 100, axisLabel: { color: '#999999', formatter: '{value}%' }, splitLine: { lineStyle: { color: '#1e293b' } } },
    series: [{
      type: 'bar', data: cores.map(v => ({
        value: v,
        itemStyle: { color: v > 80 ? '#C41E3A' : v > 50 ? '#B8860B' : '#3A5F4B' }
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
    lineStyle: { color: '#C41E3A', width: 2 }, itemStyle: { color: '#C41E3A' },
    symbol: 'none', yAxisIndex: 0,
  }]
  const yAxes = [{
    type: 'value', name: 'Loss', nameTextStyle: { color: '#C41E3A' },
    axisLabel: { color: '#999999' }, splitLine: { lineStyle: { color: '#1e293b' } },
  }]

  if (accs.length > 0) {
    series.push({
      name: 'Accuracy', type: 'line', data: task.metrics.map(m => m.accuracy),
      smooth: true, lineStyle: { color: '#2E8B57', width: 2 }, itemStyle: { color: '#2E8B57' },
      symbol: 'none', yAxisIndex: 1,
    })
    yAxes.push({
      type: 'value', name: 'Acc', nameTextStyle: { color: '#2E8B57' },
      axisLabel: { color: '#999999' }, splitLine: { show: false },
      max: 1, min: 0,
    })
  }

  return {
    tooltip: { trigger: 'axis', backgroundColor: 'rgba(248, 245, 240, 0.97)', borderColor: '#3A5F4B', textStyle: { color: '#2C2C2C' } },
    legend: { textStyle: { color: '#666666' }, top: 4 },
    grid: { top: 40, right: accs.length ? 60 : 16, bottom: 40, left: 60 },
    dataZoom: [{ type: 'inside' }],
    xAxis: { type: 'category', data: epochs, name: 'Epoch', nameTextStyle: { color: '#999999' }, axisLabel: { color: '#999999' }, axisLine: { lineStyle: { color: '#1e293b' } } },
    yAxis: yAxes,
    series,
  }
})

const timelineOption = computed(() => {
  if (!taskTimeline.value.length) return null
  const now = Date.now() / 1000
  const items = taskTimeline.value.slice(0, 20)
  const categories = items.map((t, i) => {
    const cmd = (t.command || '').split('/').pop().split(' ')[0] || 'PID:' + t.pid
    return `${t.username}/${cmd}`
  })

  return {
    tooltip: {
      backgroundColor: 'rgba(248, 245, 240, 0.97)', borderColor: '#3A5F4B', textStyle: { color: '#2C2C2C' },
      formatter: (p) => {
        const t = items[p.dataIndex]
        const dur = (t.last_seen - t.first_seen)
        return `<b>${t.username}</b><br/>PID: ${t.pid} | GPU ${t.gpu_index}<br/>命令: ${t.command}<br/>时长: ${fmtDuration(dur)}<br/>显存: ${fmtBytes(t.gpu_memory_used)}<br/>状态: ${t.is_active ? '运行中' : '已结束'}`
      }
    },
    grid: { top: 16, right: 80, bottom: 24, left: 160 },
    xAxis: {
      type: 'time',
      axisLabel: { color: '#999999', formatter: (v) => new Date(v).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) },
      axisLine: { lineStyle: { color: '#1e293b' } }, splitLine: { lineStyle: { color: '#1e293b' } },
    },
    yAxis: { type: 'category', data: categories, axisLabel: { color: '#666666', fontSize: 11, width: 150, overflow: 'truncate' }, axisLine: { lineStyle: { color: '#1e293b' } } },
    series: [{
      type: 'custom',
      renderItem: (params, api) => {
        const catIdx = api.value(0)
        const start = api.coord([api.value(1), catIdx])
        const end = api.coord([api.value(2), catIdx])
        const height = 16
        return {
          type: 'rect', shape: { x: start[0], y: start[1] - height / 2, width: Math.max(end[0] - start[0], 4), height },
          style: { fill: api.value(3) ? '#3A5F4B' : '#999999', opacity: 0.8 },
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

onMounted(() => {
  loadAll()
  refreshTimer = setInterval(loadAll, 10000)
})

onUnmounted(() => {
  clearInterval(refreshTimer)
})
</script>

<template>
  <div class="monitor-page ink-page-shell">
    <WorkspaceSummary
      eyebrow="系统全貌 · 训练进度 · 用户画像 · 任务时间线"
      title="先静观其势，再判断系统应如何治理"
      :description="`当前聚焦 ${activeTabLabel}，把训练、用户、时间线和系统底盘拆入独立舱位，避免不同观察任务相互挤压。`"
    >
      <template #meta>
        <div class="ink-inline-meta">
          <span class="status-badge status-badge--ok">{{ trainingData.length }} 个训练任务</span>
          <span class="status-badge status-badge--warning">{{ userStats.length }} 个活跃用户</span>
          <span class="status-badge" :class="loading ? 'status-badge--warning' : 'status-badge--ok'">
            {{ loading ? '数据刷新中' : '观察就绪' }}
          </span>
        </div>
      </template>
      <div class="monitor-summary-grid">
        <div class="monitor-summary-card">
          <div class="monitor-summary-card__label">当前聚焦</div>
          <div class="monitor-summary-card__value">{{ activeTabLabel }}</div>
          <div class="monitor-summary-card__hint">在不同观察任务之间切换，但保持顶部判断区稳定。</div>
        </div>
        <div class="monitor-summary-card">
          <div class="monitor-summary-card__label">时间线样本</div>
          <div class="monitor-summary-card__value">{{ taskTimeline.length }}</div>
          <div class="monitor-summary-card__hint">已采集的任务生命周期样本数量。</div>
        </div>
        <div class="monitor-summary-card">
          <div class="monitor-summary-card__label">活跃用户画像</div>
          <div class="monitor-summary-card__value">{{ userStats.length }}</div>
          <div class="monitor-summary-card__hint">当前已聚合的用户占用与画像样本数量。</div>
        </div>
      </div>
    </WorkspaceSummary>

    <WorkspaceTabs v-model="activeTab" :items="monitorTabs" />

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
              <div class="sys-info-row"><span class="sys-label">网络上传</span><span class="stat-value" style="color: #2E8B57">{{ fmtSpeed(networkSpeed.sent) }}</span></div>
              <div class="sys-info-row"><span class="sys-label">网络下载</span><span class="stat-value" style="color: #3A5F4B">{{ fmtSpeed(networkSpeed.recv) }}</span></div>
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
                  <div class="progress-bar__fill" :style="{ width: d.percent + '%', background: d.percent > 90 ? '#C41E3A' : d.percent > 70 ? '#B8860B' : '#3A5F4B' }"></div>
                </div>
                <div class="disk-detail">{{ fmtBytes(d.used) }} / {{ fmtBytes(d.total) }} ({{ d.fstype }})</div>
              </div>
            </div>
          </div>
        </template>

        <template #side>
          <div class="tech-card">
            <div class="card-title">CPU 使用率 <span class="stat-value" :style="{ color: systemDetail.cpu_percent > 80 ? '#C41E3A' : '#3A5F4B' }">{{ systemDetail.cpu_percent?.toFixed(1) }}%</span></div>
            <v-chart :option="cpuCoreOption" style="height: 200px" autoresize />
          </div>

          <div class="tech-card">
            <div class="card-title">内存</div>
            <div class="gauge-row">
              <div class="gauge-item">
                <div class="gauge-ring">
                  <svg viewBox="0 0 100 100">
                    <circle cx="50" cy="50" r="40" fill="none" stroke="#1e293b" stroke-width="8"/>
                    <circle cx="50" cy="50" r="40" fill="none" :stroke="systemDetail.memory_percent > 80 ? '#C41E3A' : '#3A5F4B'" stroke-width="8" stroke-linecap="round"
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
                    <circle cx="50" cy="50" r="40" fill="none" stroke="#1e293b" stroke-width="8"/>
                    <circle cx="50" cy="50" r="40" fill="none" stroke="#5B4B8C" stroke-width="8" stroke-linecap="round"
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
              <span class="stat-value text-2xl" style="color: #C41E3A">{{ task.latest.loss?.toFixed(4) }}</span>
            </div>
            <div class="training-stat" v-if="task.latest.accuracy != null">
              <span class="training-stat-label">最新Accuracy</span>
              <span class="stat-value text-2xl" style="color: #2E8B57">{{ (task.latest.accuracy * 100).toFixed(2) }}%</span>
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
          <div class="timeline-controls">
            <span style="color: var(--text-secondary)">时间范围:</span>
            <button v-for="h in [1, 6, 24, 72]" :key="h" class="btn-tech btn-sm" :class="{ 'btn-tech--active': timelineHours === h }"
              @click="timelineHours = h; loadTimeline()">{{ h >= 24 ? (h/24) + '天' : h + '小时' }}</button>
          </div>
          <div class="tech-card" v-if="timelineOption">
            <div class="card-title">GPU任务占用时间线</div>
            <v-chart :option="timelineOption" style="height: 400px" autoresize />
          </div>
          <div v-else class="empty-state">
            <div class="empty-icon">时</div>
            <div>暂无任务历史记录</div>
            <div class="text-sm" style="color: var(--text-muted)">系统启动后会自动追踪GPU进程的生命周期</div>
          </div>
        </template>

        <template #side>
          <div class="tech-card">
            <div class="card-title">时间线台账 <span style="color: var(--text-muted); font-size: 0.75rem">({{ taskTimeline.length }} 条)</span></div>
            <div v-if="taskTimeline.length" class="table-wrap panel-scroll">
              <table class="data-table">
                <thead>
                  <tr><th>用户</th><th>PID</th><th>GPU</th><th>命令</th><th>显存</th><th>开始</th><th>时长</th><th>状态</th></tr>
                </thead>
                <tbody>
                  <tr v-for="t in taskTimeline.slice(0, 30)" :key="t.id">
                    <td>{{ t.username }}</td>
                    <td class="stat-value">{{ t.pid }}</td>
                    <td><span class="proc-gpu">GPU{{ t.gpu_index }}</span></td>
                    <td class="proc-cmd-cell" :title="t.command">{{ t.command }}</td>
                    <td class="stat-value">{{ fmtBytes(t.gpu_memory_used) }}</td>
                    <td>{{ fmtTime(t.first_seen) }}</td>
                    <td class="stat-value">{{ fmtDuration(t.last_seen - t.first_seen) }}</td>
                    <td><span :class="t.is_active ? 'status-badge status-badge--ok' : 'status-badge'">{{ t.is_active ? '运行中' : '已结束' }}</span></td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-else class="empty-state empty-state--compact">时间线明细会在这里持续累积。</div>
          </div>
        </template>
      </WorkspacePaneLayout>
    </div>

  </div>
</template>

<style scoped>
.monitor-page {
  max-width: 1400px;
  margin: 0 auto;
}

.monitor-summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.monitor-summary-card {
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid rgba(58, 95, 75, 0.08);
  background: rgba(255, 252, 247, 0.66);
}

.monitor-summary-card__label {
  font-size: 0.74rem;
  color: var(--text-muted);
  line-height: 1.6;
}

.monitor-summary-card__value {
  margin: 6px 0;
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--text-primary);
}

.monitor-summary-card__hint {
  font-size: 0.75rem;
  color: var(--text-muted);
  line-height: 1.7;
}

.tab-content { animation: fadeIn 0.2s ease; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }

/* ===== 系统全貌 ===== */
.sys-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.sys-info-card { grid-column: 1; }
.sys-info-title { font-size: 0.875rem; font-weight: 600; color: var(--accent-primary); margin-bottom: 12px; }
.sys-info-items { display: flex; flex-direction: column; gap: 10px; }
.sys-info-row { display: flex; justify-content: space-between; align-items: center; }
.sys-label { color: var(--text-secondary); font-size: 0.8125rem; }
.card-title { font-size: 0.875rem; font-weight: 600; color: var(--text-primary); margin-bottom: 12px; display: flex; align-items: center; gap: 8px; }

.gauge-row { display: flex; gap: 32px; justify-content: center; padding: 8px 0; }
.gauge-item { text-align: center; }
.gauge-ring { width: 100px; height: 100px; position: relative; margin: 0 auto 8px; }
.gauge-ring svg { width: 100%; height: 100%; }
.gauge-text { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; font-size: 1.25rem; }
.gauge-label { font-size: 0.8125rem; color: var(--text-secondary); }
.gauge-sub { font-size: 0.6875rem; color: var(--text-muted); margin-top: 2px; }

.disk-card { grid-column: 1 / -1; }
.disk-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }
.disk-item { padding: 10px; border-radius: 8px; background: rgba(255, 255, 255, 0.6); }
.disk-header { display: flex; justify-content: space-between; }
.disk-mount { color: var(--text-primary); font-size: 0.8125rem; font-weight: 500; }
.disk-usage { font-size: 0.875rem; }
.disk-detail { font-size: 0.6875rem; color: var(--text-muted); margin-top: 4px; }

/* ===== 训练进度 ===== */
.training-card { margin-bottom: 16px; }
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
.user-card { }
.user-header { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
.user-avatar { width: 40px; height: 40px; border-radius: 10px; background: var(--gradient-blue); display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 1.125rem; color: white; }
.user-name { font-weight: 600; font-size: 1rem; }
.user-sub { font-size: 0.75rem; color: var(--text-muted); }
.user-stats-row { display: flex; gap: 24px; margin-bottom: 12px; }
.user-stat { }
.user-stat-label { font-size: 0.6875rem; color: var(--text-muted); margin-bottom: 2px; }
.user-procs { display: flex; flex-direction: column; gap: 6px; }
.user-proc-item { display: flex; align-items: center; gap: 8px; padding: 6px 8px; border-radius: 6px; background: rgba(255, 255, 255, 0.6); font-size: 0.75rem; }
.proc-gpu { background: rgba(58, 95, 75, 0.15); color: var(--accent-primary); padding: 2px 6px; border-radius: 4px; font-size: 0.6875rem; font-weight: 600; white-space: nowrap; }
.proc-cmd { color: var(--text-secondary); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-family: 'JetBrains Mono', monospace; }
.proc-mem { color: var(--accent-primary); font-weight: 500; white-space: nowrap; }
.proc-time { color: var(--text-muted); white-space: nowrap; }

/* ===== 时间线 ===== */
.timeline-controls { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; }
.btn-sm { padding: 4px 12px; font-size: 0.75rem; }
.btn-tech--active { background: rgba(58, 95, 75, 0.15); color: var(--accent-primary); border-color: var(--accent-primary); }

.table-wrap { overflow-x: auto; }
.data-table { width: 100%; border-collapse: collapse; font-size: 0.8125rem; }
.data-table th { text-align: left; padding: 8px 12px; color: var(--text-muted); font-weight: 500; border-bottom: 1px solid var(--border-color); }
.data-table td { padding: 8px 12px; border-bottom: 1px solid rgba(30, 41, 59, 0.5); }
.data-table tr:hover td { background: rgba(58, 95, 75, 0.03); }
.proc-cmd-cell { max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-family: 'JetBrains Mono', monospace; color: var(--text-secondary); font-size: 0.75rem; }

/* ===== 空状态 ===== */
.empty-state { text-align: center; padding: 60px 20px; color: var(--text-secondary); }
.empty-state--compact { padding: 24px 18px; }
.empty-icon { font-size: 2.5rem; margin-bottom: 12px; opacity: 0.5; }

@media (max-width: 980px) {
  .monitor-summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>

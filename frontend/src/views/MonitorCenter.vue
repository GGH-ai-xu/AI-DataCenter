<script setup>
/**
 * MonitorCenter.vue - 观察中心
 * 四大功能：训练进度、用户统计、任务时间线、系统全貌
 */
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useAppStore } from '../stores/app'
import { getMonitorReplay, getSystemDetail, getTrainingProgress, getUserStats, getTaskHistory } from '../services/api'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart, CustomChart, GaugeChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, TitleComponent } from 'echarts/components'

use([CanvasRenderer, LineChart, BarChart, CustomChart, GaugeChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, TitleComponent])

const store = useAppStore()
const activeTab = ref('system')
const loading = ref(false)

// 数据状态
const systemDetail = ref(null)
const trainingData = ref([])
const userStats = ref([])
const taskTimeline = ref([])
const replayFrames = ref([])
const timelineHours = ref(24)
const replayHours = ref(24)
const replayBucketMinutes = ref(10)
const selectedReplayIndex = ref(0)
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
    tasks.push(loadReplay())
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

async function loadReplay() {
  try {
    const { data } = await getMonitorReplay(replayHours.value, replayBucketMinutes.value)
    replayFrames.value = data.frames || []
    selectedReplayIndex.value = replayFrames.value.length ? replayFrames.value.length - 1 : 0
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

const selectedReplayFrame = computed(() => {
  if (!replayFrames.value.length) return null
  return replayFrames.value[selectedReplayIndex.value] || replayFrames.value[replayFrames.value.length - 1]
})

const replayOption = computed(() => {
  if (!replayFrames.value.length) return null
  return {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(248, 245, 240, 0.97)',
      borderColor: '#3A5F4B',
      textStyle: { color: '#2C2C2C' },
    },
    legend: { textStyle: { color: '#666666' }, top: 4 },
    grid: { top: 44, right: 20, bottom: 48, left: 56 },
    xAxis: {
      type: 'category',
      data: replayFrames.value.map((frame) =>
        new Date(frame.bucket_ts * 1000).toLocaleTimeString('zh-CN', {
          hour: '2-digit',
          minute: '2-digit',
        }),
      ),
      axisLabel: { color: '#999999' },
      axisLine: { lineStyle: { color: '#1e293b' } },
    },
    yAxis: [
      {
        type: 'value',
        name: '功率',
        axisLabel: { color: '#999999', formatter: '{value}W' },
        splitLine: { lineStyle: { color: '#1e293b' } },
      },
      {
        type: 'value',
        name: '事件',
        axisLabel: { color: '#999999' },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: '平均功率',
        type: 'line',
        smooth: true,
        data: replayFrames.value.map((frame) => frame.avg_power),
        lineStyle: { color: '#3A5F4B', width: 2 },
        itemStyle: { color: '#3A5F4B' },
        symbol: 'none',
      },
      {
        name: '活跃任务',
        type: 'bar',
        yAxisIndex: 1,
        data: replayFrames.value.map((frame) => frame.active_task_count),
        itemStyle: { color: 'rgba(46,139,87,0.55)' },
        barMaxWidth: 16,
      },
      {
        name: '告警',
        type: 'bar',
        yAxisIndex: 1,
        data: replayFrames.value.map((frame) => frame.alert_count),
        itemStyle: { color: 'rgba(196,30,58,0.55)' },
        barMaxWidth: 16,
      },
      {
        name: '调度动作',
        type: 'line',
        yAxisIndex: 1,
        data: replayFrames.value.map((frame) => frame.schedule_action_count),
        lineStyle: { color: '#B8860B', width: 2 },
        itemStyle: { color: '#B8860B' },
        symbol: 'circle',
        symbolSize: 5,
      },
    ],
  }
})

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
    <section class="ink-page-head tech-card">
      <div class="ink-page-head__body">
        <div class="ink-page-head__eyebrow">系统全貌 · 训练进度 · 用户画像 · 任务时间线</div>
        <h2 class="ink-page-head__title">先静观其势，再判断系统应如何治理</h2>
        <p class="ink-page-head__desc">
          这里把训练过程、用户占用、时间线和系统资源放到同一张观察图里，帮助你从“单点告警”升级到“整体态势判断”。
        </p>
      </div>
      <div class="ink-page-head__side">
        <div class="ink-page-head__quote">“见微知著，察势而动。”</div>
        <div class="ink-inline-meta">
          <span class="status-badge status-badge--ok">{{ trainingData.length }} 个训练任务</span>
          <span class="status-badge status-badge--warning">{{ userStats.length }} 个活跃用户</span>
          <span class="status-badge" :class="loading ? 'status-badge--warning' : 'status-badge--ok'">
            {{ loading ? '数据刷新中' : '观察就绪' }}
          </span>
        </div>
      </div>
    </section>

    <div class="page-header">
      <div class="page-header__meta">当前聚焦：{{ activeTab === 'system' ? '系统全貌' : activeTab === 'training' ? '训练进度' : activeTab === 'users' ? '用户统计' : activeTab === 'timeline' ? '任务时间线' : '治理回放' }}</div>
      <div class="tab-bar">
        <button v-for="tab in [
          { key: 'system', label: '系统全貌', icon: '总' },
          { key: 'training', label: '训练进度', icon: '训' },
          { key: 'users', label: '用户统计', icon: '人' },
          { key: 'timeline', label: '任务时间线', icon: '时' },
          { key: 'replay', label: '治理回放', icon: '回' },
        ]" :key="tab.key" class="tab-btn" :class="{ 'tab-btn--active': activeTab === tab.key }" @click="activeTab = tab.key">
          <span>{{ tab.icon }}</span> {{ tab.label }}
        </button>
      </div>
    </div>

    <!-- ========== Tab: 系统全貌 ========== -->
    <div v-if="activeTab === 'system'" class="tab-content">
      <div v-if="systemDetail" class="sys-grid">
        <!-- 运行时长 + 负载 -->
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

        <!-- CPU 使用率 -->
        <div class="tech-card">
          <div class="card-title">CPU 使用率 <span class="stat-value" :style="{ color: systemDetail.cpu_percent > 80 ? '#C41E3A' : '#3A5F4B' }">{{ systemDetail.cpu_percent?.toFixed(1) }}%</span></div>
          <v-chart :option="cpuCoreOption" style="height: 200px" autoresize />
        </div>

        <!-- 内存 -->
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

        <!-- 磁盘 -->
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
      </div>
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
      <!-- 时间线表格 -->
      <div class="tech-card" v-if="taskTimeline.length" style="margin-top: 16px">
        <div class="card-title">历史记录 <span style="color: var(--text-muted); font-size: 0.75rem">({{ taskTimeline.length }} 条)</span></div>
        <div class="table-wrap">
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
      </div>
    </div>

    <div v-if="activeTab === 'replay'" class="tab-content">
      <div class="timeline-controls">
        <span style="color: var(--text-secondary)">回放窗口:</span>
        <button
          v-for="h in [6, 24, 72]"
          :key="`replay-${h}`"
          class="btn-tech btn-sm"
          :class="{ 'btn-tech--active': replayHours === h }"
          @click="replayHours = h; loadReplay()"
        >
          {{ h >= 24 ? (h / 24) + '天' : h + '小时' }}
        </button>
        <span style="color: var(--text-secondary); margin-left: 8px">粒度:</span>
        <button
          v-for="bucket in [5, 10, 15]"
          :key="`bucket-${bucket}`"
          class="btn-tech btn-sm"
          :class="{ 'btn-tech--active': replayBucketMinutes === bucket }"
          @click="replayBucketMinutes = bucket; loadReplay()"
        >
          {{ bucket }} 分钟
        </button>
      </div>

      <div v-if="replayFrames.length">
        <div class="tech-card replay-card">
          <div class="card-title">治理回放轴</div>
          <input
            v-model.number="selectedReplayIndex"
            type="range"
            min="0"
            :max="Math.max(replayFrames.length - 1, 0)"
            class="replay-slider"
          />
          <div class="replay-meta" v-if="selectedReplayFrame">
            <span>时间 {{ fmtTime(selectedReplayFrame.bucket_ts) }}</span>
            <span>活跃任务 {{ selectedReplayFrame.active_task_count }}</span>
            <span>告警 {{ selectedReplayFrame.alert_count }}</span>
            <span>动作 {{ selectedReplayFrame.schedule_action_count }}</span>
          </div>
        </div>

        <div class="replay-grid">
          <div class="tech-card replay-stat">
            <div class="replay-stat__label">平均功率</div>
            <div class="replay-stat__value stat-value">{{ selectedReplayFrame?.avg_power?.toFixed(1) || '0.0' }}W</div>
            <div class="replay-stat__hint">用于复盘该时间桶的整体负载强度</div>
          </div>
          <div class="tech-card replay-stat">
            <div class="replay-stat__label">最高温度</div>
            <div class="replay-stat__value stat-value">{{ selectedReplayFrame?.max_temp || 0 }}°C</div>
            <div class="replay-stat__hint">帮助定位热风险是否伴随动作触发</div>
          </div>
          <div class="tech-card replay-stat">
            <div class="replay-stat__label">活跃用户</div>
            <div class="replay-stat__value stat-value">{{ selectedReplayFrame?.active_user_count || 0 }}</div>
            <div class="replay-stat__hint">观察资源竞争是否集中到少数用户</div>
          </div>
          <div class="tech-card replay-stat">
            <div class="replay-stat__label">关键告警</div>
            <div class="replay-stat__value stat-value">{{ selectedReplayFrame?.critical_alert_count || 0 }}</div>
            <div class="replay-stat__hint">衡量该窗口是否进入高风险区</div>
          </div>
        </div>

        <div class="tech-card">
          <div class="card-title">回放趋势</div>
          <v-chart :option="replayOption" style="height: 340px" autoresize />
        </div>

        <div class="tech-card replay-actions" v-if="selectedReplayFrame?.schedule_actions?.length">
          <div class="card-title">当前时间桶的调度动作</div>
          <div class="replay-action-list">
            <div
              v-for="(item, index) in selectedReplayFrame.schedule_actions"
              :key="`${selectedReplayFrame.bucket_ts}-${index}`"
              class="replay-action-item"
            >
              <div class="replay-action-item__top">
                <span>{{ item.action }}</span>
                <span>{{ item.result || 'unknown' }}</span>
              </div>
              <div class="replay-action-item__reason">{{ item.reason }}</div>
            </div>
          </div>
        </div>
      </div>
      <div v-else class="empty-state">
        <div class="empty-icon">回</div>
        <div>暂无可回放治理数据</div>
        <div class="text-sm" style="color: var(--text-muted)">等待真实功耗、告警与调度日志继续累积</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.monitor-page {
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.page-header__meta {
  font-size: 0.78rem;
  color: var(--text-muted);
  letter-spacing: 0.14em;
}

.tab-bar {
  display: flex;
  gap: 6px;
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  background: transparent;
  color: var(--text-secondary);
  font-size: 0.8125rem;
  cursor: pointer;
  transition: all 0.2s;
}
.tab-btn:hover { background: rgba(58, 95, 75, 0.06); color: var(--text-primary); }
.tab-btn--active { background: rgba(58, 95, 75, 0.12); color: var(--accent-primary); border-color: var(--accent-primary); }

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

.replay-card {
  margin-bottom: 16px;
}

.replay-slider {
  width: 100%;
  margin: 14px 0 10px;
  accent-color: var(--accent-primary);
}

.replay-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 0.75rem;
  color: var(--text-muted);
}

.replay-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  margin-bottom: 16px;
}

.replay-stat {
  padding: 16px;
}

.replay-stat__label,
.replay-stat__hint,
.replay-action-item__reason {
  font-size: 0.75rem;
  color: var(--text-muted);
  line-height: 1.6;
}

.replay-stat__value {
  font-size: 1.8rem;
  margin: 8px 0 6px;
}

.replay-actions {
  margin-top: 16px;
}

.replay-action-list {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.replay-action-item {
  padding: 12px 14px;
  border-radius: 10px;
  background: rgba(58, 95, 75, 0.04);
  border: 1px solid rgba(58, 95, 75, 0.08);
}

.replay-action-item__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
  color: var(--text-primary);
  font-size: 0.8125rem;
}

.table-wrap { overflow-x: auto; }
.data-table { width: 100%; border-collapse: collapse; font-size: 0.8125rem; }
.data-table th { text-align: left; padding: 8px 12px; color: var(--text-muted); font-weight: 500; border-bottom: 1px solid var(--border-color); }
.data-table td { padding: 8px 12px; border-bottom: 1px solid rgba(30, 41, 59, 0.5); }
.data-table tr:hover td { background: rgba(58, 95, 75, 0.03); }
.proc-cmd-cell { max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-family: 'JetBrains Mono', monospace; color: var(--text-secondary); font-size: 0.75rem; }

/* ===== 空状态 ===== */
.empty-state { text-align: center; padding: 60px 20px; color: var(--text-secondary); }
.empty-icon { font-size: 2.5rem; margin-bottom: 12px; opacity: 0.5; }

@media (max-width: 980px) {
  .page-header {
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
  }

  .tab-bar {
    overflow-x: auto;
    padding-bottom: 4px;
  }

  .tab-btn {
    flex: 0 0 auto;
  }

  .replay-grid,
  .replay-action-list {
    grid-template-columns: 1fr;
  }
}
</style>

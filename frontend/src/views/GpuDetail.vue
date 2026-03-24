<script setup>
/**
 * GpuDetail.vue - 单GPU详情页，含历史趋势图
 */
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAppStore } from '../stores/app'
import { getGpuHistory } from '../services/api'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent } from 'echarts/components'
import VChart from 'vue-echarts'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent])

const route = useRoute()
const router = useRouter()
const store = useAppStore()
const gpuIndex = parseInt(route.params.index)

const history = ref([])
const selectedRange = ref(1)
const loading = ref(false)

const gpu = computed(() => store.gpus.find(g => g.index === gpuIndex) || {})

const ranges = [
  { label: '1小时', value: 1 },
  { label: '6小时', value: 6 },
  { label: '24小时', value: 24 },
  { label: '7天', value: 168 },
]

async function loadHistory(hours) {
  selectedRange.value = hours
  loading.value = true
  try {
    const { data } = await getGpuHistory(gpuIndex, hours)
    history.value = data.data || []
  } catch (e) {
    history.value = []
  }
  loading.value = false
}

const chartOption = computed(() => {
  const times = history.value.map(d => new Date(d.timestamp * 1000))
  const makeStyle = (color) => ({
    type: 'line', smooth: true, symbol: 'none',
    lineStyle: { width: 1.5, color },
    areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: color + '25' }, { offset: 1, color: color + '05' }] } },
  })

  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(17,24,39,0.9)',
      borderColor: 'rgba(56,189,248,0.2)',
      textStyle: { color: '#f1f5f9', fontSize: 12 },
    },
    legend: {
      data: ['温度', '功耗', 'GPU利用率', '显存利用率'],
      textStyle: { color: '#94a3b8', fontSize: 11 },
      top: 0,
    },
    grid: { left: 50, right: 20, top: 36, bottom: 60 },
    dataZoom: [{ type: 'inside' }, { type: 'slider', height: 20, bottom: 8, borderColor: 'transparent', backgroundColor: 'rgba(255,255,255,0.04)', fillerColor: 'rgba(56,189,248,0.1)', handleStyle: { color: '#38bdf8' }, textStyle: { color: '#64748b' } }],
    xAxis: { type: 'category', data: times, axisLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } }, axisTick: { show: false }, axisLabel: { color: '#64748b', fontSize: 10, formatter: (v) => new Date(v).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) } },
    yAxis: { type: 'value', axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: '#64748b', fontSize: 10 }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.04)' } } },
    series: [
      { name: '温度', data: history.value.map(d => d.temperature), ...makeStyle('#fbbf24') },
      { name: '功耗', data: history.value.map(d => d.power_usage), ...makeStyle('#38bdf8') },
      { name: 'GPU利用率', data: history.value.map(d => d.gpu_utilization), ...makeStyle('#818cf8') },
      { name: '显存利用率', data: history.value.map(d => d.memory_utilization), ...makeStyle('#34d399') },
    ],
    animation: false,
  }
})

const fmtMem = (bytes) => ((bytes || 0) / 1073741824).toFixed(1)

onMounted(() => loadHistory(1))
</script>

<template>
  <div class="gpu-detail">
    <div class="detail-header">
      <button class="btn-tech" @click="router.push('/')">← 返回大屏</button>
      <h2 style="font-size: 1.125rem; font-weight: 600">
        <span style="color: var(--accent-primary)">GPU {{ gpuIndex }}</span>
        <span style="color: var(--text-muted); margin-left: 8px; font-size: 0.875rem">{{ gpu.name }}</span>
      </h2>
    </div>

    <!-- 实时指标 -->
    <div class="detail-stats">
      <div class="dstat tech-card">
        <div class="dstat__label">温度</div>
        <div class="dstat__value stat-value" style="font-size: 2rem">{{ gpu.temperature || '--' }}<span style="font-size: 0.875rem; color: var(--text-muted)">°C</span></div>
      </div>
      <div class="dstat tech-card">
        <div class="dstat__label">功耗</div>
        <div class="dstat__value stat-value" style="font-size: 2rem">{{ (gpu.power_usage || 0).toFixed(0) }}<span style="font-size: 0.875rem; color: var(--text-muted)">W</span></div>
      </div>
      <div class="dstat tech-card">
        <div class="dstat__label">GPU利用率</div>
        <div class="dstat__value stat-value" style="font-size: 2rem">{{ gpu.gpu_utilization || 0 }}<span style="font-size: 0.875rem; color: var(--text-muted)">%</span></div>
      </div>
      <div class="dstat tech-card">
        <div class="dstat__label">显存</div>
        <div class="dstat__value stat-value" style="font-size: 2rem">{{ fmtMem(gpu.memory_used) }}<span style="font-size: 0.875rem; color: var(--text-muted)">/ {{ fmtMem(gpu.memory_total) }} GB</span></div>
      </div>
      <div class="dstat tech-card">
        <div class="dstat__label">风扇</div>
        <div class="dstat__value stat-value" style="font-size: 2rem">{{ gpu.fan_speed || 0 }}<span style="font-size: 0.875rem; color: var(--text-muted)">%</span></div>
      </div>
      <div class="dstat tech-card">
        <div class="dstat__label">功耗限制</div>
        <div class="dstat__value stat-value" style="font-size: 2rem">{{ (gpu.power_limit || 0).toFixed(0) }}<span style="font-size: 0.875rem; color: var(--text-muted)">W</span></div>
      </div>
    </div>

    <!-- 历史趋势 -->
    <div class="history-panel tech-card" style="padding: 20px; margin-top: 16px">
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px">
        <div class="section-title">历史趋势</div>
        <div style="display: flex; gap: 6px">
          <button
            v-for="r in ranges" :key="r.value"
            class="btn-tech"
            :class="{ 'btn-tech--primary': selectedRange === r.value }"
            @click="loadHistory(r.value)"
          >{{ r.label }}</button>
        </div>
      </div>
      <div style="height: 360px; position: relative">
        <div v-if="loading" style="position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; color: var(--text-muted)">加载中...</div>
        <v-chart v-else :option="chartOption" autoresize style="width: 100%; height: 100%" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.gpu-detail { max-width: 1400px; margin: 0 auto; }
.detail-header { display: flex; align-items: center; gap: 16px; margin-bottom: 20px; }
.detail-stats { display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; }
.dstat { padding: 18px; text-align: center; }
.dstat__label { font-size: 0.75rem; color: var(--text-muted); margin-bottom: 6px; }
</style>

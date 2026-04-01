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

const processedHistory = computed(() => ({
  times: history.value.map((point) => new Date(point.timestamp * 1000)),
  temperatures: history.value.map((point) => point.temperature),
  powerUsage: history.value.map((point) => point.power_usage),
  gpuUtilization: history.value.map((point) => point.gpu_utilization),
  memoryUtilization: history.value.map((point) => point.memory_utilization),
}))

const chartOption = computed(() => {
  const makeStyle = (color) => ({
    type: 'line', smooth: true, symbol: 'none',
    lineStyle: { width: 1.5, color },
    areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: color + '25' }, { offset: 1, color: color + '05' }] } },
  })
  const processed = processedHistory.value

  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(248,245,240,0.97)',
      borderColor: 'rgba(58,95,75,0.2)',
      textStyle: { color: '#2C2C2C', fontSize: 12 },
    },
    legend: {
      data: ['温度', '功耗', 'GPU利用率', '显存利用率'],
      textStyle: { color: '#666666', fontSize: 11 },
      top: 0,
    },
    grid: { left: 50, right: 20, top: 36, bottom: 60 },
    dataZoom: [{ type: 'inside' }, { type: 'slider', height: 20, bottom: 8, borderColor: 'transparent', backgroundColor: 'rgba(255,255,255,0.04)', fillerColor: 'rgba(58,95,75,0.1)', handleStyle: { color: '#3A5F4B' }, textStyle: { color: '#999999' } }],
    xAxis: { type: 'category', data: processed.times, axisLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } }, axisTick: { show: false }, axisLabel: { color: '#999999', fontSize: 10, formatter: (v) => new Date(v).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) } },
    yAxis: { type: 'value', axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: '#999999', fontSize: 10 }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.04)' } } },
    series: [
      { name: '温度', data: processed.temperatures, ...makeStyle('#B8860B') },
      { name: '功耗', data: processed.powerUsage, ...makeStyle('#3A5F4B') },
      { name: 'GPU利用率', data: processed.gpuUtilization, ...makeStyle('#5B4B8C') },
      { name: '显存利用率', data: processed.memoryUtilization, ...makeStyle('#2E8B57') },
    ],
    animation: false,
  }
})

const fmtMem = (bytes) => ((bytes || 0) / 1073741824).toFixed(1)

onMounted(() => loadHistory(1))
</script>

<template>
  <div class="gpu-detail ink-page-shell">
    <section class="ink-page-head tech-card">
      <div class="ink-page-head__body">
        <div class="ink-page-head__eyebrow">单卡画像 · 历史趋势 · 实时指标</div>
        <h2 class="ink-page-head__title">GPU {{ gpuIndex }} 的呼吸、脉络与负载起伏</h2>
        <p class="ink-page-head__desc">
          {{ gpu.name || '当前单卡信息正在加载中。' }}
          这里以单卡为单位观察温度、功耗、利用率和显存变化，帮助你定位热点、异常和限功后的响应。
        </p>
      </div>
      <div class="ink-page-head__side">
        <button class="btn-tech" @click="router.push('/')">返回总览</button>
        <div class="ink-inline-meta">
          <span class="status-badge status-badge--warning">温度 {{ gpu.temperature || '--' }}°C</span>
          <span class="status-badge status-badge--ok">功耗 {{ (gpu.power_usage || 0).toFixed(0) }}W</span>
        </div>
      </div>
    </section>

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
.gpu-detail { max-width: 1460px; margin: 0 auto; }
.detail-stats { display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; }
.dstat { padding: 18px; text-align: center; }
.dstat__label { font-size: 0.75rem; color: var(--text-muted); margin-bottom: 6px; }

@media (max-width: 1180px) {
  .detail-stats {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 720px) {
  .detail-stats {
    grid-template-columns: 1fr;
  }
}
</style>

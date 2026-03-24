<script setup>
/**
 * 功耗趋势图 - 实时滚动的多GPU功耗折线图
 */
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent])

const props = defineProps({ gpus: { type: Array, default: () => [] } })

const GPU_COLORS = ['#38bdf8', '#818cf8', '#34d399', '#fbbf24']
const MAX_POINTS = 60

// 历史数据缓存（每张GPU保留60个点）
const history = ref({})

watch(() => props.gpus, (gpus) => {
  gpus.forEach(gpu => {
    if (!history.value[gpu.index]) history.value[gpu.index] = []
    const arr = history.value[gpu.index]
    arr.push({ time: new Date(), value: gpu.power_usage })
    if (arr.length > MAX_POINTS) arr.shift()
  })
}, { deep: true })

const option = ref({})

function updateChart() {
  const series = []
  const legend = []

  Object.entries(history.value).forEach(([idx, data]) => {
    const name = `GPU ${idx}`
    legend.push(name)
    series.push({
      name,
      type: 'line',
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 2, color: GPU_COLORS[idx] || '#38bdf8' },
      areaStyle: {
        color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: (GPU_COLORS[idx] || '#38bdf8') + '30' },
            { offset: 1, color: (GPU_COLORS[idx] || '#38bdf8') + '05' },
          ],
        },
      },
      data: data.map(d => [d.time, d.value]),
    })
  })

  option.value = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(17, 24, 39, 0.9)',
      borderColor: 'rgba(56, 189, 248, 0.2)',
      textStyle: { color: '#f1f5f9', fontSize: 12 },
      formatter: (params) => {
        let s = `<div style="font-size:11px;color:#64748b;margin-bottom:4px">${new Date(params[0].value[0]).toLocaleTimeString('zh-CN')}</div>`
        params.forEach(p => {
          s += `<div style="display:flex;align-items:center;gap:6px;margin:2px 0">
            <span style="width:8px;height:8px;border-radius:50%;background:${p.color}"></span>
            ${p.seriesName}: <b>${p.value[1].toFixed(1)}W</b></div>`
        })
        return s
      },
    },
    legend: {
      data: legend,
      textStyle: { color: '#94a3b8', fontSize: 11 },
      top: 0,
      right: 0,
      itemWidth: 12,
      itemHeight: 3,
    },
    grid: { left: 45, right: 12, top: 28, bottom: 24 },
    xAxis: {
      type: 'time',
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
      axisTick: { show: false },
      axisLabel: { color: '#64748b', fontSize: 10 },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      name: 'W',
      nameTextStyle: { color: '#64748b', fontSize: 10 },
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#64748b', fontSize: 10 },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.04)' } },
    },
    series,
    animation: false,
  }
}

let timer
onMounted(() => { timer = setInterval(updateChart, 1000) })
onUnmounted(() => clearInterval(timer))
</script>

<template>
  <v-chart :option="option" autoresize style="width: 100%; height: 100%" />
</template>

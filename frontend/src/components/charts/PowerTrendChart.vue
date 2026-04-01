<script setup>
/**
 * 功耗趋势图 - 实时滚动的多GPU功耗折线图
 */
import { ref, watch } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent])

const props = defineProps({ gpus: { type: Array, default: () => [] } })

const GPU_COLORS = ['#3A5F4B', '#5B4B8C', '#2E8B57', '#B8860B']
const MAX_POINTS = 60

// 历史数据缓存（每张GPU保留60个点）
const history = ref({})
const option = ref({
  backgroundColor: 'transparent',
  tooltip: {
    trigger: 'axis',
    backgroundColor: 'rgba(248, 245, 240, 0.97)',
    borderColor: 'rgba(58, 95, 75, 0.2)',
    textStyle: { color: '#2C2C2C', fontSize: 12 },
    formatter: (params) => {
      if (!params.length) return ''
      let output = `<div style="font-size:11px;color:#999999;margin-bottom:4px">${new Date(params[0].value[0]).toLocaleTimeString('zh-CN')}</div>`
      params.forEach((item) => {
        output += `<div style="display:flex;align-items:center;gap:6px;margin:2px 0">
          <span style="width:8px;height:8px;border-radius:50%;background:${item.color}"></span>
          ${item.seriesName}: <b>${item.value[1].toFixed(1)}W</b></div>`
      })
      return output
    },
  },
  legend: {
    data: [],
    textStyle: { color: '#666666', fontSize: 11 },
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
    axisLabel: { color: '#999999', fontSize: 10 },
    splitLine: { show: false },
  },
  yAxis: {
    type: 'value',
    name: 'W',
    nameTextStyle: { color: '#999999', fontSize: 10 },
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { color: '#999999', fontSize: 10 },
    splitLine: { lineStyle: { color: 'rgba(255,255,255,0.04)' } },
  },
  series: [],
  animation: false,
})

function appendHistory(gpus) {
  gpus.forEach((gpu) => {
    if (!history.value[gpu.index]) history.value[gpu.index] = []
    const points = history.value[gpu.index]
    points.push({ time: new Date(), value: gpu.power_usage })
    if (points.length > MAX_POINTS) points.shift()
  })
}

function updateChartOption() {
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
      lineStyle: { width: 2, color: GPU_COLORS[idx] || '#3A5F4B' },
      areaStyle: {
        color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: (GPU_COLORS[idx] || '#3A5F4B') + '30' },
            { offset: 1, color: (GPU_COLORS[idx] || '#3A5F4B') + '05' },
          ],
        },
      },
      data: data.map(d => [d.time, d.value]),
    })
  })

  option.value = {
    ...option.value,
    legend: {
      ...option.value.legend,
      data: legend,
    },
    series,
  }
}

watch(
  () => props.gpus,
  (gpus) => {
    appendHistory(gpus || [])
    updateChartOption()
  },
  { immediate: true },
)
</script>

<template>
  <v-chart :option="option" autoresize style="width: 100%; height: 100%" />
</template>

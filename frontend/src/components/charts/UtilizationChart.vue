<script setup>
/**
 * 利用率分布图 - 多GPU利用率雷达图/柱状图
 */
import { computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import VChart from 'vue-echarts'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent])

const props = defineProps({ gpus: { type: Array, default: () => [] } })

const GPU_COLORS = ['#38bdf8', '#818cf8', '#34d399', '#fbbf24']

const option = computed(() => ({
  backgroundColor: 'transparent',
  tooltip: {
    trigger: 'axis',
    backgroundColor: 'rgba(17, 24, 39, 0.9)',
    borderColor: 'rgba(56, 189, 248, 0.2)',
    textStyle: { color: '#f1f5f9', fontSize: 12 },
  },
  grid: { left: 45, right: 12, top: 12, bottom: 50 },
  xAxis: {
    type: 'category',
    data: props.gpus.map(g => `GPU ${g.index}`),
    axisLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
    axisTick: { show: false },
    axisLabel: { color: '#94a3b8', fontSize: 11 },
  },
  yAxis: [
    {
      type: 'value', name: '%', max: 100,
      nameTextStyle: { color: '#64748b', fontSize: 10 },
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#64748b', fontSize: 10 },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.04)' } },
    },
  ],
  series: [
    {
      name: 'GPU利用率',
      type: 'bar',
      barWidth: 28,
      itemStyle: {
        borderRadius: [4, 4, 0, 0],
        color: (params) => ({
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: GPU_COLORS[params.dataIndex] || '#38bdf8' },
            { offset: 1, color: (GPU_COLORS[params.dataIndex] || '#38bdf8') + '40' },
          ],
        }),
      },
      data: props.gpus.map(g => g.gpu_utilization),
    },
    {
      name: '显存利用率',
      type: 'bar',
      barWidth: 28,
      itemStyle: {
        borderRadius: [4, 4, 0, 0],
        color: 'rgba(148, 163, 184, 0.2)',
      },
      data: props.gpus.map(g => g.memory_utilization),
    },
  ],
  animation: true,
  animationDuration: 600,
}))
</script>

<template>
  <v-chart :option="option" autoresize style="width: 100%; height: 100%" />
</template>

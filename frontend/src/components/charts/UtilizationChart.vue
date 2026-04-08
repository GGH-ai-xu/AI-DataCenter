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

const GPU_COLORS = ['#00D4AA', '#0EA5E9', '#38BDF8', '#F59E0B']

const option = computed(() => ({
  backgroundColor: 'transparent',
  tooltip: {
    trigger: 'axis',
    backgroundColor: 'rgba(17, 21, 32, 0.96)',
    borderColor: 'rgba(0, 212, 170, 0.18)',
    textStyle: { color: '#E8ECF4', fontSize: 12 },
  },
  grid: { left: 45, right: 12, top: 12, bottom: 50 },
  xAxis: {
    type: 'category',
    data: props.gpus.map(g => `GPU ${g.index}`),
    axisLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
    axisTick: { show: false },
    axisLabel: { color: '#A0AABE', fontSize: 11 },
  },
  yAxis: [
    {
      type: 'value', name: '%', max: 100,
      nameTextStyle: { color: '#6B7A94', fontSize: 10 },
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#6B7A94', fontSize: 10 },
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
            { offset: 0, color: GPU_COLORS[params.dataIndex] || '#00D4AA' },
            { offset: 1, color: (GPU_COLORS[params.dataIndex] || '#00D4AA') + '40' },
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

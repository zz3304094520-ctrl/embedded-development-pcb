<script setup lang="ts">
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { init, use, type ECharts, type EChartsCoreOption } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { nextTick, onBeforeUnmount, onMounted, useTemplateRef, watch } from 'vue'
import type { SensorReading } from '@/types'

use([LineChart, BarChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer])

const props = defineProps<{ readings: SensorReading[]; compact?: boolean }>()
const chartEl = useTemplateRef<HTMLDivElement>('chart')
let chart: ECharts | null = null
let observer: ResizeObserver | null = null

const colors = ['#167a5c', '#c78015', '#2d6f9d', '#a54c3c', '#6f5f9a']
function option(): EChartsCoreOption {
  const metrics = [...new Set(props.readings.map((item) => item.metric))].slice(0, 5)
  const timeline = [...new Set(props.readings.map((item) => item.recorded_at))].sort().slice(-30)
  return {
    animationDuration: 220,
    color: colors,
    tooltip: { trigger: 'axis', confine: true },
    legend: { top: 0, left: 0, textStyle: { color: '#52635e' } },
    grid: { left: 16, right: 16, top: 42, bottom: 14, containLabel: true },
    xAxis: { type: 'category', data: timeline.map((time) => new Intl.DateTimeFormat('zh-CN', { hour: '2-digit', minute: '2-digit' }).format(new Date(time))), axisLine: { lineStyle: { color: '#d8e1dd' } }, axisLabel: { color: '#6c7b76' } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: '#edf1ef' } }, axisLabel: { color: '#6c7b76' } },
    series: metrics.map((metric) => ({ name: metric, type: 'line', smooth: 0.28, showSymbol: false, connectNulls: true, data: timeline.map((time) => props.readings.find((item) => item.metric === metric && item.recorded_at === time)?.value ?? null), lineStyle: { width: 2 }, areaStyle: { opacity: 0.04 } })),
  }
}

function render() { if (chart) chart.setOption(option(), true) }
onMounted(async () => { await nextTick(); if (!chartEl.value) return; chart = init(chartEl.value); render(); observer = new ResizeObserver(() => chart?.resize()); observer.observe(chartEl.value) })
watch(() => props.readings, render, { deep: true })
onBeforeUnmount(() => { observer?.disconnect(); chart?.dispose() })
</script>

<template>
  <div v-if="readings.length" ref="chart" class="trend-chart" :class="{ 'trend-chart--compact': compact }" role="img" aria-label="传感器数据趋势图"></div>
  <el-empty v-else description="暂无可绘制的传感器数据" :image-size="72" />
</template>

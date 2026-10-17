<script setup lang="ts">
import { formatDateTime, formatNumber } from '../../format'
import { labelMetric, labelUnit } from '../../labels'
import type { SensorReading } from '../../types'

defineProps<{
  readings: SensorReading[]
}>()
</script>

<template>
  <article class="panel panel--wide js-entrance">
    <div class="section-heading">
      <div>
        <span class="panel__label">最新数据</span>
        <h2>传感器记录</h2>
      </div>
    </div>
    <div v-if="readings.length === 0" class="empty-state">
      <strong>暂无记录</strong>
      <p>上报数据后可以在这里核对最近的传感器读数。</p>
    </div>
    <div v-else class="reading-table" role="table" aria-label="最新传感器记录">
      <div role="row" class="reading-table__head">
        <span role="columnheader">指标</span>
        <span role="columnheader">数值</span>
        <span role="columnheader">质量</span>
        <span role="columnheader">时间</span>
      </div>
      <div v-for="reading in readings" :key="reading.id" role="row" class="reading-table__row">
        <span role="cell">{{ labelMetric(reading.metric) }}</span>
        <strong role="cell">{{ formatNumber(reading.value) }} {{ labelUnit(reading.unit) }}</strong>
        <span role="cell">{{ reading.quality }}</span>
        <span role="cell">{{ formatDateTime(reading.recorded_at) }}</span>
      </div>
    </div>
  </article>
</template>

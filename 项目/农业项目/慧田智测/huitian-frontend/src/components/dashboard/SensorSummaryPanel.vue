<script setup lang="ts">
import { computed } from 'vue'
import SensorDeviceGroup from './SensorDeviceGroup.vue'
import type { Device, SensorReading } from '../../types'

type SensorGroup = {
  type: 'soil_sensor' | 'weather_station' | 'wind_speed_sensor' | 'wind_direction_sensor'
  title: string
  accent: 'soil' | 'weather'
  device: Device | null
  readings: SensorReading[]
}

const props = defineProps<{
  devices: Device[]
  readings: SensorReading[]
}>()

const sensorGroups = computed<SensorGroup[]>(() =>
  [
    { type: 'soil_sensor' as const, title: '土壤多参数传感器', accent: 'soil' as const },
    { type: 'weather_station' as const, title: '气象环境传感器', accent: 'weather' as const },
    { type: 'wind_speed_sensor' as const, title: '三杯式风速传感器', accent: 'weather' as const },
    { type: 'wind_direction_sensor' as const, title: '八方位风向传感器', accent: 'weather' as const },
  ].map((group) => {
    const device = props.devices.find((item) => item.device_type === group.type) ?? null
    return {
      ...group,
      device,
      readings: device ? props.readings.filter((reading) => reading.device_id === device.id) : [],
    }
  }),
)
</script>

<template>
  <article class="panel panel--wide monitoring-panel js-entrance">
    <div class="section-heading">
      <div>
        <span class="panel__label">FIELD DATA</span>
        <h2>实时传感器</h2>
      </div>
      <span class="monitoring-panel__hint">数据来自 Jetson 现场采集</span>
    </div>

    <div class="monitoring-groups">
      <SensorDeviceGroup
        v-for="group in sensorGroups"
        :key="group.type"
        :title="group.title"
        :accent="group.accent"
        :device="group.device"
        :readings="group.readings"
      />
    </div>
  </article>
</template>

<style scoped>
.monitoring-panel__hint {
  color: var(--muted);
  font-size: 0.72rem;
}

.monitoring-groups {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--space-4);
}

@media (max-width: 520px) {
  .monitoring-panel__hint {
    display: none;
  }
}
</style>

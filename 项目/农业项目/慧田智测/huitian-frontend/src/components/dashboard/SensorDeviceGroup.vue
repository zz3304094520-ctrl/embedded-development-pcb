<script setup lang="ts">
import { computed } from 'vue'
import { PhCloudSun, PhPlant } from '@phosphor-icons/vue'
import { formatDateTime, formatNumber, relativeStatusTime } from '../../format'
import { labelMetric, labelReadingQuality, labelUnit } from '../../labels'
import type { Device, SensorReading } from '../../types'

type SensorAccent = 'soil' | 'weather'

const props = defineProps<{
  title: string
  accent: SensorAccent
  device: Device | null
  readings: SensorReading[]
}>()

const metricOrder: Record<SensorAccent, string[]> = {
  soil: [
    'soil_moisture',
    'soil_temperature',
    'soil_ec',
    'soil_ph',
    'soil_nitrogen',
    'soil_phosphorus',
    'soil_potassium',
  ],
  weather: ['air_temperature', 'air_humidity', 'illumination', 'rainfall', 'wind_speed', 'wind_direction'],
}

const orderedReadings = computed(() => {
  const order = metricOrder[props.accent]
  return [...props.readings].sort((left, right) => {
    const leftIndex = order.indexOf(left.metric)
    const rightIndex = order.indexOf(right.metric)
    return (leftIndex === -1 ? order.length : leftIndex) - (rightIndex === -1 ? order.length : rightIndex)
  })
})

const statusLabel = computed(() => {
  if (!props.device) return '未配置'
  return props.device.is_online ? '在线' : '离线'
})

const emptyState = computed(() => {
  if (!props.device) {
    return {
      title: '设备尚未配置',
      message: '后端配置设备后，这里会自动显示实时读数。',
    }
  }
  if (props.device.is_online) {
    return {
      title: '已连接，等待首次采样',
      message: 'Jetson 完成第一轮采集后会自动更新。',
    }
  }
  return {
    title: '传感器离线',
    message: '等待传感器接入 Jetson，历史读数不会被伪造。',
  }
})

function readingDigits(metric: string): number {
  if (metric === 'soil_ph') return 2
  if (metric === 'wind_direction') return 0
  return 1
}

function qualityTone(quality: string): 'good' | 'suspect' | 'bad' {
  if (quality === 'good' || quality === 'bad') return quality
  return 'suspect'
}
</script>

<template>
  <section class="sensor-device" :class="`sensor-device--${props.accent}`">
    <header class="sensor-device__heading">
      <span class="sensor-device__icon" aria-hidden="true">
        <PhPlant v-if="props.accent === 'soil'" :size="21" weight="duotone" />
        <PhCloudSun v-else :size="21" weight="duotone" />
      </span>
      <span class="sensor-device__identity">
        <strong>{{ props.title }}</strong>
        <small>{{ props.device?.name ?? '等待设备配置' }}</small>
      </span>
      <span
        class="sensor-device__status"
        :class="{ 'sensor-device__status--online': props.device?.is_online }"
      >
        <span aria-hidden="true"></span>
        {{ statusLabel }}
      </span>
    </header>

    <div v-if="props.device" class="sensor-device__meta">
      <span>{{ props.device.device_code }}</span>
      <span>最后在线：{{ relativeStatusTime(props.device.last_seen_at) }}</span>
    </div>

    <div v-if="orderedReadings.length === 0" class="sensor-device__empty">
      <strong>{{ emptyState.title }}</strong>
      <p>{{ emptyState.message }}</p>
    </div>

    <div v-else class="sensor-reading-grid">
      <article
        v-for="reading in orderedReadings"
        :key="`${reading.device_id}:${reading.metric}`"
        class="sensor-reading"
      >
        <div class="sensor-reading__topline">
          <span>{{ labelMetric(reading.metric) }}</span>
          <span
            class="sensor-reading__quality"
            :class="`sensor-reading__quality--${qualityTone(reading.quality)}`"
          >
            {{ labelReadingQuality(reading.quality) }}
          </span>
        </div>
        <strong class="sensor-reading__value">
          {{ formatNumber(reading.value, readingDigits(reading.metric)) }}
          <small>{{ labelUnit(reading.unit) }}</small>
        </strong>
        <small class="sensor-reading__time">采集于 {{ formatDateTime(reading.recorded_at) }}</small>
      </article>
    </div>

    <p v-if="props.device && !props.device.is_online && orderedReadings.length > 0" class="sensor-device__offline-note">
      当前设备离线，以上为最后一次有效采样。
    </p>
  </section>
</template>

<style scoped>
.sensor-device {
  display: grid;
  min-width: 0;
  gap: var(--space-3);
  padding: var(--space-4);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background: oklch(100% 0 0 / 0.045);
}

.sensor-device__heading {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-3);
}

.sensor-device__icon {
  display: grid;
  width: 2.4rem;
  height: 2.4rem;
  place-items: center;
  border-radius: 0.8rem;
}

.sensor-device--soil .sensor-device__icon {
  background: oklch(80% 0.08 145 / 0.18);
  color: var(--primary);
}

.sensor-device--weather .sensor-device__icon {
  background: oklch(80% 0.08 235 / 0.16);
  color: oklch(72% 0.11 235);
}

.sensor-device__identity {
  display: grid;
  min-width: 0;
  gap: 0.18rem;
}

.sensor-device__identity strong {
  color: var(--ink);
  font-size: 0.96rem;
}

.sensor-device__identity small,
.sensor-device__meta,
.sensor-reading__time,
.sensor-device__offline-note {
  color: var(--muted);
}

.sensor-device__identity small {
  overflow: hidden;
  font-size: 0.72rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sensor-device__status {
  display: inline-flex;
  align-items: center;
  gap: 0.38rem;
  padding: 0.3rem 0.58rem;
  border: 1px solid var(--line);
  border-radius: 999px;
  color: var(--muted);
  font-size: 0.68rem;
  font-weight: 750;
}

.sensor-device__status > span {
  width: 0.42rem;
  height: 0.42rem;
  border-radius: 50%;
  background: var(--muted-2);
}

.sensor-device__status--online {
  border-color: oklch(76% 0.08 150 / 0.55);
  color: var(--success);
}

.sensor-device__status--online > span {
  background: var(--success);
  box-shadow: 0 0 0 3px oklch(70% 0.1 152 / 0.16);
}

.sensor-device__meta {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: var(--space-2);
  padding-bottom: var(--space-2);
  border-bottom: 1px solid var(--line);
  font-size: 0.68rem;
}

.sensor-reading-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-3);
}

.sensor-reading {
  display: grid;
  min-width: 0;
  gap: var(--space-2);
  padding: var(--space-3);
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  background: oklch(100% 0 0 / 0.055);
}

.sensor-reading__topline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  color: var(--muted);
  font-size: 0.72rem;
}

.sensor-reading__quality {
  flex: 0 0 auto;
  padding: 0.18rem 0.4rem;
  border-radius: 999px;
  background: var(--surface-2);
  font-size: 0.62rem;
  font-weight: 750;
}

.sensor-reading__quality--good {
  background: oklch(80% 0.08 150 / 0.16);
  color: var(--success);
}

.sensor-reading__quality--suspect {
  background: oklch(80% 0.09 85 / 0.16);
  color: var(--warning);
}

.sensor-reading__quality--bad {
  background: oklch(70% 0.12 28 / 0.14);
  color: var(--danger);
}

.sensor-reading__value {
  color: var(--ink);
  font-size: clamp(1.3rem, 2.4vw, 1.7rem);
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.03em;
}

.sensor-reading__value small {
  color: var(--muted);
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0;
}

.sensor-reading__time {
  font-size: 0.64rem;
}

.sensor-device__empty {
  display: grid;
  gap: var(--space-2);
  min-height: 7.4rem;
  align-content: center;
  padding: var(--space-4);
  border: 1px dashed var(--line-strong);
  border-radius: var(--radius-md);
  color: var(--ink);
  text-align: center;
}

.sensor-device__empty p,
.sensor-device__offline-note {
  margin: 0;
  font-size: 0.7rem;
  line-height: 1.55;
}

.sensor-device__offline-note {
  padding-top: var(--space-2);
  border-top: 1px solid var(--line);
}

@media (max-width: 560px) {
  .sensor-device {
    padding: var(--space-3);
  }

  .sensor-device__heading {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .sensor-device__status {
    grid-column: 2;
    width: fit-content;
  }
}
</style>

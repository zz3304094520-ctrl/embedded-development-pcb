<script setup lang="ts">
import {
  PhArrowRight,
  PhCaretDown,
  PhFolderOpen,
  PhMapTrifold,
  PhPlant,
  PhThermometerSimple,
  PhVideoCamera,
} from '@phosphor-icons/vue'
import { computed } from 'vue'
import { weatherCodeLabel, type CurrentWeather } from '../../composables/useHangzhouWeather'
import { formatDateTime, formatNumber } from '../../format'
import { labelMetric, labelUnit } from '../../labels'
import type { Farm, HealthResponse, Plot, SensorReading } from '../../types'

const props = defineProps<{
  health: HealthResponse | null
  selectedFarm: Farm | null
  selectedPlot: Plot | null
  farms: Farm[]
  farmPlots: Plot[]
  onlineDeviceCount: number
  deviceCount: number
  temperatureReading: SensorReading | null
  currentWeather: CurrentWeather | null
  weatherLoading: boolean
  weatherError: string | null
}>()

const farmId = defineModel<number | null>('farmId', { required: true })
const plotId = defineModel<number | null>('plotId', { required: true })

const emit = defineEmits<{
  farmChange: []
  plotChange: []
}>()

const farmArea = computed(() => props.farmPlots.reduce((total, plot) => total + plot.area, 0))
const isHealthy = computed(() => props.health?.status === 'ok')
const displayedTemperature = computed(() => props.currentWeather?.temperature ?? props.temperatureReading?.value ?? null)
const displayedTemperatureUnit = computed(() => (props.currentWeather ? '°C' : labelUnit(props.temperatureReading?.unit ?? '')))
const displayedTemperatureTime = computed(
  () => props.currentWeather?.observedAt ?? props.temperatureReading?.recorded_at,
)
const temperatureDetail = computed(() => {
  if (props.currentWeather) {
    return `杭州 · ${weatherCodeLabel(props.currentWeather.weatherCode)} · 湿度 ${formatNumber(props.currentWeather.humidity, 0)}%`
  }
  if (props.temperatureReading) return labelMetric(props.temperatureReading.metric)
  if (props.weatherLoading) return '正在获取杭州天气'
  return props.weatherError ? '天气暂不可用' : '等待温度数据'
})
const temperatureSourceLabel = computed(() => {
  if (props.currentWeather) return 'Open-Meteo 实况'
  if (props.temperatureReading) return '现场采样'
  return props.weatherLoading ? '正在连接' : '等待数据'
})

function handleFarmChange(event: Event): void {
  const value = (event.target as HTMLSelectElement).value
  farmId.value = value ? Number(value) : null
  emit('farmChange')
}

function handlePlotChange(event: Event): void {
  const value = (event.target as HTMLSelectElement).value
  plotId.value = value ? Number(value) : null
  emit('plotChange')
}
</script>

<template>
  <section id="overview" class="overview-home js-entrance" aria-labelledby="overview-title">
    <header class="overview-header">
      <div>
        <span class="overview-kicker">TODAY</span>
        <h2 id="overview-title">农场总览</h2>
        <p>{{ props.selectedFarm?.name ?? '请选择需要查看的农场' }}</p>
      </div>
      <span class="health-badge" :class="{ 'health-badge--warning': !isHealthy }">
        <span class="health-badge__dot" aria-hidden="true"></span>
        {{ isHealthy ? '服务在线' : '等待连接' }}
      </span>
    </header>

    <div class="primary-grid">
      <article class="metric-card metric-card--farm">
        <div class="metric-card__topline">
          <span class="metric-card__icon" aria-hidden="true">
            <PhMapTrifold :size="24" weight="duotone" />
          </span>
          <span>农场面积</span>
        </div>
        <div class="metric-card__value">
          <strong>{{ formatNumber(farmArea) }}</strong>
          <span>亩</span>
        </div>
        <div class="metric-card__footer">
          <div>
            <small>当前地块</small>
            <b>{{ props.selectedPlot?.name ?? '暂无地块' }}</b>
          </div>
          <span>{{ props.farmPlots.length }} 个地块</span>
        </div>
      </article>

      <article class="metric-card metric-card--temperature">
        <div class="metric-card__topline">
          <span class="metric-card__icon" aria-hidden="true">
            <PhThermometerSimple :size="24" weight="duotone" />
          </span>
          <span>杭州实时天气</span>
        </div>
        <div class="metric-card__value">
          <template v-if="displayedTemperature !== null">
            <strong>{{ formatNumber(displayedTemperature) }}</strong>
            <span>{{ displayedTemperatureUnit }}</span>
          </template>
          <strong v-else>--</strong>
        </div>
        <div class="metric-card__footer">
          <div>
            <small>{{ temperatureDetail }}</small>
            <b>{{ formatDateTime(displayedTemperatureTime) }}</b>
          </div>
          <span
            class="live-badge"
            :class="{ 'live-badge--offline': !props.currentWeather && !props.weatherLoading }"
            :title="props.weatherError || '天气数据来自 Open-Meteo'"
          >
            <span aria-hidden="true"></span>{{ temperatureSourceLabel }}
          </span>
        </div>
      </article>
    </div>

    <section class="quick-section" aria-labelledby="quick-title">
      <div class="quick-section__heading">
        <div>
          <span>QUICK ACCESS</span>
          <h3 id="quick-title">快捷服务</h3>
        </div>
        <p>高频功能，一步直达</p>
      </div>

      <div class="quick-grid">
        <a class="quick-card quick-card--diagnosis" href="#diagnosis">
          <span class="quick-card__icon" aria-hidden="true">
            <PhPlant :size="26" weight="duotone" />
          </span>
          <span class="quick-card__content">
            <strong>作物智诊</strong>
            <small>病害识别与处方</small>
          </span>
          <PhArrowRight class="quick-card__arrow" :size="18" weight="bold" aria-hidden="true" />
        </a>

        <a class="quick-card quick-card--monitor" href="#camera">
          <span class="quick-card__icon" aria-hidden="true">
            <PhVideoCamera :size="26" weight="duotone" />
          </span>
          <span class="quick-card__content">
            <strong>AI监控</strong>
            <small>{{ props.onlineDeviceCount }} / {{ props.deviceCount }} 台设备在线</small>
          </span>
          <PhArrowRight class="quick-card__arrow" :size="18" weight="bold" aria-hidden="true" />
        </a>

        <details class="quick-card archive-card">
          <summary>
            <span class="quick-card__icon" aria-hidden="true">
              <PhFolderOpen :size="26" weight="duotone" />
            </span>
            <span class="quick-card__content">
              <strong>农场档案</strong>
              <small>{{ props.selectedFarm?.location || '选择农场与地块' }}</small>
            </span>
            <PhCaretDown class="archive-card__caret" :size="18" weight="bold" aria-hidden="true" />
          </summary>

          <div class="archive-card__selectors">
            <label>
              <span>农场</span>
              <select :value="farmId ?? ''" name="farm_id" autocomplete="off" @change="handleFarmChange">
                <option v-if="props.farms.length === 0" value="">暂无农场</option>
                <option v-for="farm in props.farms" :key="farm.id" :value="farm.id">
                  {{ farm.name }}
                </option>
              </select>
            </label>
            <label>
              <span>地块</span>
              <select :value="plotId ?? ''" name="plot_id" autocomplete="off" @change="handlePlotChange">
                <option v-if="props.farmPlots.length === 0" value="">暂无地块</option>
                <option v-for="plot in props.farmPlots" :key="plot.id" :value="plot.id">
                  {{ plot.name }}
                </option>
              </select>
            </label>
          </div>
        </details>
      </div>
    </section>
  </section>
</template>

<style scoped>
.overview-home {
  display: grid;
  gap: 0.7rem;
  color: #17221d;
}

.overview-header,
.quick-section__heading {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  clip-path: inset(50%);
  white-space: nowrap;
}

.overview-header h2,
.quick-section__heading h3 {
  margin: 0.18rem 0 0;
  color: #14221b;
  font-size: 1.05rem;
  line-height: 1.08;
  letter-spacing: -0.02em;
}

.overview-header p,
.quick-section__heading p {
  margin: 0.24rem 0 0;
  color: #718077;
  font-size: 0.72rem;
}

.overview-kicker,
.quick-section__heading > div > span {
  color: #58816c;
  font-size: 0.58rem;
  font-weight: 800;
  letter-spacing: 0.12em;
}

.health-badge {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 0.4rem;
  min-height: 1.8rem;
  padding: 0 0.65rem;
  border: 1px solid #cce2d4;
  border-radius: 999px;
  background: #eff8f2;
  color: #246440;
  font-size: 0.66rem;
  font-weight: 700;
}

.health-badge__dot {
  width: 0.38rem;
  height: 0.38rem;
  border-radius: 50%;
  background: #2ca263;
  box-shadow: 0 0 0 3px rgb(44 162 99 / 13%);
}

.health-badge--warning {
  border-color: #ead3c8;
  background: #fff4ef;
  color: #9a4d30;
}

.health-badge--warning .health-badge__dot {
  background: #d25e3e;
  box-shadow: 0 0 0 4px rgb(210 94 62 / 13%);
}

.primary-grid {
  display: grid;
  grid-template-columns: 1.35fr 1fr;
  gap: 0.55rem;
}

.metric-card {
  position: relative;
  display: flex;
  min-height: 7.2rem;
  flex-direction: column;
  justify-content: space-between;
  overflow: hidden;
  padding: 0.85rem;
  border: 1px solid rgb(255 255 255 / 14%);
  border-radius: 1rem;
  color: #fff;
  box-shadow: 0 0.45rem 1.5rem rgb(24 53 40 / 10%);
}

.metric-card--farm {
  background: #174b38;
}

.metric-card--temperature {
  background: #c84943;
}

.metric-card__topline {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.7rem;
  font-weight: 700;
}

.metric-card__icon {
  display: grid;
  width: 1.9rem;
  height: 1.9rem;
  flex: 0 0 auto;
  place-items: center;
  border: 1px solid rgb(255 255 255 / 18%);
  border-radius: 0.6rem;
  background: rgb(255 255 255 / 12%);
}

.metric-card__icon :deep(svg) {
  width: 1rem;
  height: 1rem;
}

.metric-card__value {
  display: flex;
  align-items: baseline;
  gap: 0.35rem;
  margin: 0.55rem 0 0.35rem;
}

.metric-card__value strong {
  font-size: clamp(1.75rem, 4vw, 2.45rem);
  font-weight: 700;
  line-height: 1;
  letter-spacing: -0.055em;
}

.metric-card__value span {
  font-size: 0.7rem;
  font-weight: 700;
  opacity: 0.76;
}

.metric-card__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.55rem;
  padding-top: 0.5rem;
  border-top: 1px solid rgb(255 255 255 / 16%);
}

.metric-card__footer div {
  display: grid;
  gap: 4px;
}

.metric-card__footer small,
.metric-card__footer > span {
  color: rgb(255 255 255 / 70%);
  font-size: 0.6rem;
}

.metric-card__footer b {
  font-size: 0.67rem;
  font-weight: 700;
}

.live-badge {
  display: inline-flex;
  min-height: 1.7rem;
  align-items: center;
  gap: 0.25rem;
  padding: 0 0.55rem;
  border: 1px solid rgb(255 255 255 / 26%);
  border-radius: 999px;
  background: rgb(255 255 255 / 14%);
  color: #fff;
  font-size: 0.58rem;
  font-weight: 700;
}

.live-badge > span {
  width: 0.38rem;
  height: 0.38rem;
  border-radius: 50%;
  background: #bff59e;
  box-shadow: 0 0 0 3px rgb(191 245 158 / 16%);
}

.live-badge--offline > span {
  background: #ffd29d;
  box-shadow: 0 0 0 3px rgb(255 210 157 / 16%);
}

.quick-card:focus-visible,
.archive-card summary:focus-visible,
.archive-card select:focus-visible {
  outline: 3px solid rgb(92 159 119 / 28%);
  outline-offset: 3px;
}

.quick-section {
  display: grid;
  gap: 0.55rem;
}

.quick-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.55rem;
}

.quick-card {
  min-width: 0;
  border: 1px solid #e2e8e3;
  border-radius: 0.9rem;
  background: #fff;
  color: inherit;
  box-shadow: 0 0.35rem 1.1rem rgb(33 58 45 / 6%);
}

.quick-card--diagnosis {
  border-color: #d9ee98;
  background: #e0f3a3;
}

a.quick-card,
.archive-card summary {
  display: flex;
  min-height: 5.65rem;
  align-items: center;
  gap: 0.7rem;
  padding: 0.8rem;
  text-decoration: none;
}

a.quick-card {
  transition: border-color 160ms ease, box-shadow 160ms ease, transform 160ms ease;
}

a.quick-card:hover {
  border-color: #bfd6c7;
  box-shadow: 0 15px 34px rgb(33 58 45 / 11%);
  transform: translateY(-2px);
}

.quick-card__icon {
  display: grid;
  width: 2.2rem;
  height: 2.2rem;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 0.7rem;
  background: #eaf5ed;
  color: #2a7650;
}

.quick-card--diagnosis .quick-card__icon {
  background: #f6ffda;
  color: #43651e;
}

.quick-card--monitor .quick-card__icon {
  background: #e9f0fa;
  color: #426d9c;
}

.quick-card__content {
  display: grid;
  min-width: 0;
  flex: 1;
  gap: 0.2rem;
}

.quick-card__content strong {
  font-size: 0.8rem;
  font-weight: 750;
}

.quick-card__content small {
  overflow: hidden;
  color: #7a887f;
  font-size: 0.62rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.quick-card__arrow,
.archive-card__caret {
  flex: 0 0 auto;
  color: #9aa69f;
}

.archive-card summary {
  cursor: pointer;
  list-style: none;
}

.archive-card summary::-webkit-details-marker {
  display: none;
}

.archive-card__caret {
  transition: transform 180ms ease;
}

.archive-card[open] {
  grid-column: 1 / -1;
}

.archive-card[open] .archive-card__caret {
  transform: rotate(180deg);
}

.archive-card__selectors {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.6rem;
  padding: 0 0.8rem 0.8rem;
}

.archive-card__selectors label {
  display: grid;
  gap: 7px;
}

.archive-card__selectors label > span {
  color: #6b796f;
  font-size: 0.7rem;
  font-weight: 700;
}

.archive-card__selectors select {
  width: 100%;
  min-height: 2.45rem;
  padding: 0 2rem 0 0.65rem;
  border: 1px solid #dce4de;
  border-radius: 12px;
  background-color: #f7faf8;
  color: #233129;
  font: inherit;
  font-size: 0.82rem;
}

@media (max-width: 760px) {
  .overview-home {
    gap: 0.7rem;
  }

  .primary-grid {
    grid-template-columns: 1.15fr 1fr;
  }

  .metric-card {
    min-height: 7.8rem;
    border-radius: 0.9rem;
  }

  .quick-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 9px;
  }

  a.quick-card,
  .archive-card summary {
    min-height: 5.3rem;
    flex-direction: column;
    align-items: flex-start;
    gap: 0.35rem;
    padding: 0.65rem;
  }

  .quick-card__icon {
    width: 2rem;
    height: 2rem;
    border-radius: 0.6rem;
  }

  .quick-card__content small {
    display: none;
  }

  .quick-card__arrow,
  .archive-card__caret {
    position: absolute;
    right: 12px;
    bottom: 13px;
  }

  .quick-card {
    position: relative;
    border-radius: 0.8rem;
  }
}

@media (max-width: 520px) {
  .overview-header,
  .quick-section__heading {
    align-items: flex-start;
  }

  .quick-section__heading > p {
    display: none;
  }

  .health-badge {
    min-height: 1.75rem;
    padding: 0 0.55rem;
  }

  .metric-card__footer {
    align-items: center;
  }

  .archive-card__selectors {
    grid-template-columns: 1fr;
  }

  .metric-card__footer > span,
  .metric-card__footer b,
  .live-badge {
    display: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  a.quick-card,
  .archive-card__caret {
    transition: none;
  }
}
</style>

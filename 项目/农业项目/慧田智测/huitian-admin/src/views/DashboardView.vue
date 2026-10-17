<script setup lang="ts">
import { computed, onMounted, shallowRef } from 'vue'
import { api } from '@/api'
import PageHeader from '@/components/PageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import TrendChart from '@/components/TrendChart.vue'
import { dateTime, deviceTypeName, metricName } from '@/format'
import type { AlertItem, Device, DeviceCommand, Farm, HealthResponse, Plot, SensorReading } from '@/types'

const loading = shallowRef(true)
const error = shallowRef('')
const health = shallowRef<HealthResponse | null>(null)
const farms = shallowRef<Farm[]>([])
const plots = shallowRef<Plot[]>([])
const devices = shallowRef<Device[]>([])
const alerts = shallowRef<AlertItem[]>([])
const commands = shallowRef<DeviceCommand[]>([])
const readings = shallowRef<SensorReading[]>([])

const onlineCount = computed(() => devices.value.filter((item) => item.is_online).length)
const activeAlerts = computed(() => alerts.value.filter((item) => item.status !== 'resolved'))
const latestReadings = computed(() => readings.value.slice(0, 6))
const latestCommands = computed(() => commands.value.slice(0, 5))

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    const [healthData, farmData, plotData, deviceData, alertData, commandData] = await Promise.all([
      api.health(), api.farms(), api.plots(), api.devices(), api.alerts(), api.commands(),
    ])
    health.value = healthData
    farms.value = farmData
    plots.value = plotData
    devices.value = deviceData
    alerts.value = alertData
    commands.value = commandData
    readings.value = plotData[0] ? await api.telemetry({ plotId: plotData[0].id, limit: 80 }) : []
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '加载总览失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <section>
    <PageHeader title="今天需要关注什么" description="先看连接、设备和未解决告警，再进入具体业务页面。" :refreshing="loading" @refresh="load" />
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" class="page-alert" />

    <div v-loading="loading" class="dashboard-stack">
      <div class="system-banner" :class="{ 'system-banner--error': health && health.status !== 'ok' }">
        <div>
          <span class="system-banner__pulse"></span>
          <div>
            <strong>{{ health?.status === 'ok' ? '数据链路运行正常' : '正在检查数据链路' }}</strong>
            <p>FastAPI {{ health?.status || 'unknown' }} · SQLite {{ health?.database || 'unknown' }} · MQTT {{ health?.mqtt || 'unknown' }}</p>
          </div>
        </div>
        <time>最近检查 {{ dateTime(health?.timestamp) }}</time>
      </div>

      <div class="metric-strip">
        <article><span>农场 / 地块</span><strong>{{ farms.length }} <small>/ {{ plots.length }}</small></strong><p>已纳入平台的生产资源</p></article>
        <article><span>在线设备</span><strong>{{ onlineCount }} <small>/ {{ devices.length }}</small></strong><p>{{ devices.length ? `在线率 ${Math.round(onlineCount / devices.length * 100)}%` : '暂无设备' }}</p></article>
        <article :class="{ 'metric-strip__attention': activeAlerts.length }"><span>待处置告警</span><strong>{{ activeAlerts.length }}</strong><p>{{ activeAlerts.length ? '建议立即进入告警中心' : '当前没有活动告警' }}</p></article>
        <article><span>最近命令</span><strong>{{ commands.length }}</strong><p>{{ latestCommands[0] ? `最新：${latestCommands[0].command_type}` : '尚未创建控制命令' }}</p></article>
      </div>

      <div class="dashboard-grid">
        <article class="content-panel content-panel--wide">
          <div class="panel-heading"><div><h3>环境指标趋势</h3><p>默认展示首个地块最近 80 条数据</p></div><RouterLink to="/telemetry">查看全部</RouterLink></div>
          <TrendChart :readings="readings" compact />
        </article>

        <article class="content-panel">
          <div class="panel-heading"><div><h3>活动告警</h3><p>未解决事项按时间展示</p></div><RouterLink to="/alerts">去处置</RouterLink></div>
          <div v-if="activeAlerts.length" class="activity-list">
            <div v-for="item in activeAlerts.slice(0, 5)" :key="item.id">
              <StatusTag :value="item.severity" /><span><strong>{{ item.message }}</strong><small>{{ dateTime(item.created_at) }}</small></span>
            </div>
          </div>
          <el-empty v-else description="当前没有活动告警" :image-size="70" />
        </article>

        <article class="content-panel">
          <div class="panel-heading"><div><h3>设备状态</h3><p>HTTP 设备与边缘节点</p></div><RouterLink to="/resources">设备管理</RouterLink></div>
          <div v-if="devices.length" class="device-brief-list">
            <div v-for="item in devices.slice(0, 6)" :key="item.id">
              <span class="device-avatar">{{ item.name.slice(0, 1) }}</span>
              <span><strong>{{ item.name }}</strong><small>{{ deviceTypeName(item.device_type) }} · {{ item.device_code }}</small></span>
              <StatusTag :value="item.is_online" />
            </div>
          </div>
          <el-empty v-else description="尚未创建设备" :image-size="70" />
        </article>

        <article class="content-panel content-panel--wide">
          <div class="panel-heading"><div><h3>最新传感器读数</h3><p>用于快速确认现场数据是否持续更新</p></div></div>
          <el-table :data="latestReadings" empty-text="暂无传感器数据">
            <el-table-column label="指标" min-width="140"><template #default="{ row }">{{ metricName(row.metric) }}</template></el-table-column>
            <el-table-column label="数值" min-width="120"><template #default="{ row }"><strong class="table-value">{{ row.value }} {{ row.unit }}</strong></template></el-table-column>
            <el-table-column label="质量" width="110"><template #default="{ row }"><StatusTag :value="row.quality" /></template></el-table-column>
            <el-table-column label="采集时间" min-width="160"><template #default="{ row }">{{ dateTime(row.recorded_at) }}</template></el-table-column>
          </el-table>
        </article>
      </div>
    </div>
  </section>
</template>

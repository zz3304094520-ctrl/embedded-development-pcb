<script setup lang="ts">
import { computed, onMounted, shallowRef, watch } from 'vue'
import { api } from '@/api'
import PageHeader from '@/components/PageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import TrendChart from '@/components/TrendChart.vue'
import { dateTime, metricName } from '@/format'
import type { Device, Plot, SensorReading } from '@/types'

const loading = shallowRef(false)
const error = shallowRef('')
const plots = shallowRef<Plot[]>([])
const devices = shallowRef<Device[]>([])
const readings = shallowRef<SensorReading[]>([])
const plotId = shallowRef<number | undefined>()
const deviceId = shallowRef<number | undefined>()
const limit = shallowRef(200)

const availableDevices = computed(() => plotId.value ? devices.value.filter((item) => item.plot_id === plotId.value) : devices.value)
const latestTime = computed(() => readings.value[0]?.recorded_at)

async function loadResources(): Promise<void> {
  const [plotData, deviceData] = await Promise.all([api.plots(), api.devices()])
  plots.value = plotData
  devices.value = deviceData
  plotId.value ||= plotData[0]?.id
}

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    if (!plots.value.length) await loadResources()
    readings.value = (await api.telemetry({ plotId: plotId.value, deviceId: deviceId.value, limit: limit.value }))
      .sort((a, b) => new Date(b.recorded_at).getTime() - new Date(a.recorded_at).getTime())
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '读取传感器数据失败'
  } finally { loading.value = false }
}

watch(plotId, () => { if (deviceId.value && !availableDevices.value.some((item) => item.id === deviceId.value)) deviceId.value = undefined })
onMounted(load)
</script>

<template>
  <section>
    <PageHeader title="传感器数据" description="按地块和设备筛选最新上报，检查变化趋势与数据质量。" :refreshing="loading" @refresh="load" />
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" class="page-alert" />
    <div class="filter-bar">
      <el-select v-model="plotId" placeholder="选择地块" clearable @change="load"><el-option v-for="item in plots" :key="item.id" :label="item.name" :value="item.id" /></el-select>
      <el-select v-model="deviceId" placeholder="全部设备" clearable @change="load"><el-option v-for="item in availableDevices" :key="item.id" :label="item.name" :value="item.id" /></el-select>
      <el-select v-model="limit" aria-label="读取数量" @change="load"><el-option label="最近 100 条" :value="100" /><el-option label="最近 200 条" :value="200" /><el-option label="最近 500 条" :value="500" /></el-select>
      <span class="filter-bar__meta">{{ readings.length }} 条 · 更新于 {{ dateTime(latestTime) }}</span>
    </div>

    <div v-loading="loading" class="telemetry-layout">
      <article class="content-panel"><div class="panel-heading"><div><h3>指标趋势</h3><p>最多展示五类指标，时间从左到右</p></div></div><TrendChart :readings="[...readings].reverse()" /></article>
      <article class="content-panel">
        <div class="panel-heading"><div><h3>原始读数</h3><p>后端保存的最近上报明细</p></div></div>
        <el-table :data="readings" height="520" empty-text="当前筛选条件下没有数据">
          <el-table-column prop="id" label="ID" width="74" />
          <el-table-column label="指标" min-width="150"><template #default="{ row }">{{ metricName(row.metric) }}</template></el-table-column>
          <el-table-column label="数值" min-width="130"><template #default="{ row }"><strong class="table-value">{{ row.value }} {{ row.unit }}</strong></template></el-table-column>
          <el-table-column label="质量" width="110"><template #default="{ row }"><StatusTag :value="row.quality" /></template></el-table-column>
          <el-table-column label="设备 ID" width="100" prop="device_id" />
          <el-table-column label="采集时间" min-width="170"><template #default="{ row }">{{ dateTime(row.recorded_at) }}</template></el-table-column>
        </el-table>
      </article>
    </div>
  </section>
</template>

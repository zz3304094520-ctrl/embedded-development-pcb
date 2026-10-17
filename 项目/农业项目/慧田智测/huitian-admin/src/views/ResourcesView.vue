<script setup lang="ts">
import { onMounted, shallowRef } from 'vue'
import { api } from '@/api'
import PageHeader from '@/components/PageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import { dateTime, deviceTypeName } from '@/format'
import type { Device, Farm, Plot } from '@/types'

const loading = shallowRef(false)
const error = shallowRef('')
const farms = shallowRef<Farm[]>([])
const plots = shallowRef<Plot[]>([])
const devices = shallowRef<Device[]>([])
async function load() { loading.value = true; error.value = ''; try { [farms.value, plots.value, devices.value] = await Promise.all([api.farms(), api.plots(), api.devices()]) } catch (e) { error.value = e instanceof Error ? e.message : '加载失败' } finally { loading.value = false } }
const farmName = (id: number) => farms.value.find((item) => item.id === id)?.name || `农场 ${id}`
const plotName = (id: number) => plots.value.find((item) => item.id === id)?.name || `地块 ${id}`
onMounted(load)
</script>

<template><section><PageHeader title="农场与设备" description="查看当前后端保存的农场、地块和 HTTP 设备。" :refreshing="loading" @refresh="load" /><el-alert v-if="error" :title="error" type="error" :closable="false" class="page-alert" /><article v-loading="loading" class="content-panel"><el-tabs>
  <el-tab-pane :label="`农场 ${farms.length}`"><el-table :data="farms" empty-text="暂无农场"><el-table-column prop="id" label="ID" width="70"/><el-table-column prop="name" label="名称"/><el-table-column prop="location" label="位置"/><el-table-column prop="description" label="说明"/><el-table-column label="创建时间"><template #default="{row}">{{ dateTime(row.created_at) }}</template></el-table-column></el-table></el-tab-pane>
  <el-tab-pane :label="`地块 ${plots.length}`"><el-table :data="plots" empty-text="暂无地块"><el-table-column prop="id" label="ID" width="70"/><el-table-column prop="name" label="名称"/><el-table-column label="所属农场"><template #default="{row}">{{ farmName(row.farm_id) }}</template></el-table-column><el-table-column prop="crop_type" label="作物"/><el-table-column prop="area" label="面积"/></el-table></el-tab-pane>
  <el-tab-pane :label="`设备 ${devices.length}`"><el-table :data="devices" empty-text="暂无设备"><el-table-column prop="device_code" label="设备编码" min-width="150"/><el-table-column prop="name" label="名称"/><el-table-column label="地块"><template #default="{row}">{{ plotName(row.plot_id) }}</template></el-table-column><el-table-column label="类型"><template #default="{row}">{{ deviceTypeName(row.device_type) }}</template></el-table-column><el-table-column label="状态" width="100"><template #default="{row}"><StatusTag :value="row.is_online"/></template></el-table-column><el-table-column label="最后在线"><template #default="{row}">{{ dateTime(row.last_seen_at) }}</template></el-table-column></el-table></el-tab-pane>
</el-tabs></article></section></template>

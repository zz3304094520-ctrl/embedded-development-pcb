<script setup lang="ts">
import { computed, onMounted, reactive, shallowRef, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '@/api'
import PageHeader from '@/components/PageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import { dateTime } from '@/format'
import type { Device, DeviceCommand } from '@/types'

type CommandType = 'pump_on' | 'pump_off' | 'light_on' | 'light_off'

const loading = shallowRef(false)
const devices = shallowRef<Device[]>([])
const commands = shallowRef<DeviceCommand[]>([])
const form = reactive({
  device_id: undefined as number | undefined,
  command_type: 'pump_on' as CommandType,
  duration_seconds: 30,
})

const actuatorDevices = computed(() =>
  devices.value.filter((device) => device.device_type === 'pump' || device.device_type === 'grow_light'),
)
const selectedDevice = computed(() => actuatorDevices.value.find((device) => device.id === form.device_id))
const commandOptions = computed(() =>
  selectedDevice.value?.device_type === 'grow_light'
    ? [
        { label: '开启作物补光灯（CH2）', value: 'light_on' as const },
        { label: '关闭作物补光灯（CH2）', value: 'light_off' as const },
      ]
    : [
        { label: '开启水泵（CH1）', value: 'pump_on' as const },
        { label: '关闭水泵（CH1）', value: 'pump_off' as const },
      ],
)

watch(selectedDevice, (device) => {
  if (!device) return
  form.command_type = device.device_type === 'grow_light' ? 'light_on' : 'pump_on'
})

function actuatorStateLabel(device: Device): string {
  if (device.actuator_state === 'on') return 'ON'
  if (device.actuator_state === 'off') return 'OFF'
  return '状态未知'
}

function deviceName(deviceId: number): string {
  return devices.value.find((device) => device.id === deviceId)?.name ?? `设备 #${deviceId}`
}

async function load(): Promise<void> {
  loading.value = true
  try {
    ;[devices.value, commands.value] = await Promise.all([api.devices(), api.commands()])
    const currentExists = actuatorDevices.value.some((device) => device.id === form.device_id)
    if (!currentExists) {
      form.device_id = actuatorDevices.value.find((device) => device.device_type === 'pump')?.id ?? actuatorDevices.value[0]?.id
    }
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '加载失败')
  } finally {
    loading.value = false
  }
}

async function submit(): Promise<void> {
  if (!form.device_id) {
    ElMessage.warning('请选择水泵或作物补光灯')
    return
  }
  if (form.command_type.endsWith('_on') && (!Number.isInteger(form.duration_seconds) || form.duration_seconds < 1 || form.duration_seconds > 300)) {
    ElMessage.warning('持续时间必须是 1–300 秒之间的整数')
    return
  }
  try {
    const parameters = form.command_type.endsWith('_on') ? { duration_seconds: form.duration_seconds } : {}
    await api.createCommand({ device_id: form.device_id, command_type: form.command_type, parameters })
    ElMessage.success('命令已创建，等待 Jetson 执行')
    await load()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '创建失败')
  }
}

onMounted(load)
</script>

<template>
  <section>
    <PageHeader
      title="控制命令"
      description="通过 HTTP 向 Jetson 创建水泵或作物补光灯命令。"
      :refreshing="loading"
      @refresh="load"
    />
    <div class="dashboard-grid">
      <article class="content-panel">
        <div class="panel-heading">
          <div>
            <h3>创建命令</h3>
            <p>开启命令最多运行 300 秒，到时自动关闭</p>
          </div>
        </div>
        <el-empty v-if="actuatorDevices.length === 0" description="暂无水泵或作物补光灯" />
        <el-form v-else label-position="top">
          <el-form-item label="设备">
            <el-select v-model="form.device_id" style="width: 100%">
              <el-option
                v-for="device in actuatorDevices"
                :key="device.id"
                :label="`${device.name} · ${actuatorStateLabel(device)}`"
                :value="device.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="动作">
            <el-select v-model="form.command_type" style="width: 100%">
              <el-option v-for="option in commandOptions" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
          </el-form-item>
          <el-form-item v-if="form.command_type.endsWith('_on')" label="持续时间（秒）">
            <el-input-number v-model="form.duration_seconds" :min="1" :max="300" :step="1" />
          </el-form-item>
          <el-button type="primary" @click="submit">创建命令</el-button>
        </el-form>
      </article>

      <article class="content-panel">
        <div class="panel-heading">
          <div>
            <h3>命令记录</h3>
            <p>最近创建和执行状态</p>
          </div>
        </div>
        <el-table :data="commands" height="430" empty-text="暂无命令">
          <el-table-column prop="id" label="ID" width="65" />
          <el-table-column label="设备">
            <template #default="{ row }">{{ deviceName(row.device_id) }}</template>
          </el-table-column>
          <el-table-column prop="command_type" label="命令" />
          <el-table-column label="状态">
            <template #default="{ row }"><StatusTag :value="row.status" /></template>
          </el-table-column>
          <el-table-column label="时间">
            <template #default="{ row }">{{ dateTime(row.created_at) }}</template>
          </el-table-column>
        </el-table>
      </article>
    </div>
  </section>
</template>

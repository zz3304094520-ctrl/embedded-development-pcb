<script setup lang="ts">
import { computed } from 'vue'
import { PhLightning, PhTimer } from '@phosphor-icons/vue'
import { commandLabels, labelCommand, labelCommandStatus } from '../../labels'
import type { CommandType, Device, DeviceCommand } from '../../types'

const props = defineProps<{
  devices: Device[]
  commands: DeviceCommand[]
  selectedCommandDevice: Device | null
  deviceReady: boolean
  canSubmit: boolean
  actionBusy: boolean
}>()

const commandDeviceId = defineModel<number | null>('commandDeviceId', { required: true })
const commandType = defineModel<CommandType>('commandType', { required: true })
const commandDuration = defineModel<number>('commandDuration', { required: true })

defineEmits<{
  submitCommand: []
}>()

const actuatorDevices = computed(() =>
  props.devices.filter((device) => device.device_type === 'pump' || device.device_type === 'grow_light'),
)

const commandOptions = computed<Array<{ label: string; value: CommandType }>>(() => {
  if (props.selectedCommandDevice?.device_type === 'pump') {
    return [
      { value: 'pump_on', label: commandLabels.pump_on },
      { value: 'pump_off', label: commandLabels.pump_off },
    ]
  }
  if (props.selectedCommandDevice?.device_type === 'grow_light') {
    return [
      { value: 'light_on', label: commandLabels.light_on },
      { value: 'light_off', label: commandLabels.light_off },
    ]
  }
  return []
})

function deviceName(deviceId: number): string {
  return props.devices.find((device) => device.id === deviceId)?.name ?? `设备 #${deviceId}`
}

function commandStatusClass(status: string): string {
  if (status === 'succeeded') return 'command-status--success'
  if (status === 'failed') return 'command-status--failed'
  if (status === 'acknowledged') return 'command-status--executing'
  return 'command-status--pending'
}
</script>

<template>
  <article class="panel command-panel js-entrance">
    <div class="section-heading">
      <div>
        <span class="panel__label">CONTROL</span>
        <h2>水泵与补光灯控制</h2>
      </div>
    </div>
    <div v-if="actuatorDevices.length === 0" class="empty-state">
      <strong>当前地块暂无可控设备</strong>
      <p>请确认后端已创建 pump-001 和 grow-light-001。</p>
    </div>
    <form v-else class="form-stack" @submit.prevent="$emit('submitCommand')">
      <label>
        <span>设备</span>
        <select v-model.number="commandDeviceId" name="command_device_id" autocomplete="off">
          <option v-for="device in actuatorDevices" :key="device.id" :value="device.id">
            {{ device.name }} · {{ device.actuator_state === 'on' ? 'ON' : device.actuator_state === 'off' ? 'OFF' : '状态未知' }}
          </option>
        </select>
      </label>
      <label>
        <span>命令</span>
        <select v-model="commandType" name="command_type" autocomplete="off">
          <option v-for="option in commandOptions" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
      </label>
      <label v-if="commandType === 'pump_on' || commandType === 'light_on'">
        <span class="form-label-with-icon"><PhTimer :size="17" weight="bold" aria-hidden="true" />持续时间（1–300 秒）</span>
        <input v-model.number="commandDuration" name="duration_seconds" type="number" inputmode="numeric" autocomplete="off" min="1" max="300" step="1" />
      </label>
      <button class="button button--primary" type="submit" :disabled="!canSubmit">
        <PhLightning :size="18" weight="fill" aria-hidden="true" />
        {{ actionBusy ? '发送中…' : deviceReady ? '创建命令' : '等待继电器连接' }}
      </button>
      <p class="form-note" :class="{ 'form-note--warning': selectedCommandDevice && !deviceReady }">
        {{
          !selectedCommandDevice
            ? '请选择设备'
            : deviceReady
              ? `继电器已连接，将发送到 ${selectedCommandDevice.device_code}`
              : '继电器 Agent 离线；插入 USB 继电器后会自动连接'
        }}
      </p>
    </form>
    <div v-if="commands.length" class="command-list">
      <div v-for="command in commands" :key="command.id">
        <span class="command-list__summary">
          <strong>{{ labelCommand(command.command_type) }}</strong>
          <small>{{ deviceName(command.device_id) }}</small>
        </span>
        <span class="command-status" :class="commandStatusClass(command.status)">{{ labelCommandStatus(command.status) }}</span>
      </div>
    </div>
    <div v-else class="empty-state command-list-empty">
      <strong>暂无控制命令</strong>
      <p>创建命令后，执行状态会显示在这里。</p>
    </div>
  </article>
</template>

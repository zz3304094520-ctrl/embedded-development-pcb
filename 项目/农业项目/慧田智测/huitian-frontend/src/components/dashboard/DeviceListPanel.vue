<script setup lang="ts">
import { PhBroadcast, PhCamera, PhDrop, PhSun } from '@phosphor-icons/vue'
import { labelActuatorState, labelDeviceType } from '../../labels'
import { hasRecentHeartbeat, relativeStatusTime } from '../../format'
import type { Device } from '../../types'

defineProps<{
  devices: Device[]
}>()

const selectedDeviceId = defineModel<number | null>('selectedDeviceId', { required: true })

function selectDevice(deviceId: number): void {
  selectedDeviceId.value = deviceId
}

function isActuator(device: Device): boolean {
  return device.device_type === 'pump' || device.device_type === 'grow_light'
}

function deviceIsOnline(device: Device): boolean {
  if (!isActuator(device)) return device.is_online
  return hasRecentHeartbeat(device.is_online, device.last_seen_at)
}
</script>

<template>
  <article class="panel device-panel js-entrance">
    <div class="section-heading">
      <div>
        <span class="panel__label">DEVICES</span>
        <h2>现场设备</h2>
      </div>
    </div>
    <div v-if="devices.length === 0" class="empty-state">
      <strong>当前地块暂无设备</strong>
      <p>请先在后端初始化演示数据。</p>
    </div>
    <div v-else class="device-list">
      <button
        v-for="device in devices"
        :key="device.id"
        class="device-row"
        :class="{ 'is-selected': selectedDeviceId === device.id }"
        type="button"
        @click="selectDevice(device.id)"
      >
        <span class="device-row__icon" aria-hidden="true">
          <PhDrop v-if="device.device_type === 'pump'" :size="22" weight="duotone" />
          <PhSun v-else-if="device.device_type === 'grow_light'" :size="22" weight="duotone" />
          <PhCamera v-else-if="device.device_type === 'camera'" :size="22" weight="duotone" />
          <PhBroadcast v-else :size="22" weight="duotone" />
        </span>
        <span class="device-row__identity">
          <strong>{{ device.name }}</strong>
          <small>{{ labelDeviceType(device.device_type) }} · {{ device.device_code }}</small>
          <small class="device-row__connectivity">
            <span class="status-dot" :class="deviceIsOnline(device) ? 'status-dot--ok' : 'status-dot--idle'"></span>
            {{ deviceIsOnline(device) ? '在线' : '离线' }} · {{ relativeStatusTime(device.last_seen_at) }}
          </small>
        </span>
        <span v-if="isActuator(device)" class="device-row__actuator">
          <span class="actuator-state" :class="`actuator-state--${device.actuator_state}`">
            继电器 {{ labelActuatorState(device.actuator_state) }}
          </span>
          <small>状态更新：{{ relativeStatusTime(device.state_updated_at) }}</small>
        </span>
      </button>
    </div>
  </article>
</template>

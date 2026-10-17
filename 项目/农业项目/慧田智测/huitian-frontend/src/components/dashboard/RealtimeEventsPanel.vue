<script setup lang="ts">
import { formatDateTime } from '../../format'
import type { RealtimeEvent } from '../../types'

defineProps<{
  events: RealtimeEvent[]
  wsConnected: boolean
}>()
</script>

<template>
  <article class="panel js-entrance">
    <div class="section-heading">
      <div>
        <span class="panel__label">实时事件</span>
        <h2>WebSocket</h2>
      </div>
      <span class="badge" :class="wsConnected ? 'badge--ok' : 'badge--idle'">
        {{ wsConnected ? '已连接' : '未连接' }}
      </span>
    </div>
    <div v-if="events.length === 0" class="empty-state">
      <strong>等待实时消息</strong>
      <p>传感器上报、告警和命令状态变化会显示在这里。</p>
    </div>
    <div v-else class="event-list">
      <div v-for="event in events" :key="event.id">
        <strong>{{ event.event }}</strong>
        <small>{{ formatDateTime(event.receivedAt) }}</small>
      </div>
    </div>
  </article>
</template>

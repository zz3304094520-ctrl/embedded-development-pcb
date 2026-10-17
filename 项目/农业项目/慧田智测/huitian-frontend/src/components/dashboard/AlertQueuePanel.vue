<script setup lang="ts">
import { computed } from 'vue'
import { formatDateTime } from '../../format'
import { labelAlertStatus, labelSeverity } from '../../labels'
import type { Alert } from '../../types'
import type { AlertAction } from '../../composables/useFarmDashboard'

const props = defineProps<{
  alerts: Alert[]
  activeAlertCount: number
  actionBusy: boolean
}>()

const emit = defineEmits<{
  changeStatus: [alert: Alert, action: AlertAction]
}>()

const displayedAlerts = computed(() => props.alerts.slice(0, 6))
</script>

<template>
  <article class="panel js-entrance">
    <div class="section-heading">
      <div>
        <span class="panel__label">告警</span>
        <h2>处理队列</h2>
      </div>
      <span class="badge" :class="props.activeAlertCount > 0 ? 'badge--warning' : 'badge--ok'">
        {{ props.activeAlertCount }} 待处理
      </span>
    </div>
    <div v-if="props.alerts.length === 0" class="empty-state">
      <strong>暂无告警</strong>
      <p>上报告警数据后，这里会出现需要确认或解决的记录。</p>
    </div>
    <div v-else class="alert-list">
      <div v-for="alert in displayedAlerts" :key="alert.id" class="alert-item" :class="`alert-item--${alert.severity}`">
        <div>
          <span class="badge">{{ labelSeverity(alert.severity) }}</span>
          <strong>{{ alert.message }}</strong>
          <small>{{ labelAlertStatus(alert.status) }} · {{ formatDateTime(alert.created_at) }}</small>
        </div>
        <div v-if="alert.status !== 'resolved'" class="row-actions">
          <button
            v-if="alert.status === 'open'"
            class="button button--ghost"
            type="button"
            :disabled="props.actionBusy"
            @click="emit('changeStatus', alert, 'acknowledge')"
          >
            确认
          </button>
          <button class="button button--secondary" type="button" :disabled="props.actionBusy" @click="emit('changeStatus', alert, 'resolve')">
            解决
          </button>
        </div>
      </div>
    </div>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ value: string | boolean; kind?: 'status' | 'severity' | 'quality' }>()
const normalized = computed(() => String(props.value))
const labels: Record<string, string> = {
  true: '在线', false: '离线', open: '待处理', acknowledged: '执行中', resolved: '已解决',
  pending: '待下发', sent: '已下发', succeeded: '成功', failed: '失败',
  critical: '严重', warning: '警告', info: '提示', good: '良好', suspect: '可疑', bad: '异常',
  ok: '正常', connected: '已连接', disabled: '已关闭', disconnected: '未连接',
}
const tone = computed(() => {
  if (['true', 'ok', 'connected', 'succeeded', 'resolved', 'good'].includes(normalized.value)) return 'success'
  if (['critical', 'failed', 'bad', 'open'].includes(normalized.value)) return 'danger'
  if (['warning', 'suspect', 'pending', 'acknowledged'].includes(normalized.value)) return 'warning'
  return 'info'
})
</script>

<template><span class="status-tag" :class="`status-tag--${tone}`"><i></i>{{ labels[normalized] || normalized }}</span></template>

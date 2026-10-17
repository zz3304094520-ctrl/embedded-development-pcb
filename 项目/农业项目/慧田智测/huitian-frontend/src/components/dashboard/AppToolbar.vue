<script setup lang="ts">
import { PhArrowClockwise, PhLink } from '@phosphor-icons/vue'
import { apiEndpointLabel } from '../../api'

defineProps<{
  refreshing: boolean
}>()

defineEmits<{
  refresh: []
}>()
</script>

<template>
  <section class="toolbar js-entrance" aria-label="系统操作">
    <div class="toolbar__endpoint">
      <PhLink :size="18" weight="bold" aria-hidden="true" />
      <span>
        <small class="toolbar__label">服务连接</small>
        <strong>{{ apiEndpointLabel }}</strong>
      </span>
    </div>
    <button class="button button--ghost toolbar__refresh" type="button" :disabled="refreshing" @click="$emit('refresh')">
      <PhArrowClockwise :size="18" weight="bold" aria-hidden="true" />
      {{ refreshing ? '刷新中' : '刷新数据' }}
    </button>
  </section>
</template>

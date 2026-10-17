<script setup lang="ts">
defineProps<{ title: string; description: string; refreshing?: boolean }>()
defineEmits<{ refresh: [] }>()
</script>

<template>
  <div class="page-heading">
    <div>
      <h2>{{ title }}</h2>
      <p>{{ description }}</p>
    </div>
    <div class="page-heading__actions">
      <slot name="actions" />
      <el-button :loading="refreshing" @click="$emit('refresh')">刷新数据</el-button>
    </div>
  </div>
</template>

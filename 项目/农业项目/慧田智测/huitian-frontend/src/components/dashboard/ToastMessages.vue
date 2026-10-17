<script setup lang="ts">
defineProps<{
  errorMessage: string
  successMessage: string
}>()

defineEmits<{
  dismissError: []
}>()
</script>

<template>
  <div v-if="errorMessage" class="toast toast--error" role="alert">
    <span>{{ errorMessage }}</span>
    <button type="button" @click="$emit('dismissError')">知道了</button>
  </div>
  <div v-if="successMessage" class="toast toast--success" role="status">
    {{ successMessage }}
  </div>
</template>

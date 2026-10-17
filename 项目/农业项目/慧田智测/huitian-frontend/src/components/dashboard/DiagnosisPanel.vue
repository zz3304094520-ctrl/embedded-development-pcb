<script setup lang="ts">
import { watch, useTemplateRef } from 'vue'
import { formatDateTime } from '../../format'
import type { DiagnosisRecord } from '../../types'

defineProps<{
  records: DiagnosisRecord[]
  canUpload: boolean
  diagnosisBusy: boolean
}>()

const file = defineModel<File | null>('file', { required: true })
const fileInput = useTemplateRef<HTMLInputElement>('fileInput')

defineEmits<{
  upload: []
}>()

function onFileChange(event: Event): void {
  const input = event.target as HTMLInputElement
  file.value = input.files?.[0] ?? null
}

watch(file, (value) => {
  if (!value && fileInput.value) {
    fileInput.value.value = ''
  }
})
</script>

<template>
  <article class="panel js-entrance">
    <div class="section-heading">
      <div>
        <span class="panel__label">诊断</span>
        <h2>图片演示诊断</h2>
      </div>
    </div>
    <form class="form-stack" @submit.prevent="$emit('upload')">
      <label>
        <span>上传作物图片</span>
        <input ref="fileInput" name="diagnosis_image" type="file" accept="image/png,image/jpeg,image/jpg,image/webp" autocomplete="off" @change="onFileChange" />
      </label>
      <button class="button button--primary" type="submit" :disabled="!canUpload">
        {{ diagnosisBusy ? '上传中…' : '上传诊断图片' }}
      </button>
      <p class="form-note">当前后端返回的是演示诊断结果，不是真实 AI 判断。</p>
    </form>
    <div v-if="records.length === 0" class="empty-state empty-state--compact">
      <strong>暂无诊断记录</strong>
    </div>
    <div v-else class="diagnosis-list">
      <div v-for="record in records" :key="record.id">
        <strong>{{ record.health_status }}</strong>
        <small>{{ record.crop_type }} · {{ record.growth_stage }} · {{ formatDateTime(record.created_at) }}</small>
        <p>{{ record.result_text }}</p>
      </div>
    </div>
  </article>
</template>

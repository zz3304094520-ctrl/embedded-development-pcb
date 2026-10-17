<script setup lang="ts">
import { onMounted, shallowRef } from 'vue'
import { api } from '@/api'
import PageHeader from '@/components/PageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import { dateTime } from '@/format'
import type { DiagnosisRecord, Plot } from '@/types'
const loading=shallowRef(false);const records=shallowRef<DiagnosisRecord[]>([]);const plots=shallowRef<Plot[]>([]);const plotId=shallowRef<number|undefined>()
async function load(){loading.value=true;try{if(!plots.value.length)plots.value=await api.plots();records.value=await api.diagnoses(plotId.value)}finally{loading.value=false}}
const plotName=(id:number)=>plots.value.find(p=>p.id===id)?.name||`地块 ${id}`
onMounted(load)
</script>
<template><section><PageHeader title="诊断记录" description="查看后端保存的作物图片诊断演示结果。" :refreshing="loading" @refresh="load"><template #actions><el-select v-model="plotId" placeholder="全部地块" clearable @change="load"><el-option v-for="p in plots" :key="p.id" :label="p.name" :value="p.id"/></el-select></template></PageHeader><article v-loading="loading" class="content-panel"><el-table :data="records" empty-text="暂无诊断记录"><el-table-column label="地块"><template #default="{row}">{{plotName(row.plot_id)}}</template></el-table-column><el-table-column prop="crop_type" label="作物"/><el-table-column prop="growth_stage" label="生长阶段"/><el-table-column label="健康状态"><template #default="{row}"><StatusTag :value="row.health_status"/></template></el-table-column><el-table-column prop="result_text" label="诊断说明" min-width="300"/><el-table-column label="时间" min-width="160"><template #default="{row}">{{dateTime(row.created_at)}}</template></el-table-column></el-table></article></section></template>

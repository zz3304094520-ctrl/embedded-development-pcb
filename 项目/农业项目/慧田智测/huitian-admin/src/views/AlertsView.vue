<script setup lang="ts">
import { onMounted, shallowRef } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '@/api'
import PageHeader from '@/components/PageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import { dateTime, metricName } from '@/format'
import type { AlertItem, AlertRule } from '@/types'
const loading = shallowRef(false); const error = shallowRef(''); const alerts = shallowRef<AlertItem[]>([]); const rules = shallowRef<AlertRule[]>([])
async function load(){loading.value=true;error.value='';try{[alerts.value,rules.value]=await Promise.all([api.alerts(),api.rules()])}catch(e){error.value=e instanceof Error?e.message:'加载失败'}finally{loading.value=false}}
async function change(id:number, action:'ack'|'resolve'){try{action==='ack'?await api.acknowledgeAlert(id):await api.resolveAlert(id);ElMessage.success(action==='ack'?'告警已确认':'告警已解决');await load()}catch(e){ElMessage.error(e instanceof Error?e.message:'操作失败')}}
onMounted(load)
</script>
<template><section><PageHeader title="告警中心" description="查看规则并确认或解决现场告警。" :refreshing="loading" @refresh="load"/><el-alert v-if="error" :title="error" type="error" :closable="false" class="page-alert"/><article v-loading="loading" class="content-panel"><el-tabs><el-tab-pane :label="`告警 ${alerts.length}`"><el-table :data="alerts" empty-text="暂无告警"><el-table-column prop="message" label="告警内容" min-width="240"/><el-table-column label="级别" width="100"><template #default="{row}"><StatusTag :value="row.severity"/></template></el-table-column><el-table-column label="状态" width="110"><template #default="{row}"><StatusTag :value="row.status"/></template></el-table-column><el-table-column label="时间" min-width="150"><template #default="{row}">{{dateTime(row.created_at)}}</template></el-table-column><el-table-column label="操作" width="170"><template #default="{row}"><el-button v-if="row.status==='open'" link type="primary" @click="change(row.id,'ack')">确认</el-button><el-button v-if="row.status!=='resolved'" link type="success" @click="change(row.id,'resolve')">解决</el-button></template></el-table-column></el-table></el-tab-pane><el-tab-pane :label="`规则 ${rules.length}`"><el-table :data="rules" empty-text="暂无规则"><el-table-column prop="name" label="规则"/><el-table-column label="指标"><template #default="{row}">{{metricName(row.metric)}}</template></el-table-column><el-table-column label="条件"><template #default="{row}">{{row.operator}} {{row.threshold}}</template></el-table-column><el-table-column label="级别"><template #default="{row}"><StatusTag :value="row.severity"/></template></el-table-column><el-table-column label="启用"><template #default="{row}"><StatusTag :value="row.enabled"/></template></el-table-column></el-table></el-tab-pane></el-tabs></article></section></template>

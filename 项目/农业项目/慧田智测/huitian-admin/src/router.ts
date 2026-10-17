import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: () => import('@/views/DashboardView.vue'), meta: { title: '运行总览' } },
    { path: '/resources', name: 'resources', component: () => import('@/views/ResourcesView.vue'), meta: { title: '农场与设备' } },
    { path: '/telemetry', name: 'telemetry', component: () => import('@/views/TelemetryView.vue'), meta: { title: '传感器数据' } },
    { path: '/alerts', name: 'alerts', component: () => import('@/views/AlertsView.vue'), meta: { title: '告警中心' } },
    { path: '/commands', name: 'commands', component: () => import('@/views/CommandsView.vue'), meta: { title: '控制命令' } },
    { path: '/diagnosis', name: 'diagnosis', component: () => import('@/views/DiagnosisView.vue'), meta: { title: '诊断记录' } },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.afterEach((to) => {
  document.title = `${String(to.meta.title || '管理后台')} · 慧田智测`
})

export default router

<script setup lang="ts">
import { computed, shallowRef } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const mobileNavOpen = shallowRef(false)
const h5Url = import.meta.env.VITE_H5_URL || 'http://172.20.10.2:5173'

const navItems = [
  { to: '/', label: '运行总览', mark: '总' },
  { to: '/resources', label: '农场与设备', mark: '田' },
  { to: '/telemetry', label: '传感器数据', mark: '数' },
  { to: '/alerts', label: '告警中心', mark: '警' },
  { to: '/commands', label: '控制命令', mark: '控' },
  { to: '/diagnosis', label: '诊断记录', mark: '诊' },
]

const pageTitle = computed(() => String(route.meta.title || '管理后台'))
</script>

<template>
  <div class="admin-shell">
    <button class="mobile-menu" type="button" aria-label="打开导航" @click="mobileNavOpen = !mobileNavOpen">菜单</button>
    <aside class="sidebar" :class="{ 'sidebar--open': mobileNavOpen }">
      <div class="brand">
        <span class="brand__mark">田</span>
        <span><strong>慧田智测</strong><small>农业物联网管理后台</small></span>
      </div>
      <nav class="sidebar__nav" aria-label="管理后台导航">
        <RouterLink v-for="item in navItems" :key="item.to" :to="item.to" @click="mobileNavOpen = false">
          <span class="nav-mark">{{ item.mark }}</span>
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>
      <div class="sidebar__foot">
        <span class="connection-dot" aria-hidden="true"></span>
        <span><strong>HTTP 模式</strong><small>FastAPI · SQLite</small></span>
      </div>
    </aside>
    <button v-if="mobileNavOpen" class="nav-backdrop" type="button" aria-label="关闭导航" @click="mobileNavOpen = false"></button>

    <div class="workspace">
      <header class="topbar">
        <div>
          <p>慧田智测 / {{ pageTitle }}</p>
          <h1>{{ pageTitle }}</h1>
        </div>
        <a class="h5-link" :href="h5Url" target="_blank" rel="noreferrer">打开 H5 监测端 <span>↗</span></a>
      </header>
      <main class="page-content">
        <RouterView v-slot="{ Component }">
          <Transition name="page" mode="out-in">
            <component :is="Component" />
          </Transition>
        </RouterView>
      </main>
    </div>
  </div>
</template>

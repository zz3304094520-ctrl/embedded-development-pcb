<script setup lang="ts">
import type { Component } from 'vue'
import { PhCpu, PhHouse, PhStethoscope, PhUserCircle } from '@phosphor-icons/vue'

type NavigationKey = 'home' | 'diagnosis' | 'devices' | 'profile'

type NavigationItem = {
  key: NavigationKey
  label: string
  href: string
  icon: Component
}

const active = defineModel<NavigationKey>('active', { default: 'home' })

const emit = defineEmits<{
  navigate: [target: NavigationKey]
}>()

const navigationItems: NavigationItem[] = [
  { key: 'home', label: '首页', href: '#top', icon: PhHouse },
  { key: 'diagnosis', label: '智诊', href: '#diagnosis', icon: PhStethoscope },
  { key: 'devices', label: '设备', href: '#devices', icon: PhCpu },
  { key: 'profile', label: '我的', href: '#profile', icon: PhUserCircle },
]

function navigateTo(item: NavigationItem): void {
  active.value = item.key
  emit('navigate', item.key)
}
</script>

<template>
  <nav class="bottom-navigation" aria-label="主要功能导航">
    <a
      v-for="item in navigationItems"
      :key="item.key"
      class="bottom-navigation__item"
      :class="{ 'is-active': active === item.key }"
      :href="item.href"
      :aria-current="active === item.key ? 'page' : undefined"
      @click="navigateTo(item)"
    >
      <span class="bottom-navigation__icon">
        <component :is="item.icon" :size="21" :weight="active === item.key ? 'fill' : 'regular'" aria-hidden="true" />
      </span>
      <span>{{ item.label }}</span>
    </a>
  </nav>
</template>

<style scoped>
.bottom-navigation {
  position: fixed;
  z-index: 80;
  right: 0;
  bottom: 0;
  left: 0;
  min-height: calc(4rem + env(safe-area-inset-bottom));
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  border-top: 1px solid #dce4da;
  background: #fffef8;
  padding: 0.35rem max(0.75rem, calc((100vw - 72rem) / 2)) env(safe-area-inset-bottom);
  box-shadow: 0 -0.35rem 1.5rem rgb(31 63 45 / 9%);
}

.bottom-navigation__item {
  min-width: 0;
  display: grid;
  place-content: center;
  justify-items: center;
  gap: 0.14rem;
  color: #7a8b80;
  font-size: 0.68rem;
  font-weight: 700;
  text-decoration: none;
}

.bottom-navigation__icon {
  min-width: 2.2rem;
  min-height: 1.8rem;
  display: grid;
  place-items: center;
  border-radius: 0.55rem;
}

.bottom-navigation__item.is-active {
  color: #24714d;
}

.bottom-navigation__item.is-active .bottom-navigation__icon {
  background: #dcefe3;
}

.bottom-navigation__item:focus-visible {
  outline: 3px solid rgb(52 131 86 / 24%);
  outline-offset: -3px;
}
</style>

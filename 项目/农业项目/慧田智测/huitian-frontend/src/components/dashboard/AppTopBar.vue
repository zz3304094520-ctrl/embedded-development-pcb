<script setup lang="ts">
import { PhPlant, PhWifiHigh, PhWifiSlash } from '@phosphor-icons/vue'

const props = defineProps<{
  greeting: string
  userName: string
  location: string
  notificationCount: number
  wsConnected: boolean
}>()

defineEmits<{
  notification: []
}>()
</script>

<template>
  <header class="app-top-bar">
    <span class="app-top-bar__connection" :class="{ 'is-offline': !props.wsConnected }">
      <PhWifiHigh v-if="props.wsConnected" :size="16" weight="bold" aria-hidden="true" />
      <PhWifiSlash v-else :size="16" weight="bold" aria-hidden="true" />
      <span>{{ props.wsConnected ? '实时连接' : '连接中' }}</span>
    </span>

    <a class="app-top-bar__brand" href="#top" aria-label="返回慧田智测首页">
      <PhPlant :size="18" weight="fill" aria-hidden="true" />
      <strong>慧田智测</strong>
    </a>

    <span class="app-top-bar__location" :title="props.location">{{ props.location }}</span>
  </header>
</template>

<style scoped>
.app-top-bar {
  min-height: 3.5rem;
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  gap: 1rem;
  background: #10251a;
  padding: 0 clamp(1rem, 3vw, 2rem);
  color: #f6faf7;
}

.app-top-bar__brand,
.app-top-bar__connection {
  display: inline-flex;
  align-items: center;
}

.app-top-bar__brand {
  gap: 0.45rem;
  color: inherit;
  font-size: 0.98rem;
  letter-spacing: 0.04em;
  text-decoration: none;
}

.app-top-bar__connection {
  justify-self: start;
  gap: 0.4rem;
  color: #a9d5b8;
  font-size: 0.72rem;
  font-weight: 700;
}

.app-top-bar__connection.is-offline {
  color: #e6c47a;
}

.app-top-bar__location {
  max-width: 18rem;
  justify-self: end;
  overflow: hidden;
  color: #b8c8be;
  font-size: 0.72rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 640px) {
  .app-top-bar {
    grid-template-columns: 2rem 1fr 2rem;
    gap: 0.35rem;
    padding-inline: 0.8rem;
  }

  .app-top-bar__brand {
    justify-self: center;
  }

  .app-top-bar__connection span,
  .app-top-bar__location {
    display: none;
  }
}
</style>

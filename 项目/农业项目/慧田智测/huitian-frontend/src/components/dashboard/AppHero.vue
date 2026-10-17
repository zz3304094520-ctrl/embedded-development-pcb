<script setup lang="ts">
import { computed, shallowRef } from 'vue'
import { PhBell, PhMapPin, PhWarningCircle } from '@phosphor-icons/vue'
import fieldHero from '../../assets/field-hero.png'
import AppTopBar from './AppTopBar.vue'
import BottomNavigation from './BottomNavigation.vue'

type NavigationKey = 'home' | 'diagnosis' | 'devices' | 'profile'

const props = withDefaults(defineProps<{
  systemStatusLabel: string
  fieldRiskLabel: string
  wsConnected: boolean
  activeAlertCount: number
  criticalAlertCount: number
  location?: string
  hasTelemetry?: boolean
  alertCount?: number
  userName?: string
}>(), {
  location: '上海 · 金山示范田',
  hasTelemetry: false,
  alertCount: undefined,
  userName: '歆澜',
})

const emit = defineEmits<{
  notification: []
  navigate: [target: NavigationKey]
}>()

const activeNavigation = shallowRef<NavigationKey>('home')
const notificationCount = computed(() => props.alertCount ?? props.activeAlertCount)
const greeting = getGreeting()
const statusHeadline = computed(() => props.hasTelemetry ? '田间设备数据正在实时更新。' : '尚未收到田间设备数据。')
const statusDetail = computed(() => props.hasTelemetry
  ? `${props.systemStatusLabel}，${props.fieldRiskLabel}`
  : '请检查 Jetson、传感器供电和后端网络，数据到达后会自动更新。')

function getGreeting(): string {
  const hour = new Date().getHours()
  if (hour < 6) return '夜深了'
  if (hour < 11) return '早上好'
  if (hour < 14) return '中午好'
  if (hour < 18) return '下午好'
  return '晚上好'
}
</script>

<template>
  <section id="top" class="farm-hero" aria-labelledby="page-title">
    <AppTopBar
      :greeting="greeting"
      :user-name="props.userName"
      :location="props.location"
      :notification-count="notificationCount"
      :ws-connected="props.wsConnected"
      @notification="emit('notification')"
    />

    <div class="farm-hero__card">
      <img class="farm-hero__image" :src="fieldHero" alt="夕阳下的成熟稻田">
      <span class="farm-hero__shade" aria-hidden="true"></span>

      <div class="farm-hero__profile">
        <span class="farm-hero__avatar" aria-hidden="true">歆</span>
        <span>
          <strong>{{ greeting }}，{{ props.userName }}</strong>
          <small><PhMapPin :size="14" weight="fill" aria-hidden="true" />{{ props.location }}</small>
        </span>
      </div>

      <a class="farm-hero__notification" href="#alerts" @click="emit('notification')">
        <PhBell :size="18" weight="bold" aria-hidden="true" />
        <span>通知</span>
        <b v-if="notificationCount > 0">{{ notificationCount > 99 ? '99+' : notificationCount }}</b>
      </a>

      <div class="farm-hero__content">
        <p>今日田间</p>
        <h1 id="page-title">{{ statusHeadline }}</h1>
        <span>{{ statusDetail }}</span>
      </div>

      <div v-if="props.criticalAlertCount > 0" class="farm-hero__critical" role="status">
        <PhWarningCircle :size="18" weight="fill" aria-hidden="true" />
        {{ props.criticalAlertCount }} 个严重告警
      </div>
    </div>

    <BottomNavigation v-model:active="activeNavigation" @navigate="emit('navigate', $event)" />
  </section>
</template>

<style scoped>
.farm-hero {
  width: 100%;
  background: #edf2e8;
}

.farm-hero__card {
  position: relative;
  min-height: 19rem;
  overflow: hidden;
  border-radius: 0 0 1.8rem 1.8rem;
  background: #183723;
  color: #ffffff;
}

.farm-hero__image,
.farm-hero__shade {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.farm-hero__image {
  display: block;
  object-fit: cover;
  object-position: 45% center;
  filter: saturate(0.82) brightness(0.72) contrast(1.06);
}

.farm-hero__shade {
  background: rgb(4 24 13 / 48%);
}

.farm-hero__profile,
.farm-hero__notification,
.farm-hero__content,
.farm-hero__critical {
  position: absolute;
  z-index: 1;
}

.farm-hero__profile {
  top: 1.15rem;
  left: clamp(1rem, 2.5vw, 1.5rem);
  display: flex;
  align-items: center;
  gap: 0.65rem;
}

.farm-hero__avatar {
  width: 2.7rem;
  height: 2.7rem;
  display: grid;
  place-items: center;
  border: 1px solid rgb(255 255 255 / 22%);
  border-radius: 0.75rem;
  background: rgb(19 44 27 / 72%);
  font-weight: 850;
}

.farm-hero__profile strong,
.farm-hero__profile small {
  display: flex;
  align-items: center;
}

.farm-hero__profile strong {
  font-size: 0.9rem;
}

.farm-hero__profile small {
  gap: 0.2rem;
  margin-top: 0.23rem;
  color: #d6dfd8;
  font-size: 0.68rem;
}

.farm-hero__notification {
  top: 1.25rem;
  right: clamp(1rem, 2.5vw, 1.5rem);
  min-height: 2.4rem;
  display: inline-flex;
  align-items: center;
  gap: 0.38rem;
  border: 1px solid rgb(255 255 255 / 20%);
  border-radius: 0.8rem;
  background: rgb(19 44 27 / 68%);
  padding: 0 0.8rem;
  color: #ffffff;
  font-size: 0.75rem;
  font-weight: 750;
  text-decoration: none;
}

.farm-hero__notification b {
  min-width: 1.2rem;
  min-height: 1.2rem;
  display: grid;
  place-items: center;
  border-radius: 999px;
  background: #c54e3e;
  padding-inline: 0.2rem;
  font-size: 0.6rem;
}

.farm-hero__content {
  right: clamp(1rem, 3vw, 2rem);
  bottom: 2.4rem;
  left: clamp(1rem, 3vw, 2rem);
  max-width: 42rem;
}

.farm-hero__content p {
  margin: 0 0 0.65rem;
  color: #dfe8df;
  font-size: 0.76rem;
  font-weight: 760;
}

.farm-hero__content h1 {
  margin: 0;
  color: #ffffff;
  font-size: clamp(1.75rem, 4vw, 2.65rem);
  line-height: 1.12;
  letter-spacing: -0.04em;
}

.farm-hero__content > span {
  display: block;
  max-width: 35rem;
  margin-top: 0.7rem;
  color: #d4ded6;
  font-size: 0.78rem;
  line-height: 1.65;
}

.farm-hero__critical {
  right: 1.25rem;
  bottom: 1.25rem;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  border-radius: 999px;
  background: #9e362c;
  padding: 0.52rem 0.78rem;
  font-size: 0.7rem;
  font-weight: 750;
}

@media (max-width: 640px) {
  .farm-hero__card {
    min-height: 23rem;
  }

  .farm-hero__notification span {
    display: none;
  }

  .farm-hero__notification {
    padding-inline: 0.68rem;
  }

  .farm-hero__content {
    bottom: 2rem;
  }

  .farm-hero__critical {
    display: none;
  }
}
</style>

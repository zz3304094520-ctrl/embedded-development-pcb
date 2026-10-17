<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, useTemplateRef, watch } from 'vue'
import { PhCpu, PhStethoscope, PhUserCircle } from '@phosphor-icons/vue'
import AlertQueuePanel from './components/dashboard/AlertQueuePanel.vue'
import AppHero from './components/dashboard/AppHero.vue'
import AppToolbar from './components/dashboard/AppToolbar.vue'
import CommandPanel from './components/dashboard/CommandPanel.vue'
import CameraMonitorPanel from './components/dashboard/CameraMonitorPanel.vue'
import DeviceListPanel from './components/dashboard/DeviceListPanel.vue'
import DiagnosisPanel from './components/dashboard/DiagnosisPanel.vue'
import LoadingGrid from './components/dashboard/LoadingGrid.vue'
import OverviewGrid from './components/dashboard/OverviewGrid.vue'
import RealtimeEventsPanel from './components/dashboard/RealtimeEventsPanel.vue'
import SensorReadingsPanel from './components/dashboard/SensorReadingsPanel.vue'
import SensorSummaryPanel from './components/dashboard/SensorSummaryPanel.vue'
import ToastMessages from './components/dashboard/ToastMessages.vue'
import { useFarmDashboard } from './composables/useFarmDashboard'
import { useHangzhouWeather } from './composables/useHangzhouWeather'
import { useInterfaceMotion } from './composables/useInterfaceMotion'
import { useRealtimeEvents } from './composables/useRealtimeEvents'

const dashboard = useFarmDashboard()
const hangzhouWeather = useHangzhouWeather()
const rootEl = useTemplateRef<HTMLElement>('root')
const motion = useInterfaceMotion(rootEl)
const realtime = useRealtimeEvents({
  onRefreshRequested: () => {
    void dashboard.refreshAll(true)
  },
  onSensorRefreshRequested: () => {
    void dashboard.refreshSensorData()
  },
})

const hasTelemetry = computed(() => dashboard.latestSensorReadings.value.length > 0)
const currentLocation = computed(() => dashboard.selectedFarm.value?.location || '上海 · 金山示范田')
let actuatorRefreshTimer: number | null = null

watch(dashboard.successMessage, async (value) => {
  if (!value) return
  await nextTick()
  motion.animateSuccessToast()
})

onMounted(async () => {
  await dashboard.loadAll()
  realtime.connectWebSocket()
  actuatorRefreshTimer = window.setInterval(() => {
    void dashboard.refreshActuatorData()
  }, 3_000)
  await nextTick()
  motion.animateEntrance()
})

onBeforeUnmount(() => {
  if (actuatorRefreshTimer !== null) {
    window.clearInterval(actuatorRefreshTimer)
    actuatorRefreshTimer = null
  }
})
</script>

<template>
  <a class="skip-link" href="#main-content">跳到主要内容</a>
  <main id="main-content" ref="root" class="app-shell">
    <AppHero
      :system-status-label="dashboard.systemStatusLabel.value"
      :field-risk-label="dashboard.fieldRiskLabel.value"
      :ws-connected="realtime.wsConnected.value"
      :active-alert-count="dashboard.activeAlerts.value.length"
      :critical-alert-count="dashboard.criticalAlerts.value.length"
      :location="currentLocation"
      :has-telemetry="hasTelemetry"
    />

    <div class="dashboard-body">
      <ToastMessages
        :error-message="dashboard.errorMessage.value"
        :success-message="dashboard.successMessage.value"
        @dismiss-error="dashboard.clearError"
      />

      <LoadingGrid v-if="dashboard.loading.value" />

      <template v-else>
        <OverviewGrid
          v-model:farm-id="dashboard.selectedFarmId.value"
          v-model:plot-id="dashboard.selectedPlotId.value"
          :health="dashboard.health.value"
          :selected-farm="dashboard.selectedFarm.value"
          :selected-plot="dashboard.selectedPlot.value"
          :farms="dashboard.farms.value"
          :farm-plots="dashboard.farmPlots.value"
          :online-device-count="dashboard.onlineDevices.value.length"
          :device-count="dashboard.devices.value.length"
          :temperature-reading="dashboard.latestAirTemperature.value"
          :current-weather="hangzhouWeather.currentWeather.value"
          :weather-loading="hangzhouWeather.weatherLoading.value"
          :weather-error="hangzhouWeather.weatherError.value"
          @farm-change="dashboard.onFarmChange"
          @plot-change="dashboard.onPlotChange"
        />

        <SensorSummaryPanel
          id="sensors"
          :devices="dashboard.plotSensorDevices.value"
          :readings="dashboard.latestSensorReadings.value"
        />

        <section id="diagnosis" class="dashboard-section" aria-labelledby="diagnosis-section-title">
          <header class="dashboard-section__heading">
            <span class="dashboard-section__icon"><PhStethoscope :size="22" weight="duotone" aria-hidden="true" /></span>
            <div>
              <span>AI</span>
              <h2 id="diagnosis-section-title">作物智诊与实时监控</h2>
            </div>
          </header>
          <div class="content-grid content-grid--feature">
            <CameraMonitorPanel
              id="camera"
              :camera="dashboard.selectedCamera.value"
              :detections="dashboard.latestCameraDetections.value"
            />

            <DiagnosisPanel
              id="diagnosis-panel"
              v-model:file="dashboard.diagnosisFile.value"
              :records="dashboard.latestDiagnoses.value"
              :can-upload="dashboard.canUploadDiagnosis.value"
              :diagnosis-busy="dashboard.diagnosisBusy.value"
              @upload="dashboard.uploadDiagnosis"
            />
          </div>
        </section>

        <section id="devices" class="dashboard-section" aria-labelledby="devices-section-title">
          <header class="dashboard-section__heading">
            <span class="dashboard-section__icon"><PhCpu :size="22" weight="duotone" aria-hidden="true" /></span>
            <div>
              <span>CONTROL</span>
              <h2 id="devices-section-title">设备与执行控制</h2>
            </div>
          </header>
          <div class="content-grid">
            <DeviceListPanel
              id="device-list"
              v-model:selected-device-id="dashboard.selectedDeviceId.value"
              :devices="dashboard.plotDevices.value"
            />

            <CommandPanel
              id="command-center"
              v-model:command-device-id="dashboard.commandDeviceId.value"
              v-model:command-type="dashboard.commandType.value"
              v-model:command-duration="dashboard.commandDuration.value"
              :devices="dashboard.plotDevices.value"
              :commands="dashboard.latestCommands.value"
              :selected-command-device="dashboard.selectedCommandDevice.value"
              :device-ready="dashboard.selectedCommandDeviceReady.value"
              :can-submit="dashboard.canSubmitCommand.value"
              :action-busy="dashboard.actionBusy.value"
              @submit-command="dashboard.submitCommand"
            />
          </div>
        </section>

        <section id="profile" class="dashboard-section" aria-labelledby="profile-section-title">
          <header class="dashboard-section__heading">
            <span class="dashboard-section__icon"><PhUserCircle :size="22" weight="duotone" aria-hidden="true" /></span>
            <div>
              <span>RECORDS</span>
              <h2 id="profile-section-title">农场记录与系统状态</h2>
            </div>
          </header>
          <div class="content-grid">
            <AlertQueuePanel
              id="alerts"
              :alerts="dashboard.sortedAlerts.value"
              :active-alert-count="dashboard.activeAlerts.value.length"
              :action-busy="dashboard.actionBusy.value"
              @change-status="dashboard.changeAlertStatus"
            />

            <RealtimeEventsPanel
              id="realtime"
              :events="realtime.realtimeEvents.value"
              :ws-connected="realtime.wsConnected.value"
            />

            <SensorReadingsPanel id="readings" :readings="dashboard.latestReadings.value" />
          </div>
          <AppToolbar :refreshing="dashboard.refreshing.value" @refresh="dashboard.refreshAll()" />
        </section>
      </template>
    </div>
  </main>
</template>

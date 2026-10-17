import { computed, shallowRef, watch } from 'vue'
import { api } from '../api'
import { hasRecentHeartbeat } from '../format'
import { labelCommand, labelCommandStatus } from '../labels'
import type {
  Alert,
  CommandType,
  Device,
  DeviceCommand,
  DiseaseDetection,
  DiagnosisRecord,
  Farm,
  HealthResponse,
  Plot,
  SensorReading,
} from '../types'

export type AlertAction = 'acknowledge' | 'resolve'

function isActuatorDevice(device: Device): boolean {
  return device.device_type === 'pump' || device.device_type === 'grow_light'
}

function isSensorDevice(device: Device): boolean {
  return (
    device.device_type === 'weather_station' ||
    device.device_type === 'soil_sensor' ||
    device.device_type === 'wind_speed_sensor' ||
    device.device_type === 'wind_direction_sensor'
  )
}

function defaultCommandFor(device: Device): CommandType {
  return device.device_type === 'pump' ? 'pump_on' : 'light_on'
}

function deviceAcceptsCommand(device: Device, command: CommandType): boolean {
  if (device.device_type === 'pump') return command === 'pump_on' || command === 'pump_off'
  if (device.device_type === 'grow_light') return command === 'light_on' || command === 'light_off'
  return false
}

export function useFarmDashboard() {
  const loading = shallowRef(true)
  const refreshing = shallowRef(false)
  const actionBusy = shallowRef(false)
  const diagnosisBusy = shallowRef(false)
  const errorMessage = shallowRef('')
  const successMessage = shallowRef('')
  const health = shallowRef<HealthResponse | null>(null)
  const farms = shallowRef<Farm[]>([])
  const plots = shallowRef<Plot[]>([])
  const devices = shallowRef<Device[]>([])
  const readings = shallowRef<SensorReading[]>([])
  const alerts = shallowRef<Alert[]>([])
  const commands = shallowRef<DeviceCommand[]>([])
  const diagnoses = shallowRef<DiagnosisRecord[]>([])
  const detections = shallowRef<DiseaseDetection[]>([])
  const selectedFarmId = shallowRef<number | null>(null)
  const selectedPlotId = shallowRef<number | null>(null)
  const selectedDeviceId = shallowRef<number | null>(null)
  const commandDeviceId = shallowRef<number | null>(null)
  const commandType = shallowRef<CommandType>('pump_on')
  const commandDuration = shallowRef(30)
  const diagnosisFile = shallowRef<File | null>(null)

  const selectedFarm = computed(() => farms.value.find((farm) => farm.id === selectedFarmId.value) ?? null)
  const farmPlots = computed(() => {
    if (!selectedFarmId.value) return plots.value
    return plots.value.filter((plot) => plot.farm_id === selectedFarmId.value)
  })
  const selectedPlot = computed(() => plots.value.find((plot) => plot.id === selectedPlotId.value) ?? null)
  const plotDevices = computed(() => devices.value.filter((device) => device.plot_id === selectedPlotId.value))
  const plotActuatorDevices = computed(() => plotDevices.value.filter(isActuatorDevice))
  const plotSensorDevices = computed(() => plotDevices.value.filter(isSensorDevice))
  const weatherDevice = computed(
    () => plotSensorDevices.value.find((device) => device.device_type === 'weather_station') ?? null,
  )
  const latestSensorReadings = computed(() => {
    const sensorDeviceIds = new Set(plotSensorDevices.value.map((device) => device.id))
    const seen = new Set<string>()

    return readings.value.filter((reading) => {
      if (!sensorDeviceIds.has(reading.device_id)) return false
      const key = `${reading.device_id}:${reading.metric}`
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
  })
  const latestAirTemperature = computed(() => {
    const device = weatherDevice.value
    if (!device) return null
    return (
      latestSensorReadings.value.find(
        (reading) => reading.device_id === device.id && reading.metric === 'air_temperature',
      ) ?? null
    )
  })
  const selectedCamera = computed(() => plotDevices.value.find((device) => device.device_type === 'camera') ?? null)
  const latestCameraDetections = computed(() => {
    const camera = selectedCamera.value
    if (!camera) return []
    return detections.value.filter((detection) => detection.device_id === camera.id).slice(0, 8)
  })
  const onlineDevices = computed(() => devices.value.filter((device) => device.is_online))
  const activeAlerts = computed(() => alerts.value.filter((alert) => alert.status === 'open'))
  const criticalAlerts = computed(() => activeAlerts.value.filter((alert) => alert.severity === 'critical'))
  const latestReadings = computed(() => readings.value.slice(0, 8))
  const latestCommands = computed(() => {
    const deviceIds = new Set(plotDevices.value.map((device) => device.id))
    return commands.value.filter((command) => deviceIds.has(command.device_id)).slice(0, 6)
  })
  const latestDiagnoses = computed(() => diagnoses.value.slice(0, 4))
  const sortedAlerts = computed(() =>
    [...alerts.value].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()),
  )
  const selectedCommandDevice = computed(
    () => plotActuatorDevices.value.find((device) => device.id === commandDeviceId.value) ?? null,
  )
  const selectedCommandDeviceReady = computed(() => {
    const device = selectedCommandDevice.value
    return Boolean(device && hasRecentHeartbeat(device.is_online, device.last_seen_at))
  })
  const commandDurationIsValid = computed(
    () => Number.isInteger(commandDuration.value) && commandDuration.value >= 1 && commandDuration.value <= 300,
  )
  const canSubmitCommand = computed(() => {
    const target = selectedCommandDevice.value
    if (!target || !selectedCommandDeviceReady.value || actionBusy.value || !deviceAcceptsCommand(target, commandType.value)) {
      return false
    }
    const isStartCommand = commandType.value === 'pump_on' || commandType.value === 'light_on'
    return !isStartCommand || commandDurationIsValid.value
  })
  const canUploadDiagnosis = computed(() => Boolean(selectedPlotId.value && diagnosisFile.value) && !diagnosisBusy.value)
  const systemStatusLabel = computed(() => {
    if (!health.value) return '未连接'
    if (health.value.status === 'ok') return '后端正常'
    return '后端降级'
  })
  const fieldRiskLabel = computed(() => {
    if (criticalAlerts.value.length > 0) return `${criticalAlerts.value.length} 个严重告警`
    if (activeAlerts.value.length > 0) return `${activeAlerts.value.length} 个待处理告警`
    return '当前无待处理告警'
  })

  function setSuccess(message: string): void {
    successMessage.value = message
    window.setTimeout(() => {
      if (successMessage.value === message) successMessage.value = ''
    }, 4200)
  }

  function setError(message: string): void {
    errorMessage.value = message
  }

  function clearError(): void {
    errorMessage.value = ''
  }

  function chooseDefaults(): void {
    if (!selectedFarmId.value || !farms.value.some((farm) => farm.id === selectedFarmId.value)) {
      selectedFarmId.value = farms.value[0]?.id ?? null
    }

    const availablePlots = selectedFarmId.value
      ? plots.value.filter((plot) => plot.farm_id === selectedFarmId.value)
      : plots.value
    if (!selectedPlotId.value || !availablePlots.some((plot) => plot.id === selectedPlotId.value)) {
      selectedPlotId.value = availablePlots[0]?.id ?? null
    }

    const availableDevices = selectedPlotId.value
      ? devices.value.filter((device) => device.plot_id === selectedPlotId.value)
      : devices.value
    if (!selectedDeviceId.value || !availableDevices.some((device) => device.id === selectedDeviceId.value)) {
      selectedDeviceId.value = availableDevices[0]?.id ?? null
    }
    const availableActuators = availableDevices.filter(isActuatorDevice)
    if (!commandDeviceId.value || !availableActuators.some((device) => device.id === commandDeviceId.value)) {
      const preferredActuator = availableActuators.find((device) => device.device_type === 'pump') ?? availableActuators[0]
      commandDeviceId.value = preferredActuator?.id ?? null
      if (preferredActuator) commandType.value = defaultCommandFor(preferredActuator)
    }
  }

  watch(selectedCommandDevice, (device) => {
    if (device && !deviceAcceptsCommand(device, commandType.value)) {
      commandType.value = defaultCommandFor(device)
    }
  })

  async function loadCoreData(): Promise<void> {
    const [healthData, farmData, plotData, deviceData, alertData, commandData, diagnosisData] = await Promise.all([
      api.health(),
      api.farms(),
      api.plots(),
      api.devices(),
      api.alerts(),
      api.commands(),
      api.diagnoses(),
    ])

    health.value = healthData
    farms.value = farmData
    plots.value = plotData
    devices.value = deviceData
    alerts.value = alertData
    commands.value = commandData.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    diagnoses.value = diagnosisData.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    chooseDefaults()
  }

  async function loadPlotData(): Promise<void> {
    if (!selectedPlotId.value) {
      readings.value = []
      detections.value = []
      return
    }

    const [readingData, diagnosisData, detectionData] = await Promise.all([
      api.telemetry({ plotId: selectedPlotId.value, limit: 80 }),
      api.diagnoses(selectedPlotId.value),
      api.detections({ plotId: selectedPlotId.value, limit: 50 }),
    ])

    readings.value = readingData.sort((a, b) => new Date(b.recorded_at).getTime() - new Date(a.recorded_at).getTime())
    diagnoses.value = diagnosisData.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    detections.value = detectionData.sort(
      (a, b) => new Date(b.detected_at).getTime() - new Date(a.detected_at).getTime(),
    )
  }

  async function loadAll(): Promise<void> {
    clearError()
    loading.value = true
    try {
      await loadCoreData()
      await loadPlotData()
    } catch (error) {
      setError(error instanceof Error ? error.message : '连接后端失败，请确认后端已经启动。')
    } finally {
      loading.value = false
    }
  }

  async function refreshAll(silent = false): Promise<void> {
    if (!silent) refreshing.value = true
    try {
      await loadCoreData()
      await loadPlotData()
    } catch (error) {
      setError(error instanceof Error ? error.message : '刷新失败，请检查后端服务。')
    } finally {
      refreshing.value = false
    }
  }

  let sensorRefreshInFlight: Promise<void> | null = null

  async function refreshSensorData(): Promise<void> {
    if (sensorRefreshInFlight) return sensorRefreshInFlight

    const plotId = selectedPlotId.value
    sensorRefreshInFlight = (async () => {
      if (!plotId) {
        readings.value = []
        return
      }

      const [deviceData, readingData] = await Promise.all([
        api.devices(),
        api.telemetry({ plotId, limit: 80 }),
      ])
      devices.value = deviceData
      chooseDefaults()

      if (selectedPlotId.value === plotId) {
        readings.value = readingData.sort(
          (a, b) => new Date(b.recorded_at).getTime() - new Date(a.recorded_at).getTime(),
        )
      }
    })()

    try {
      await sensorRefreshInFlight
    } catch (error) {
      setError(error instanceof Error ? error.message : '刷新传感器数据失败。')
    } finally {
      sensorRefreshInFlight = null
    }
  }

  let actuatorRefreshInFlight: Promise<void> | null = null

  async function refreshActuatorData(): Promise<void> {
    if (actuatorRefreshInFlight) return actuatorRefreshInFlight

    actuatorRefreshInFlight = (async () => {
      const [deviceData, commandData] = await Promise.all([
        api.devices(),
        api.commands(),
      ])
      devices.value = deviceData
      commands.value = commandData.sort(
        (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
      )
      chooseDefaults()
    })()

    try {
      await actuatorRefreshInFlight
    } catch (error) {
      setError(error instanceof Error ? error.message : '刷新继电器状态失败。')
    } finally {
      actuatorRefreshInFlight = null
    }
  }

  async function onFarmChange(): Promise<void> {
    selectedPlotId.value = farmPlots.value[0]?.id ?? null
    selectedDeviceId.value = null
    commandDeviceId.value = null
    chooseDefaults()
    await loadPlotData()
  }

  async function onPlotChange(): Promise<void> {
    selectedDeviceId.value = plotSensorDevices.value[0]?.id ?? plotDevices.value[0]?.id ?? null
    commandDeviceId.value = null
    chooseDefaults()
    await loadPlotData()
  }

  async function submitCommand(): Promise<void> {
    const target = selectedCommandDevice.value
    if (!target) {
      setError('请选择水泵或作物补光灯，传感器不能接收控制命令。')
      return
    }
    if (!deviceAcceptsCommand(target, commandType.value)) {
      setError('当前命令与设备类型不匹配。')
      return
    }
    if (!selectedCommandDeviceReady.value) {
      setError('继电器 Agent 当前离线；请插入 USB 继电器，连接恢复后再发送命令。')
      return
    }
    const isStartCommand = commandType.value === 'pump_on' || commandType.value === 'light_on'
    if (isStartCommand && !commandDurationIsValid.value) {
      setError('开启设备的持续时间必须是 1–300 秒之间的整数。')
      return
    }

    actionBusy.value = true
    try {
      const parameters =
        isStartCommand
          ? { duration_seconds: commandDuration.value }
          : {}
      const created = await api.createCommand({
        device_id: target.id,
        command_type: commandType.value,
        parameters,
      })
      commands.value = [created, ...commands.value].slice(0, 20)
      setSuccess(`${labelCommand(commandType.value)}命令已创建，当前状态：${labelCommandStatus(created.status)}。`)
    } catch (error) {
      setError(error instanceof Error ? error.message : '创建控制命令失败。')
    } finally {
      actionBusy.value = false
    }
  }

  async function changeAlertStatus(alert: Alert, action: AlertAction): Promise<void> {
    actionBusy.value = true
    try {
      const updated = action === 'acknowledge' ? await api.acknowledgeAlert(alert.id) : await api.resolveAlert(alert.id)
      alerts.value = alerts.value.map((item) => (item.id === updated.id ? updated : item))
      setSuccess(action === 'acknowledge' ? '告警已确认。' : '告警已解决。')
    } catch (error) {
      setError(error instanceof Error ? error.message : '更新告警状态失败。')
    } finally {
      actionBusy.value = false
    }
  }

  function setDiagnosisFile(file: File | null): void {
    diagnosisFile.value = file
  }

  async function uploadDiagnosis(): Promise<void> {
    if (!selectedPlotId.value || !diagnosisFile.value) {
      setError('请选择地块和图片后再上传。')
      return
    }

    diagnosisBusy.value = true
    try {
      const created = await api.uploadDiagnosis(selectedPlotId.value, diagnosisFile.value)
      diagnoses.value = [created, ...diagnoses.value]
      diagnosisFile.value = null
      setSuccess('诊断图片已上传，后端已返回演示诊断结果。')
    } catch (error) {
      setError(error instanceof Error ? error.message : '上传诊断图片失败。')
    } finally {
      diagnosisBusy.value = false
    }
  }

  return {
    loading,
    refreshing,
    actionBusy,
    diagnosisBusy,
    errorMessage,
    successMessage,
    health,
    farms,
    plots,
    devices,
    readings,
    alerts,
    commands,
    diagnoses,
    detections,
    selectedFarmId,
    selectedPlotId,
    selectedDeviceId,
    commandDeviceId,
    commandType,
    commandDuration,
    diagnosisFile,
    selectedFarm,
    farmPlots,
    selectedPlot,
    plotDevices,
    plotActuatorDevices,
    plotSensorDevices,
    weatherDevice,
    latestSensorReadings,
    latestAirTemperature,
    selectedCamera,
    latestCameraDetections,
    onlineDevices,
    activeAlerts,
    criticalAlerts,
    latestReadings,
    latestCommands,
    latestDiagnoses,
    sortedAlerts,
    selectedCommandDevice,
    selectedCommandDeviceReady,
    canSubmitCommand,
    canUploadDiagnosis,
    systemStatusLabel,
    fieldRiskLabel,
    setError,
    clearError,
    loadAll,
    refreshAll,
    refreshSensorData,
    refreshActuatorData,
    onFarmChange,
    onPlotChange,
    submitCommand,
    changeAlertStatus,
    setDiagnosisFile,
    uploadDiagnosis,
  }
}

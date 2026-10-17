import type { ActuatorState, AlertSeverity, AlertStatus, CommandStatus, CommandType } from './types'

export const metricLabels: Record<string, string> = {
  air_temperature: '空气温度',
  air_humidity: '空气湿度',
  illumination: '光照',
  light_intensity: '光照强度',
  wind_speed: '风速',
  wind_direction: '风向',
  rainfall: '降雨量',
  soil_temperature: '土壤温度',
  soil_moisture: '土壤湿度',
  soil_ec: '电导率',
  soil_ph: '土壤 pH',
  soil_nitrogen: '土壤氮',
  soil_phosphorus: '土壤磷',
  soil_potassium: '土壤钾',
}

export const deviceTypeLabels: Record<string, string> = {
  weather_station: '气象仪',
  wind_speed_sensor: '风速传感器',
  wind_direction_sensor: '风向传感器',
  soil_sensor: '土壤传感器',
  pump: '水泵',
  grow_light: '作物补光灯',
  camera: 'D435i 深度相机',
}

export const commandLabels: Record<CommandType, string> = {
  pump_on: '开启水泵',
  pump_off: '关闭水泵',
  light_on: '开启作物补光灯',
  light_off: '关闭作物补光灯',
}

export const commandStatusLabels: Record<CommandStatus, string> = {
  pending: '等待执行',
  sent: '等待执行',
  acknowledged: '执行中',
  succeeded: '已成功',
  failed: '失败',
}

export const actuatorStateLabels: Record<ActuatorState, string> = {
  on: 'ON',
  off: 'OFF',
  unknown: '未知',
}

export const alertStatusLabels: Record<AlertStatus, string> = {
  open: '待处理',
  acknowledged: '已确认',
  resolved: '已解决',
}

export const severityLabels: Record<AlertSeverity, string> = {
  info: '提示',
  warning: '预警',
  critical: '严重',
}

export function labelMetric(metric: string): string {
  return metricLabels[metric] ?? metric
}

export function labelDeviceType(type: string): string {
  return deviceTypeLabels[type] ?? type
}

export function labelActuatorState(state: ActuatorState): string {
  return actuatorStateLabels[state]
}

export function labelCommand(type: string): string {
  return commandLabels[type as CommandType] ?? type
}

export function labelCommandStatus(status: string): string {
  return commandStatusLabels[status as CommandStatus] ?? status
}

export function labelAlertStatus(status: string): string {
  return alertStatusLabels[status as AlertStatus] ?? status
}

export function labelSeverity(severity: string): string {
  return severityLabels[severity as AlertSeverity] ?? severity
}

export function labelReadingQuality(quality: string): string {
  const labels: Record<string, string> = {
    good: '正常',
    suspect: '待核对',
    bad: '异常',
  }
  return labels[quality] ?? quality
}

export function labelUnit(unit: string): string {
  const units: Record<string, string> = {
    celsius: '℃',
    percent: '%',
    lux: 'lux',
    ph: 'pH',
    millimeter: 'mm',
    microsiemens_per_centimeter: 'μS/cm',
    milligram_per_kilogram: 'mg/kg',
    meters_per_second: 'm/s',
    degree: '°',
  }
  return units[unit] ?? unit
}

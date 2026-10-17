export type HealthResponse = {
  app: string
  status: 'ok' | 'degraded' | string
  database: string
  mqtt: string
  timestamp: string
}

export type Farm = {
  id: number
  name: string
  location: string
  description: string
  created_at: string
}

export type Plot = {
  id: number
  farm_id: number
  name: string
  crop_type: string
  area: number
  created_at: string
}

export type ActuatorState = 'on' | 'off' | 'unknown'

export type Device = {
  id: number
  plot_id: number
  device_code: string
  name: string
  device_type: string
  communication_type: string
  is_online: boolean
  last_seen_at: string | null
  actuator_state: ActuatorState
  state_updated_at: string | null
  camera_model: string | null
  stream_url: string | null
  capabilities_json: string[]
  metadata_json: Record<string, unknown>
  created_at: string
}

export type DetectionSeverity = 'healthy' | 'mild' | 'moderate' | 'severe' | 'unknown'

export type DiseaseDetection = {
  id: number
  device_id: number
  device_code: string
  class_name: string
  disease_name: string
  cause: string
  severity: DetectionSeverity | string
  treatment: string[]
  confidence: number
  distance_m: number | null
  bbox: Record<string, number>
  image_url: string | null
  detected_at: string
  received_at: string
}

export type SensorReading = {
  id: number
  device_id: number
  metric: string
  value: number
  unit: string
  quality: 'good' | 'suspect' | 'bad' | string
  recorded_at: string
  received_at: string
}

export type PlotMetricSummary = {
  metric: string
  count: number
  minimum: number
  maximum: number
  average: number
  latest: number
  unit: string
}

export type AlertStatus = 'open' | 'acknowledged' | 'resolved'
export type AlertSeverity = 'info' | 'warning' | 'critical'

export type Alert = {
  id: number
  rule_id: number
  device_id: number
  reading_id: number
  severity: AlertSeverity | string
  message: string
  status: AlertStatus | string
  created_at: string
  updated_at: string
}

export type CommandType = 'pump_on' | 'pump_off' | 'light_on' | 'light_off'
export type CommandStatus = 'pending' | 'sent' | 'acknowledged' | 'succeeded' | 'failed'

export type DeviceCommand = {
  id: number
  device_id: number
  command_type: CommandType | string
  parameters_json: Record<string, unknown>
  status: CommandStatus | string
  created_at: string
  updated_at: string
}

export type DiagnosisRecord = {
  id: number
  plot_id: number
  image_path: string
  crop_type: string
  growth_stage: string
  health_status: string
  result_text: string
  created_at: string
}

export type RealtimeEvent = {
  id: number
  event: string
  data: Record<string, unknown>
  receivedAt: string
}

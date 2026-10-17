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
  PlotMetricSummary,
  SensorReading,
} from './types'

const directApiBase = import.meta.env.VITE_API_BASE_URL || 'http://172.20.10.2:8000'
const directWsUrl = import.meta.env.VITE_WS_URL || 'ws://172.20.10.2:8000/ws'

export const apiBaseUrl = import.meta.env.DEV ? '' : directApiBase.replace(/\/$/, '')
export const wsUrl = import.meta.env.DEV ? `${window.location.origin.replace(/^http/, 'ws')}/ws` : directWsUrl
export const apiEndpointLabel = (() => {
  try {
    return new URL(directApiBase).host
  } catch {
    return directApiBase.replace(/^https?:\/\//, '').replace(/\/$/, '')
  }
})()

class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    headers: {
      Accept: 'application/json',
      ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...options.headers,
    },
    ...options,
  })

  if (!response.ok) {
    let message = `请求失败，HTTP ${response.status}`
    try {
      const body = await response.json()
      if (typeof body.detail === 'string') {
        message = body.detail
      }
    } catch {
      message = response.statusText || message
    }
    throw new ApiError(message, response.status)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json() as Promise<T>
}

function buildQuery(params: Record<string, string | number | boolean | null | undefined>): string {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== '') {
      search.set(key, String(value))
    }
  })
  const query = search.toString()
  return query ? `?${query}` : ''
}

export const api = {
  health: () => request<HealthResponse>('/api/v1/health'),
  farms: () => request<Farm[]>('/api/v1/farms'),
  plots: (farmId?: number) => request<Plot[]>(`/api/v1/plots${buildQuery({ farm_id: farmId })}`),
  devices: (plotId?: number) => request<Device[]>(`/api/v1/devices${buildQuery({ plot_id: plotId })}`),
  detections: (params: { plotId?: number; deviceId?: number; limit?: number } = {}) =>
    request<DiseaseDetection[]>(
      `/api/v1/detections${buildQuery({
        plot_id: params.plotId,
        device_id: params.deviceId,
        limit: params.limit ?? 50,
      })}`,
    ),
  telemetry: (params: { plotId?: number; deviceId?: number; limit?: number }) =>
    request<SensorReading[]>(
      `/api/v1/telemetry${buildQuery({
        plot_id: params.plotId,
        device_id: params.deviceId,
        limit: params.limit ?? 80,
      })}`,
    ),
  summary: (plotId: number) => request<PlotMetricSummary[]>(`/api/v1/telemetry/summary/${plotId}`),
  alerts: () => request<Alert[]>('/api/v1/alerts'),
  acknowledgeAlert: (alertId: number) => request<Alert>(`/api/v1/alerts/${alertId}/acknowledge`, { method: 'POST' }),
  resolveAlert: (alertId: number) => request<Alert>(`/api/v1/alerts/${alertId}/resolve`, { method: 'POST' }),
  commands: () => request<DeviceCommand[]>('/api/v1/commands'),
  createCommand: (payload: { device_id: number; command_type: CommandType; parameters: Record<string, unknown> }) =>
    request<DeviceCommand>('/api/v1/commands', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  diagnoses: (plotId?: number) => request<DiagnosisRecord[]>(`/api/v1/diagnosis${buildQuery({ plot_id: plotId })}`),
  uploadDiagnosis: (plotId: number, file: File) => {
    const form = new FormData()
    form.set('plot_id', String(plotId))
    form.set('image', file)
    return request<DiagnosisRecord>('/api/v1/diagnosis', {
      method: 'POST',
      body: form,
    })
  },
}

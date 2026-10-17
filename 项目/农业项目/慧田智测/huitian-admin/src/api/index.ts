import { query, request } from './client'
import type { AlertItem, AlertRule, AlertRulePayload, Device, DeviceCommand, DeviceCreatePayload, DeviceUpdatePayload, DiagnosisRecord, Farm, FarmPayload, HealthResponse, Plot, PlotMetricSummary, PlotPayload, SensorReading } from '@/types'

const root = '/api/v1'
const json = (value: unknown): RequestInit => ({ body: JSON.stringify(value) })

export const api = {
  health: () => request<HealthResponse>(`${root}/health`),
  farms: () => request<Farm[]>(`${root}/farms`),
  createFarm: (value: FarmPayload) => request<Farm>(`${root}/farms`, { method: 'POST', ...json(value) }),
  updateFarm: (id: number, value: FarmPayload) => request<Farm>(`${root}/farms/${id}`, { method: 'PUT', ...json(value) }),
  deleteFarm: (id: number) => request<void>(`${root}/farms/${id}`, { method: 'DELETE' }),
  plots: (farmId?: number) => request<Plot[]>(`${root}/plots${query({ farm_id: farmId })}`),
  createPlot: (value: PlotPayload) => request<Plot>(`${root}/plots`, { method: 'POST', ...json(value) }),
  updatePlot: (id: number, value: PlotPayload) => request<Plot>(`${root}/plots/${id}`, { method: 'PUT', ...json(value) }),
  deletePlot: (id: number) => request<void>(`${root}/plots/${id}`, { method: 'DELETE' }),
  devices: (plotId?: number, online?: boolean) => request<Device[]>(`${root}/devices${query({ plot_id: plotId, is_online: online })}`),
  createDevice: (value: DeviceCreatePayload) => request<Device>(`${root}/devices`, { method: 'POST', ...json(value) }),
  updateDevice: (id: number, value: DeviceUpdatePayload) => request<Device>(`${root}/devices/${id}`, { method: 'PUT', ...json(value) }),
  deleteDevice: (id: number) => request<void>(`${root}/devices/${id}`, { method: 'DELETE' }),
  telemetry: (filters: { plotId?: number; deviceId?: number; limit?: number }) => request<SensorReading[]>(`${root}/telemetry${query({ plot_id: filters.plotId, device_id: filters.deviceId, limit: filters.limit || 100 })}`),
  summary: (plotId: number) => request<PlotMetricSummary[]>(`${root}/telemetry/summary/${plotId}`),
  rules: (plotId?: number) => request<AlertRule[]>(`${root}/alerts/rules${query({ plot_id: plotId })}`),
  createRule: (value: AlertRulePayload) => request<AlertRule>(`${root}/alerts/rules`, { method: 'POST', ...json(value) }),
  updateRule: (id: number, value: AlertRulePayload) => request<AlertRule>(`${root}/alerts/rules/${id}`, { method: 'PUT', ...json(value) }),
  deleteRule: (id: number) => request<void>(`${root}/alerts/rules/${id}`, { method: 'DELETE' }),
  alerts: (status?: string, severity?: string) => request<AlertItem[]>(`${root}/alerts${query({ status_filter: status, severity })}`),
  acknowledgeAlert: (id: number) => request<AlertItem>(`${root}/alerts/${id}/acknowledge`, { method: 'POST' }),
  resolveAlert: (id: number) => request<AlertItem>(`${root}/alerts/${id}/resolve`, { method: 'POST' }),
  commands: () => request<DeviceCommand[]>(`${root}/commands`),
  createCommand: (value: { device_id: number; command_type: string; parameters: Record<string, unknown> }) => request<DeviceCommand>(`${root}/commands`, { method: 'POST', ...json(value) }),
  diagnoses: (plotId?: number) => request<DiagnosisRecord[]>(`${root}/diagnosis${query({ plot_id: plotId })}`),
}

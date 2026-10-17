export interface HealthResponse { app: string; status: string; database: string; mqtt: string; timestamp: string }
export interface Farm { id: number; name: string; location: string; description: string; created_at: string }
export interface FarmPayload { name: string; location: string; description: string }
export interface Plot { id: number; farm_id: number; name: string; crop_type: string; area: number; created_at: string }
export interface PlotPayload { farm_id: number; name: string; crop_type: string; area: number }
export interface Device { id: number; plot_id: number; device_code: string; name: string; device_type: string; communication_type: string; is_online: boolean; last_seen_at: string | null; actuator_state: 'on' | 'off' | 'unknown'; state_updated_at: string | null; created_at: string }
export interface DeviceCreatePayload { plot_id: number; device_code: string; name: string; device_type: string; communication_type: 'http' }
export interface DeviceUpdatePayload { plot_id: number; name: string; device_type: string; communication_type: 'http'; is_online: boolean }
export interface SensorReading { id: number; device_id: number; metric: string; value: number; unit: string; quality: string; recorded_at: string; received_at: string }
export interface PlotMetricSummary { metric: string; count: number; minimum: number; maximum: number; average: number; latest: number; unit: string }
export interface AlertRule { id: number; plot_id: number; name: string; metric: string; operator: string; threshold: number; severity: string; enabled: boolean; message: string; created_at: string }
export interface AlertRulePayload { plot_id: number; name: string; metric: string; operator: 'gt' | 'gte' | 'lt' | 'lte'; threshold: number; severity: 'info' | 'warning' | 'critical'; enabled: boolean; message: string }
export interface AlertItem { id: number; rule_id: number; device_id: number; reading_id: number; severity: string; message: string; status: string; created_at: string; updated_at: string }
export interface DeviceCommand { id: number; device_id: number; command_type: string; parameters_json: Record<string, unknown>; status: string; created_at: string; updated_at: string }
export interface DiagnosisRecord { id: number; plot_id: number; image_path: string; crop_type: string; growth_stage: string; health_status: string; result_text: string; created_at: string }

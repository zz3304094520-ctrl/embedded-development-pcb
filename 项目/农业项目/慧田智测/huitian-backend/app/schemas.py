from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    message: str


class FarmCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    location: str = Field(default="", max_length=200)
    description: str = ""


class FarmUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    location: str | None = Field(default=None, max_length=200)
    description: str | None = None


class FarmResponse(OrmModel):
    id: int
    name: str
    location: str
    description: str
    created_at: datetime


class PlotCreate(BaseModel):
    farm_id: int
    name: str = Field(min_length=1, max_length=100)
    crop_type: str = Field(default="番茄", max_length=50)
    area: float = Field(default=0, ge=0)


class PlotUpdate(BaseModel):
    farm_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)
    crop_type: str | None = Field(default=None, max_length=50)
    area: float | None = Field(default=None, ge=0)


class PlotResponse(OrmModel):
    id: int
    farm_id: int
    name: str
    crop_type: str
    area: float
    created_at: datetime


CommunicationType = Literal["http"]
ActuatorState = Literal["on", "off", "unknown"]


class DeviceCreate(BaseModel):
    plot_id: int
    device_code: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=100)
    device_type: str = Field(min_length=1, max_length=50)
    communication_type: CommunicationType = "http"


class DeviceUpdate(BaseModel):
    plot_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)
    device_type: str | None = Field(default=None, min_length=1, max_length=50)
    communication_type: CommunicationType | None = None
    is_online: bool | None = None


class DeviceResponse(OrmModel):
    id: int
    plot_id: int
    device_code: str
    name: str
    device_type: str
    communication_type: str
    is_online: bool
    last_seen_at: datetime | None
    actuator_state: ActuatorState
    state_updated_at: datetime | None
    camera_model: str | None
    stream_url: str | None
    capabilities_json: list[str]
    metadata_json: dict[str, Any]
    created_at: datetime

    @field_validator("last_seen_at", "state_updated_at", "created_at", mode="before")
    @classmethod
    def assume_sqlite_datetimes_are_utc(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class HeartbeatRequest(BaseModel):
    actuator_state: ActuatorState | None = None


class HeartbeatResponse(BaseModel):
    device_code: str
    is_online: bool
    last_seen_at: datetime
    actuator_state: ActuatorState
    state_updated_at: datetime | None

    @field_validator("last_seen_at", "state_updated_at", mode="before")
    @classmethod
    def assume_sqlite_datetimes_are_utc(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class DeviceStatusRequest(BaseModel):
    is_online: bool


class DeviceStatusResponse(BaseModel):
    device_code: str
    is_online: bool
    last_seen_at: datetime | None

    @field_validator("last_seen_at", mode="before")
    @classmethod
    def assume_sqlite_datetime_is_utc(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class ReadingInput(BaseModel):
    metric: str = Field(min_length=1, max_length=80)
    value: float
    unit: str = Field(default="", max_length=30)
    quality: Literal["good", "suspect", "bad"] = "good"


class TelemetryCreate(BaseModel):
    device_code: str
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    readings: list[ReadingInput] = Field(min_length=1, max_length=100)

    @field_validator("recorded_at")
    @classmethod
    def recorded_at_must_have_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("recorded_at 必须包含时区，例如结尾使用 Z")
        return value.astimezone(timezone.utc)


class SensorReadingResponse(OrmModel):
    id: int
    device_id: int
    metric: str
    value: float
    unit: str
    quality: str
    recorded_at: datetime
    received_at: datetime


class TelemetryIngestResponse(BaseModel):
    device_code: str
    saved_count: int
    alert_count: int
    readings: list[SensorReadingResponse]


class LatestTelemetryItem(OrmModel):
    metric: str
    value: float
    unit: str
    quality: str
    recorded_at: datetime


class LatestTelemetryResponse(BaseModel):
    device_code: str
    readings: list[LatestTelemetryItem]


class PlotMetricSummary(BaseModel):
    metric: str
    count: int
    minimum: float
    maximum: float
    average: float
    latest: float
    unit: str


AlertOperator = Literal["gt", "gte", "lt", "lte"]
AlertSeverity = Literal["info", "warning", "critical"]


class AlertRuleCreate(BaseModel):
    plot_id: int
    name: str = Field(min_length=1, max_length=100)
    metric: str = Field(min_length=1, max_length=80)
    operator: AlertOperator
    threshold: float
    severity: AlertSeverity = "warning"
    enabled: bool = True
    message: str = Field(min_length=1, max_length=300)


class AlertRuleUpdate(BaseModel):
    plot_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)
    metric: str | None = Field(default=None, min_length=1, max_length=80)
    operator: AlertOperator | None = None
    threshold: float | None = None
    severity: AlertSeverity | None = None
    enabled: bool | None = None
    message: str | None = Field(default=None, min_length=1, max_length=300)


class AlertRuleResponse(OrmModel):
    id: int
    plot_id: int
    name: str
    metric: str
    operator: str
    threshold: float
    severity: str
    enabled: bool
    message: str
    created_at: datetime


class AlertResponse(OrmModel):
    id: int
    rule_id: int
    device_id: int
    reading_id: int
    severity: str
    message: str
    status: str
    created_at: datetime
    updated_at: datetime


CommandType = Literal["pump_on", "pump_off", "light_on", "light_off"]


class CommandCreate(BaseModel):
    device_id: int
    command_type: CommandType
    parameters: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_parameters(self) -> "CommandCreate":
        if self.command_type in {"pump_on", "light_on"}:
            if set(self.parameters) != {"duration_seconds"}:
                raise ValueError("开启命令 parameters 仅允许 duration_seconds")
            duration = self.parameters["duration_seconds"]
            if isinstance(duration, bool) or not isinstance(duration, int):
                raise ValueError("duration_seconds 必须是整数")
            if not 1 <= duration <= 300:
                raise ValueError("duration_seconds 必须在 1 到 300 秒之间")
        elif self.parameters:
            raise ValueError("关闭命令 parameters 必须为空")
        return self


class CommandAck(BaseModel):
    status: Literal["acknowledged", "succeeded", "failed"]
    actuator_state: ActuatorState | None = None


class DeviceCommandResponse(OrmModel):
    id: int
    device_id: int
    command_type: str
    parameters_json: dict[str, Any]
    status: str
    created_at: datetime
    updated_at: datetime


class DiagnosisResponse(OrmModel):
    id: int
    plot_id: int
    image_path: str
    crop_type: str
    growth_stage: str
    health_status: str
    result_text: str
    created_at: datetime


DetectionSeverity = Literal["healthy", "mild", "moderate", "severe", "unknown"]


class BoundingBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float

    @model_validator(mode="after")
    def validate_coordinates(self) -> "BoundingBox":
        if self.x2 < self.x1 or self.y2 < self.y1:
            raise ValueError("bbox 的右下坐标不能小于左上坐标")
        return self


class EdgeCameraRegistration(BaseModel):
    user_id: int | None = None
    device_code: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
    device_name: str = Field(default="Jetson D435i 智能巡检节点", min_length=1, max_length=100)
    camera_model: str = Field(default="Intel RealSense D435i", min_length=1, max_length=100)
    stream_url: str = Field(min_length=8, max_length=500, pattern=r"^https?://")
    ip_address: str | None = Field(default=None, max_length=100)
    service_port: int | None = Field(default=None, ge=1, le=65535)
    camera_online: bool = False
    capabilities: list[str] = Field(default_factory=list, max_length=30)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EdgeCameraRegistrationResponse(BaseModel):
    success: bool = True
    device_id: int
    device_code: str
    message: str = "相机状态已更新"


class DiseaseDetectionCreate(BaseModel):
    user_id: int | None = None
    device_code: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
    class_name: str = Field(min_length=1, max_length=100)
    disease_name: str = Field(min_length=1, max_length=150)
    cause: str = Field(default="", max_length=2000)
    severity: DetectionSeverity = "unknown"
    treatment: list[str] = Field(default_factory=list, max_length=20)
    confidence: float = Field(ge=0, le=1)
    distance_m: float | None = Field(default=None, ge=0, le=100)
    bbox: BoundingBox
    image_url: str | None = Field(default=None, max_length=500)
    detected_at: datetime

    @field_validator("detected_at")
    @classmethod
    def detected_at_must_have_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("detected_at 必须包含时区")
        return value.astimezone(timezone.utc)


class DiseaseDetectionResponse(BaseModel):
    id: int
    device_id: int
    device_code: str
    class_name: str
    disease_name: str
    cause: str
    severity: str
    treatment: list[str]
    confidence: float
    distance_m: float | None
    bbox: dict[str, float]
    image_url: str | None
    detected_at: datetime
    received_at: datetime

    @field_validator("detected_at", "received_at", mode="before")
    @classmethod
    def assume_sqlite_datetimes_are_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class DiseaseDetectionCreateResponse(BaseModel):
    success: bool = True
    detection_id: int
    message: str = "识别结果已保存"


class HealthResponse(BaseModel):
    app: str
    status: str
    database: str
    mqtt: str
    timestamp: datetime

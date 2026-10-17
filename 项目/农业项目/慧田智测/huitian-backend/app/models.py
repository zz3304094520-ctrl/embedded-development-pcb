from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Farm(Base):
    __tablename__ = "farms"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    location: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    plots: Mapped[list[Plot]] = relationship(back_populates="farm")


class Plot(Base):
    __tablename__ = "plots"

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    crop_type: Mapped[str] = mapped_column(String(50), default="番茄")
    area: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    farm: Mapped[Farm] = relationship(back_populates="plots")
    devices: Mapped[list[Device]] = relationship(back_populates="plot")
    alert_rules: Mapped[list[AlertRule]] = relationship(back_populates="plot")
    diagnoses: Mapped[list[DiagnosisRecord]] = relationship(back_populates="plot")


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    plot_id: Mapped[int] = mapped_column(ForeignKey("plots.id", ondelete="RESTRICT"), index=True)
    device_code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    device_type: Mapped[str] = mapped_column(String(50), nullable=False)
    communication_type: Mapped[str] = mapped_column(String(30), default="http")
    is_online: Mapped[bool] = mapped_column(Boolean, default=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actuator_state: Mapped[str] = mapped_column(
        String(20), default="unknown", server_default="unknown"
    )
    state_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    camera_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    stream_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    capabilities_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    plot: Mapped[Plot] = relationship(back_populates="devices")
    readings: Mapped[list[SensorReading]] = relationship(back_populates="device")
    alerts: Mapped[list[Alert]] = relationship(back_populates="device")
    commands: Mapped[list[DeviceCommand]] = relationship(back_populates="device")
    detections: Mapped[list[DiseaseDetection]] = relationship(back_populates="device")


class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="RESTRICT"), index=True)
    metric: Mapped[str] = mapped_column(String(80), index=True)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(30), default="")
    quality: Mapped[str] = mapped_column(String(20), default="good")
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    device: Mapped[Device] = relationship(back_populates="readings")
    alerts: Mapped[list[Alert]] = relationship(back_populates="reading")


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    plot_id: Mapped[int] = mapped_column(ForeignKey("plots.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    metric: Mapped[str] = mapped_column(String(80), index=True)
    operator: Mapped[str] = mapped_column(String(10))
    threshold: Mapped[float] = mapped_column(Float)
    severity: Mapped[str] = mapped_column(String(20), default="warning")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    message: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    plot: Mapped[Plot] = relationship(back_populates="alert_rules")
    alerts: Mapped[list[Alert]] = relationship(back_populates="rule")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    rule_id: Mapped[int] = mapped_column(ForeignKey("alert_rules.id", ondelete="RESTRICT"), index=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="RESTRICT"), index=True)
    reading_id: Mapped[int] = mapped_column(
        ForeignKey("sensor_readings.id", ondelete="RESTRICT"), index=True
    )
    severity: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    rule: Mapped[AlertRule] = relationship(back_populates="alerts")
    device: Mapped[Device] = relationship(back_populates="alerts")
    reading: Mapped[SensorReading] = relationship(back_populates="alerts")


class DeviceCommand(Base):
    __tablename__ = "device_commands"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="RESTRICT"), index=True)
    command_type: Mapped[str] = mapped_column(String(50))
    parameters_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    device: Mapped[Device] = relationship(back_populates="commands")


class DiagnosisRecord(Base):
    __tablename__ = "diagnosis_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    plot_id: Mapped[int] = mapped_column(ForeignKey("plots.id", ondelete="RESTRICT"), index=True)
    image_path: Mapped[str] = mapped_column(String(300))
    crop_type: Mapped[str] = mapped_column(String(50))
    growth_stage: Mapped[str] = mapped_column(String(50))
    health_status: Mapped[str] = mapped_column(String(100))
    result_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    plot: Mapped[Plot] = relationship(back_populates="diagnoses")


class DiseaseDetection(Base):
    __tablename__ = "disease_detections"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="RESTRICT"), index=True)
    class_name: Mapped[str] = mapped_column(String(100), index=True)
    disease_name: Mapped[str] = mapped_column(String(150))
    cause: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(20), index=True)
    treatment_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(Float)
    distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_json: Mapped[dict[str, float]] = mapped_column(JSON, default=dict)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    device: Mapped[Device] = relationship(back_populates="detections")

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models, schemas
from app.services.alert_service import evaluate_reading


def ingest_telemetry(
    db: Session, payload: schemas.TelemetryCreate
) -> tuple[models.Device, list[models.SensorReading], list[models.Alert]]:
    device = db.scalar(
        select(models.Device).where(models.Device.device_code == payload.device_code)
    )
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在，请先创建设备")

    device.is_online = True
    device.last_seen_at = models.utc_now()
    saved_readings: list[models.SensorReading] = []
    created_alerts: list[models.Alert] = []

    for item in payload.readings:
        reading = models.SensorReading(
            device_id=device.id,
            metric=item.metric,
            value=item.value,
            unit=item.unit,
            quality=item.quality,
            recorded_at=payload.recorded_at,
        )
        db.add(reading)
        db.flush()
        saved_readings.append(reading)
        created_alerts.extend(evaluate_reading(db, device, reading))

    db.commit()
    for record in [*saved_readings, *created_alerts]:
        db.refresh(record)
    db.refresh(device)
    return device, saved_readings, created_alerts


def list_readings(
    db: Session,
    device_id: int | None,
    plot_id: int | None,
    metric: str | None,
    start_time: datetime | None,
    end_time: datetime | None,
    limit: int,
) -> list[models.SensorReading]:
    statement = select(models.SensorReading).join(models.Device)
    if device_id is not None:
        statement = statement.where(models.SensorReading.device_id == device_id)
    if plot_id is not None:
        statement = statement.where(models.Device.plot_id == plot_id)
    if metric:
        statement = statement.where(models.SensorReading.metric == metric)
    if start_time:
        statement = statement.where(models.SensorReading.recorded_at >= start_time)
    if end_time:
        statement = statement.where(models.SensorReading.recorded_at <= end_time)
    statement = statement.order_by(models.SensorReading.recorded_at.desc()).limit(limit)
    return list(db.scalars(statement))


def latest_by_device(db: Session, device_code: str) -> schemas.LatestTelemetryResponse:
    device = db.scalar(select(models.Device).where(models.Device.device_code == device_code))
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")

    metrics = list(
        db.scalars(
            select(models.SensorReading.metric)
            .where(models.SensorReading.device_id == device.id)
            .distinct()
        )
    )
    items: list[schemas.LatestTelemetryItem] = []
    for metric in metrics:
        reading = db.scalar(
            select(models.SensorReading)
            .where(
                models.SensorReading.device_id == device.id,
                models.SensorReading.metric == metric,
            )
            .order_by(models.SensorReading.recorded_at.desc(), models.SensorReading.id.desc())
            .limit(1)
        )
        if reading:
            items.append(schemas.LatestTelemetryItem.model_validate(reading))
    return schemas.LatestTelemetryResponse(device_code=device_code, readings=items)


def plot_summary(db: Session, plot_id: int) -> list[schemas.PlotMetricSummary]:
    if not db.get(models.Plot, plot_id):
        raise HTTPException(status_code=404, detail="地块不存在")

    aggregate_rows = db.execute(
        select(
            models.SensorReading.metric,
            func.count(models.SensorReading.id),
            func.min(models.SensorReading.value),
            func.max(models.SensorReading.value),
            func.avg(models.SensorReading.value),
        )
        .join(models.Device)
        .where(models.Device.plot_id == plot_id)
        .group_by(models.SensorReading.metric)
    ).all()

    result: list[schemas.PlotMetricSummary] = []
    for metric, count, minimum, maximum, average in aggregate_rows:
        latest = db.scalar(
            select(models.SensorReading)
            .join(models.Device)
            .where(models.Device.plot_id == plot_id, models.SensorReading.metric == metric)
            .order_by(models.SensorReading.recorded_at.desc(), models.SensorReading.id.desc())
            .limit(1)
        )
        if latest:
            result.append(
                schemas.PlotMetricSummary(
                    metric=metric,
                    count=count,
                    minimum=minimum,
                    maximum=maximum,
                    average=average,
                    latest=latest.value,
                    unit=latest.unit,
                )
            )
    return result


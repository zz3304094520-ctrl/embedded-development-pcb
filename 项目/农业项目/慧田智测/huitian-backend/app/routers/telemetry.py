from datetime import datetime

from fastapi import APIRouter, Query, status

from app import schemas
from app.dependencies import DbSession
from app.services import telemetry_service
from app.websocket_manager import websocket_manager


router = APIRouter(prefix="/telemetry", tags=["传感器数据"])


@router.post(
    "",
    response_model=schemas.TelemetryIngestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_telemetry(payload: schemas.TelemetryCreate, db: DbSession):
    device, readings, alerts = telemetry_service.ingest_telemetry(db, payload)
    for reading in readings:
        await websocket_manager.broadcast(
            "telemetry.created",
            {
                "device_code": device.device_code,
                "metric": reading.metric,
                "value": reading.value,
                "unit": reading.unit,
            },
        )
    for alert in alerts:
        await websocket_manager.broadcast(
            "alert.created",
            {"id": alert.id, "severity": alert.severity, "message": alert.message},
        )
    return schemas.TelemetryIngestResponse(
        device_code=device.device_code,
        saved_count=len(readings),
        alert_count=len(alerts),
        readings=readings,
    )


@router.get("", response_model=list[schemas.SensorReadingResponse])
def list_telemetry(
    db: DbSession,
    device_id: int | None = None,
    plot_id: int | None = None,
    metric: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
):
    return telemetry_service.list_readings(
        db, device_id, plot_id, metric, start_time, end_time, limit
    )


@router.get("/latest/{device_code}", response_model=schemas.LatestTelemetryResponse)
def latest_telemetry(device_code: str, db: DbSession):
    return telemetry_service.latest_by_device(db, device_code)


@router.get("/summary/{plot_id}", response_model=list[schemas.PlotMetricSummary])
def telemetry_summary(plot_id: int, db: DbSession):
    return telemetry_service.plot_summary(db, plot_id)


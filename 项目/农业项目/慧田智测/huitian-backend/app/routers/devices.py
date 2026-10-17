from fastapi import APIRouter, Response, status

from app import models, schemas
from app.dependencies import DbSession
from app.services import resource_service
from app.websocket_manager import websocket_manager


router = APIRouter(prefix="/devices", tags=["设备"])


@router.post("", response_model=schemas.DeviceResponse, status_code=status.HTTP_201_CREATED)
def create_device(data: schemas.DeviceCreate, db: DbSession):
    return resource_service.create_device(db, data)


@router.get("", response_model=list[schemas.DeviceResponse])
def list_devices(
    db: DbSession, plot_id: int | None = None, is_online: bool | None = None
):
    return resource_service.list_devices(db, plot_id, is_online)


@router.get("/{device_id}", response_model=schemas.DeviceResponse)
def get_device(device_id: int, db: DbSession):
    return resource_service.get_device(db, device_id)


@router.put("/{device_id}", response_model=schemas.DeviceResponse)
def update_device(device_id: int, data: schemas.DeviceUpdate, db: DbSession):
    return resource_service.update_device(db, device_id, data)


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_device(device_id: int, db: DbSession) -> Response:
    resource_service.delete_device(db, device_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{device_code}/heartbeat", response_model=schemas.HeartbeatResponse)
async def heartbeat(
    device_code: str,
    db: DbSession,
    data: schemas.HeartbeatRequest | None = None,
):
    device = resource_service.get_device_by_code(db, device_code)
    now = models.utc_now()
    device.is_online = True
    device.last_seen_at = now
    if data and data.actuator_state is not None:
        device.actuator_state = data.actuator_state
        device.state_updated_at = now
    db.commit()
    db.refresh(device)
    await websocket_manager.broadcast(
        "device.status_changed",
        {
            "device_code": device.device_code,
            "is_online": True,
            "actuator_state": device.actuator_state,
            "state_updated_at": (
                device.state_updated_at.isoformat() if device.state_updated_at else None
            ),
        },
    )
    return schemas.HeartbeatResponse(
        device_code=device.device_code,
        is_online=device.is_online,
        last_seen_at=device.last_seen_at,
        actuator_state=device.actuator_state,
        state_updated_at=device.state_updated_at,
    )


@router.post("/{device_code}/status", response_model=schemas.DeviceStatusResponse)
async def report_device_status(
    device_code: str,
    data: schemas.DeviceStatusRequest,
    db: DbSession,
):
    device = resource_service.get_device_by_code(db, device_code)
    device.is_online = data.is_online
    if data.is_online:
        device.last_seen_at = models.utc_now()
    db.commit()
    db.refresh(device)

    response = schemas.DeviceStatusResponse(
        device_code=device.device_code,
        is_online=device.is_online,
        last_seen_at=device.last_seen_at,
    )
    await websocket_manager.broadcast(
        "device.status_changed",
        response.model_dump(mode="json"),
    )
    return response

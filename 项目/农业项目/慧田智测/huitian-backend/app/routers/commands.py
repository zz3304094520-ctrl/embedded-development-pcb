from typing import Literal

from fastapi import APIRouter, status

from app import schemas
from app.dependencies import DbSession
from app.services import command_service, resource_service
from app.websocket_manager import websocket_manager


router = APIRouter(prefix="/commands", tags=["控制命令"])


@router.post(
    "", response_model=schemas.DeviceCommandResponse, status_code=status.HTTP_201_CREATED
)
async def create_command(data: schemas.CommandCreate, db: DbSession):
    command = command_service.create_command(db, data)
    await websocket_manager.broadcast(
        "command.status_changed", {"id": command.id, "status": command.status}
    )
    return command


@router.get("", response_model=list[schemas.DeviceCommandResponse])
def list_commands(
    db: DbSession,
    device_id: int | None = None,
    status_filter: Literal[
        "pending", "sent", "acknowledged", "succeeded", "failed"
    ]
    | None = None,
):
    return command_service.list_commands(db, device_id, status_filter)


@router.get("/{command_id}", response_model=schemas.DeviceCommandResponse)
def get_command(command_id: int, db: DbSession):
    return command_service.get_command(db, command_id)


@router.post("/{command_id}/ack", response_model=schemas.DeviceCommandResponse)
async def acknowledge_command(command_id: int, data: schemas.CommandAck, db: DbSession):
    command = command_service.update_command_status(
        db, command_id, data.status, data.actuator_state
    )
    device = resource_service.get_device(db, command.device_id)
    await websocket_manager.broadcast(
        "command.status_changed", {"id": command.id, "status": command.status}
    )
    await websocket_manager.broadcast(
        "device.status_changed",
        {
            "device_code": device.device_code,
            "is_online": device.is_online,
            "actuator_state": device.actuator_state,
            "state_updated_at": (
                device.state_updated_at.isoformat() if device.state_updated_at else None
            ),
        },
    )
    return command

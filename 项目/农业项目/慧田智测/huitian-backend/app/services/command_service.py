from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas


VALID_TRANSITIONS = {
    "pending": {"sent", "acknowledged", "failed"},
    "sent": {"acknowledged", "succeeded", "failed"},
    "acknowledged": {"succeeded", "failed"},
    "succeeded": set(),
    "failed": set(),
}

EXPECTED_DEVICE_TYPES = {
    "pump_on": "pump",
    "pump_off": "pump",
    "light_on": "grow_light",
    "light_off": "grow_light",
}
ACTIVE_ON_STATUSES = ("pending", "acknowledged")


def create_command(db: Session, data: schemas.CommandCreate) -> models.DeviceCommand:
    device = db.get(models.Device, data.device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    expected_device_type = EXPECTED_DEVICE_TYPES[data.command_type]
    if device.device_type != expected_device_type:
        raise HTTPException(
            status_code=409,
            detail=(
                f"{data.command_type} 只能发送给 device_type="
                f"{expected_device_type} 的设备"
            ),
        )
    if device.communication_type != "http":
        raise HTTPException(status_code=422, detail="控制命令仅支持 HTTP 设备")

    if data.command_type in {"pump_on", "light_on"}:
        active_on_command = db.scalar(
            select(models.DeviceCommand.id)
            .where(
                models.DeviceCommand.device_id == data.device_id,
                models.DeviceCommand.command_type == data.command_type,
                models.DeviceCommand.status.in_(ACTIVE_ON_STATUSES),
            )
            .limit(1)
        )
        if active_on_command:
            raise HTTPException(
                status_code=409,
                detail="设备已有待执行或执行中的开启命令，请勿重复下发",
            )

    command = models.DeviceCommand(
        device_id=data.device_id,
        command_type=data.command_type,
        parameters_json=data.parameters,
    )
    db.add(command)
    db.commit()
    db.refresh(command)
    return command


def list_commands(
    db: Session, device_id: int | None = None, status: str | None = None
) -> list[models.DeviceCommand]:
    statement = select(models.DeviceCommand)
    if device_id is not None:
        statement = statement.where(models.DeviceCommand.device_id == device_id)
    if status:
        statement = statement.where(models.DeviceCommand.status == status)
    return list(db.scalars(statement.order_by(models.DeviceCommand.created_at.desc())))


def get_command(db: Session, command_id: int) -> models.DeviceCommand:
    command = db.get(models.DeviceCommand, command_id)
    if not command:
        raise HTTPException(status_code=404, detail="控制命令不存在")
    return command


def update_command_status(
    db: Session,
    command_id: int,
    new_status: str,
    actuator_state: schemas.ActuatorState | None = None,
) -> models.DeviceCommand:
    command = get_command(db, command_id)
    if (
        new_status != command.status
        and new_status not in VALID_TRANSITIONS.get(command.status, set())
    ):
        raise HTTPException(
            status_code=409,
            detail=f"命令状态不能从 {command.status} 变更为 {new_status}",
        )

    now = models.utc_now()
    if new_status != command.status:
        command.status = new_status
        command.updated_at = now

    device = db.get(models.Device, command.device_id)
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    device.is_online = True
    device.last_seen_at = now
    if actuator_state is not None:
        device.actuator_state = actuator_state
        device.state_updated_at = now

    db.commit()
    db.refresh(command)
    db.refresh(device)
    return command

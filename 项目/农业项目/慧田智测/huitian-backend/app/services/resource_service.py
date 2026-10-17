from typing import Any, TypeVar

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, schemas


ModelT = TypeVar("ModelT")


def _not_found(name: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{name}不存在")


def _apply_updates(instance: Any, data: dict[str, Any]) -> Any:
    for key, value in data.items():
        setattr(instance, key, value)
    return instance


def create_farm(db: Session, data: schemas.FarmCreate) -> models.Farm:
    farm = models.Farm(**data.model_dump())
    db.add(farm)
    db.commit()
    db.refresh(farm)
    return farm


def get_farm(db: Session, farm_id: int) -> models.Farm:
    farm = db.get(models.Farm, farm_id)
    if not farm:
        raise _not_found("农场")
    return farm


def list_farms(db: Session) -> list[models.Farm]:
    return list(db.scalars(select(models.Farm).order_by(models.Farm.id)))


def update_farm(db: Session, farm_id: int, data: schemas.FarmUpdate) -> models.Farm:
    farm = get_farm(db, farm_id)
    _apply_updates(farm, data.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(farm)
    return farm


def delete_farm(db: Session, farm_id: int) -> None:
    farm = get_farm(db, farm_id)
    if db.scalar(select(models.Plot.id).where(models.Plot.farm_id == farm_id).limit(1)):
        raise HTTPException(status_code=409, detail="农场下存在地块，不能删除")
    db.delete(farm)
    db.commit()


def create_plot(db: Session, data: schemas.PlotCreate) -> models.Plot:
    get_farm(db, data.farm_id)
    plot = models.Plot(**data.model_dump())
    db.add(plot)
    db.commit()
    db.refresh(plot)
    return plot


def get_plot(db: Session, plot_id: int) -> models.Plot:
    plot = db.get(models.Plot, plot_id)
    if not plot:
        raise _not_found("地块")
    return plot


def list_plots(db: Session, farm_id: int | None = None) -> list[models.Plot]:
    statement = select(models.Plot)
    if farm_id is not None:
        statement = statement.where(models.Plot.farm_id == farm_id)
    return list(db.scalars(statement.order_by(models.Plot.id)))


def update_plot(db: Session, plot_id: int, data: schemas.PlotUpdate) -> models.Plot:
    plot = get_plot(db, plot_id)
    updates = data.model_dump(exclude_unset=True)
    if "farm_id" in updates:
        get_farm(db, updates["farm_id"])
    _apply_updates(plot, updates)
    db.commit()
    db.refresh(plot)
    return plot


def delete_plot(db: Session, plot_id: int) -> None:
    plot = get_plot(db, plot_id)
    has_device = db.scalar(select(models.Device.id).where(models.Device.plot_id == plot_id).limit(1))
    has_rule = db.scalar(
        select(models.AlertRule.id).where(models.AlertRule.plot_id == plot_id).limit(1)
    )
    has_diagnosis = db.scalar(
        select(models.DiagnosisRecord.id)
        .where(models.DiagnosisRecord.plot_id == plot_id)
        .limit(1)
    )
    if has_device or has_rule or has_diagnosis:
        raise HTTPException(status_code=409, detail="地块下存在设备、规则或诊断记录，不能删除")
    db.delete(plot)
    db.commit()


def create_device(db: Session, data: schemas.DeviceCreate) -> models.Device:
    get_plot(db, data.plot_id)
    device = models.Device(**data.model_dump())
    db.add(device)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="device_code 已存在") from exc
    db.refresh(device)
    return device


def get_device(db: Session, device_id: int) -> models.Device:
    device = db.get(models.Device, device_id)
    if not device:
        raise _not_found("设备")
    return device


def get_device_by_code(db: Session, device_code: str) -> models.Device:
    device = db.scalar(select(models.Device).where(models.Device.device_code == device_code))
    if not device:
        raise _not_found("设备")
    return device


def list_devices(
    db: Session, plot_id: int | None = None, is_online: bool | None = None
) -> list[models.Device]:
    statement = select(models.Device)
    if plot_id is not None:
        statement = statement.where(models.Device.plot_id == plot_id)
    if is_online is not None:
        statement = statement.where(models.Device.is_online == is_online)
    return list(db.scalars(statement.order_by(models.Device.id)))


def update_device(db: Session, device_id: int, data: schemas.DeviceUpdate) -> models.Device:
    device = get_device(db, device_id)
    updates = data.model_dump(exclude_unset=True)
    if "plot_id" in updates:
        get_plot(db, updates["plot_id"])
    _apply_updates(device, updates)
    db.commit()
    db.refresh(device)
    return device


def delete_device(db: Session, device_id: int) -> None:
    device = get_device(db, device_id)
    references = [
        db.scalar(
            select(models.SensorReading.id)
            .where(models.SensorReading.device_id == device_id)
            .limit(1)
        ),
        db.scalar(select(models.Alert.id).where(models.Alert.device_id == device_id).limit(1)),
        db.scalar(
            select(models.DeviceCommand.id)
            .where(models.DeviceCommand.device_id == device_id)
            .limit(1)
        ),
        db.scalar(
            select(models.DiseaseDetection.id)
            .where(models.DiseaseDetection.device_id == device_id)
            .limit(1)
        ),
    ]
    if any(references):
        raise HTTPException(status_code=409, detail="设备存在历史数据、告警或命令，不能删除")
    db.delete(device)
    db.commit()

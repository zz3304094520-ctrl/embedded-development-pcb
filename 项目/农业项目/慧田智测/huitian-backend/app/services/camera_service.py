from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.services import resource_service


def register_camera(
    db: Session, data: schemas.EdgeCameraRegistration
) -> models.Device:
    device = db.scalar(
        select(models.Device).where(models.Device.device_code == data.device_code)
    )
    if not device:
        first_plot_id = db.scalar(select(models.Plot.id).order_by(models.Plot.id).limit(1))
        if first_plot_id is None:
            raise HTTPException(status_code=404, detail="可关联的地块不存在")
        device = models.Device(
            plot_id=first_plot_id,
            device_code=data.device_code,
            name=data.device_name,
            device_type="camera",
            communication_type="http",
        )
        db.add(device)

    device.name = data.device_name
    device.device_type = "camera"
    device.communication_type = "http"
    device.is_online = data.camera_online
    device.last_seen_at = models.utc_now()
    device.camera_model = data.camera_model
    device.stream_url = data.stream_url
    device.capabilities_json = data.capabilities
    device.metadata_json = data.metadata
    db.commit()
    db.refresh(device)
    return device


def create_detection(
    db: Session, data: schemas.DiseaseDetectionCreate
) -> models.DiseaseDetection:
    device = resource_service.get_device_by_code(db, data.device_code)
    device.is_online = True
    device.last_seen_at = models.utc_now()

    detection = models.DiseaseDetection(
        device_id=device.id,
        class_name=data.class_name,
        disease_name=data.disease_name,
        cause=data.cause,
        severity=data.severity,
        treatment_json=data.treatment,
        confidence=data.confidence,
        distance_m=data.distance_m,
        bbox_json=data.bbox.model_dump(),
        image_url=data.image_url,
        detected_at=data.detected_at,
    )
    db.add(detection)
    db.commit()
    db.refresh(detection)
    return detection


def list_detections(
    db: Session,
    *,
    plot_id: int | None = None,
    device_id: int | None = None,
    limit: int = 50,
) -> list[schemas.DiseaseDetectionResponse]:
    statement = select(models.DiseaseDetection, models.Device.device_code).join(
        models.Device, models.Device.id == models.DiseaseDetection.device_id
    )
    if plot_id is not None:
        statement = statement.where(models.Device.plot_id == plot_id)
    if device_id is not None:
        statement = statement.where(models.DiseaseDetection.device_id == device_id)
    rows = db.execute(
        statement.order_by(models.DiseaseDetection.detected_at.desc()).limit(limit)
    ).all()
    return [serialize_detection(detection, device_code) for detection, device_code in rows]


def serialize_detection(
    detection: models.DiseaseDetection, device_code: str
) -> schemas.DiseaseDetectionResponse:
    return schemas.DiseaseDetectionResponse(
        id=detection.id,
        device_id=detection.device_id,
        device_code=device_code,
        class_name=detection.class_name,
        disease_name=detection.disease_name,
        cause=detection.cause,
        severity=detection.severity,
        treatment=detection.treatment_json,
        confidence=detection.confidence,
        distance_m=detection.distance_m,
        bbox=detection.bbox_json,
        image_url=detection.image_url,
        detected_at=detection.detected_at,
        received_at=detection.received_at,
    )

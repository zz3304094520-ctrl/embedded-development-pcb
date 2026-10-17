from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.config import settings


ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


async def create_diagnosis(
    db: Session, plot_id: int, upload: UploadFile
) -> models.DiagnosisRecord:
    if not db.get(models.Plot, plot_id):
        raise HTTPException(status_code=404, detail="地块不存在")

    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="仅支持 jpg、jpeg、png、webp 图片")

    content = await upload.read(settings.upload_max_mb * 1024 * 1024 + 1)
    if len(content) > settings.upload_max_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"图片不能超过 {settings.upload_max_mb} MB")
    if not content:
        raise HTTPException(status_code=400, detail="上传图片为空")

    safe_name = f"{uuid4().hex}{suffix}"
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    target = settings.upload_dir / safe_name
    target.write_bytes(content)

    record = models.DiagnosisRecord(
        plot_id=plot_id,
        image_path=f"uploads/{safe_name}",
        crop_type="番茄",
        growth_stage="结果期（演示）",
        health_status="需要人工复核（演示）",
        result_text=(
            "这是用于前后端联调的演示结果，不是真实 AI 模型诊断。"
            "建议结合传感器数据并由农业技术人员人工确认。"
        ),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def list_diagnoses(db: Session, plot_id: int | None = None) -> list[models.DiagnosisRecord]:
    statement = select(models.DiagnosisRecord)
    if plot_id is not None:
        statement = statement.where(models.DiagnosisRecord.plot_id == plot_id)
    return list(db.scalars(statement.order_by(models.DiagnosisRecord.created_at.desc())))


def get_diagnosis(db: Session, diagnosis_id: int) -> models.DiagnosisRecord:
    record = db.get(models.DiagnosisRecord, diagnosis_id)
    if not record:
        raise HTTPException(status_code=404, detail="诊断记录不存在")
    return record


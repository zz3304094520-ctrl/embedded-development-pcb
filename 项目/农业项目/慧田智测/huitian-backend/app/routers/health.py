from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import text

from app.config import settings
from app.database import SessionLocal
from app.schemas import HealthResponse


router = APIRouter(tags=["健康检查"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    database_status = "connected"
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception:
        database_status = "error"
    return HealthResponse(
        app=settings.app_name,
        status="ok" if database_status == "connected" else "degraded",
        database=database_status,
        mqtt="disabled",
        timestamp=datetime.now(timezone.utc),
    )

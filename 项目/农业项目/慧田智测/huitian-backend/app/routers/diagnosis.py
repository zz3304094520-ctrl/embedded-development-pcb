from fastapi import APIRouter, File, Form, UploadFile, status

from app import schemas
from app.dependencies import DbSession
from app.services import diagnosis_service


router = APIRouter(prefix="/diagnosis", tags=["作物诊断演示"])


@router.post(
    "", response_model=schemas.DiagnosisResponse, status_code=status.HTTP_201_CREATED
)
async def create_diagnosis(
    db: DbSession,
    plot_id: int = Form(...),
    image: UploadFile = File(...),
):
    return await diagnosis_service.create_diagnosis(db, plot_id, image)


@router.get("", response_model=list[schemas.DiagnosisResponse])
def list_diagnoses(db: DbSession, plot_id: int | None = None):
    return diagnosis_service.list_diagnoses(db, plot_id)


@router.get("/{diagnosis_id}", response_model=schemas.DiagnosisResponse)
def get_diagnosis(diagnosis_id: int, db: DbSession):
    return diagnosis_service.get_diagnosis(db, diagnosis_id)


from fastapi import APIRouter, Response, status

from app import schemas
from app.dependencies import DbSession
from app.services import resource_service


router = APIRouter(prefix="/farms", tags=["农场"])


@router.post("", response_model=schemas.FarmResponse, status_code=status.HTTP_201_CREATED)
def create_farm(data: schemas.FarmCreate, db: DbSession):
    return resource_service.create_farm(db, data)


@router.get("", response_model=list[schemas.FarmResponse])
def list_farms(db: DbSession):
    return resource_service.list_farms(db)


@router.get("/{farm_id}", response_model=schemas.FarmResponse)
def get_farm(farm_id: int, db: DbSession):
    return resource_service.get_farm(db, farm_id)


@router.put("/{farm_id}", response_model=schemas.FarmResponse)
def update_farm(farm_id: int, data: schemas.FarmUpdate, db: DbSession):
    return resource_service.update_farm(db, farm_id, data)


@router.delete("/{farm_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_farm(farm_id: int, db: DbSession) -> Response:
    resource_service.delete_farm(db, farm_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


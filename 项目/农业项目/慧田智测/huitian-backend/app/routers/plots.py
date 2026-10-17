from fastapi import APIRouter, Response, status

from app import schemas
from app.dependencies import DbSession
from app.services import resource_service


router = APIRouter(prefix="/plots", tags=["地块"])


@router.post("", response_model=schemas.PlotResponse, status_code=status.HTTP_201_CREATED)
def create_plot(data: schemas.PlotCreate, db: DbSession):
    return resource_service.create_plot(db, data)


@router.get("", response_model=list[schemas.PlotResponse])
def list_plots(db: DbSession, farm_id: int | None = None):
    return resource_service.list_plots(db, farm_id)


@router.get("/{plot_id}", response_model=schemas.PlotResponse)
def get_plot(plot_id: int, db: DbSession):
    return resource_service.get_plot(db, plot_id)


@router.put("/{plot_id}", response_model=schemas.PlotResponse)
def update_plot(plot_id: int, data: schemas.PlotUpdate, db: DbSession):
    return resource_service.update_plot(db, plot_id, data)


@router.delete("/{plot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plot(plot_id: int, db: DbSession) -> Response:
    resource_service.delete_plot(db, plot_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


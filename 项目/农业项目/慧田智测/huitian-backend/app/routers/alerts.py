from typing import Literal

from fastapi import APIRouter, Response, status

from app import schemas
from app.dependencies import DbSession
from app.services import alert_service
from app.websocket_manager import websocket_manager


router = APIRouter(prefix="/alerts", tags=["告警"])


@router.post(
    "/rules", response_model=schemas.AlertRuleResponse, status_code=status.HTTP_201_CREATED
)
def create_rule(data: schemas.AlertRuleCreate, db: DbSession):
    return alert_service.create_rule(db, data)


@router.get("/rules", response_model=list[schemas.AlertRuleResponse])
def list_rules(db: DbSession, plot_id: int | None = None):
    return alert_service.list_rules(db, plot_id)


@router.put("/rules/{rule_id}", response_model=schemas.AlertRuleResponse)
def update_rule(rule_id: int, data: schemas.AlertRuleUpdate, db: DbSession):
    return alert_service.update_rule(db, rule_id, data)


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(rule_id: int, db: DbSession) -> Response:
    alert_service.delete_rule(db, rule_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("", response_model=list[schemas.AlertResponse])
def list_alerts(
    db: DbSession,
    status_filter: Literal["open", "acknowledged", "resolved"] | None = None,
    severity: Literal["info", "warning", "critical"] | None = None,
):
    return alert_service.list_alerts(db, status_filter, severity)


@router.get("/{alert_id}", response_model=schemas.AlertResponse)
def get_alert(alert_id: int, db: DbSession):
    return alert_service.get_alert(db, alert_id)


@router.post("/{alert_id}/acknowledge", response_model=schemas.AlertResponse)
async def acknowledge_alert(alert_id: int, db: DbSession):
    alert = alert_service.change_alert_status(db, alert_id, "acknowledged")
    await websocket_manager.broadcast(
        "alert.status_changed", {"id": alert.id, "status": alert.status}
    )
    return alert


@router.post("/{alert_id}/resolve", response_model=schemas.AlertResponse)
async def resolve_alert(alert_id: int, db: DbSession):
    alert = alert_service.change_alert_status(db, alert_id, "resolved")
    await websocket_manager.broadcast(
        "alert.status_changed", {"id": alert.id, "status": alert.status}
    )
    return alert


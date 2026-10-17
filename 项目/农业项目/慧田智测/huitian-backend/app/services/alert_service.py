import operator as py_operator

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas


OPERATORS = {
    "gt": py_operator.gt,
    "gte": py_operator.ge,
    "lt": py_operator.lt,
    "lte": py_operator.le,
}


def evaluate_reading(
    db: Session, device: models.Device, reading: models.SensorReading
) -> list[models.Alert]:
    if reading.quality != "good":
        return []

    rules = list(
        db.scalars(
            select(models.AlertRule).where(
                models.AlertRule.plot_id == device.plot_id,
                models.AlertRule.metric == reading.metric,
                models.AlertRule.enabled.is_(True),
            )
        )
    )
    created: list[models.Alert] = []
    for rule in rules:
        compare = OPERATORS[rule.operator]
        if compare(reading.value, rule.threshold):
            existing = db.scalar(
                select(models.Alert.id).where(
                    models.Alert.rule_id == rule.id,
                    models.Alert.device_id == device.id,
                    models.Alert.status.in_(("open", "acknowledged")),
                ).limit(1)
            )
            if existing:
                continue
            alert = models.Alert(
                rule_id=rule.id,
                device_id=device.id,
                reading_id=reading.id,
                severity=rule.severity,
                message=(
                    f"{rule.message}；当前值 {reading.value:g} {reading.unit}，"
                    f"阈值 {rule.threshold:g}"
                ),
            )
            db.add(alert)
            created.append(alert)
    db.flush()
    return created


def create_rule(db: Session, data: schemas.AlertRuleCreate) -> models.AlertRule:
    if not db.get(models.Plot, data.plot_id):
        raise HTTPException(status_code=404, detail="地块不存在")
    rule = models.AlertRule(**data.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def list_rules(db: Session, plot_id: int | None = None) -> list[models.AlertRule]:
    statement = select(models.AlertRule)
    if plot_id is not None:
        statement = statement.where(models.AlertRule.plot_id == plot_id)
    return list(db.scalars(statement.order_by(models.AlertRule.id)))


def get_rule(db: Session, rule_id: int) -> models.AlertRule:
    rule = db.get(models.AlertRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="告警规则不存在")
    return rule


def update_rule(
    db: Session, rule_id: int, data: schemas.AlertRuleUpdate
) -> models.AlertRule:
    rule = get_rule(db, rule_id)
    updates = data.model_dump(exclude_unset=True)
    if "plot_id" in updates and not db.get(models.Plot, updates["plot_id"]):
        raise HTTPException(status_code=404, detail="地块不存在")
    for key, value in updates.items():
        setattr(rule, key, value)
    db.commit()
    db.refresh(rule)
    return rule


def delete_rule(db: Session, rule_id: int) -> None:
    rule = get_rule(db, rule_id)
    if db.scalar(select(models.Alert.id).where(models.Alert.rule_id == rule_id).limit(1)):
        raise HTTPException(status_code=409, detail="规则已有告警记录，不能删除；可以将 enabled 设为 false")
    db.delete(rule)
    db.commit()


def list_alerts(
    db: Session, status: str | None = None, severity: str | None = None
) -> list[models.Alert]:
    statement = select(models.Alert)
    if status:
        statement = statement.where(models.Alert.status == status)
    if severity:
        statement = statement.where(models.Alert.severity == severity)
    return list(db.scalars(statement.order_by(models.Alert.created_at.desc())))


def get_alert(db: Session, alert_id: int) -> models.Alert:
    alert = db.get(models.Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="告警不存在")
    return alert


def change_alert_status(db: Session, alert_id: int, new_status: str) -> models.Alert:
    alert = get_alert(db, alert_id)
    alert.status = new_status
    alert.updated_at = models.utc_now()
    db.commit()
    db.refresh(alert)
    return alert

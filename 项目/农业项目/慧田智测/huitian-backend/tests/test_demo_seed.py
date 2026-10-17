from sqlalchemy import func, select

from app import models
from app.database import SessionLocal
from scripts.init_demo_data import main


def test_demo_seed_adds_actuators_idempotently():
    main()
    main()

    with SessionLocal() as db:
        pump = db.scalar(
            select(models.Device).where(models.Device.device_code == "pump-001")
        )
        light = db.scalar(
            select(models.Device).where(models.Device.device_code == "grow-light-001")
        )
        actuator_count = db.scalar(
            select(func.count(models.Device.id)).where(
                models.Device.device_code.in_(("pump-001", "grow-light-001"))
            )
        )
        camera = db.scalar(
            select(models.Device).where(models.Device.device_code == "edge-orin-001")
        )

    assert actuator_count == 2
    assert pump is not None
    assert pump.name == "A1 灌溉水泵"
    assert pump.device_type == "pump"
    assert pump.actuator_state == "unknown"
    assert light is not None
    assert light.name == "A1 作物补光灯"
    assert light.device_type == "grow_light"
    assert light.actuator_state == "unknown"
    assert camera is not None
    assert camera.name == "Jetson D435i 智能巡检节点"
    assert camera.device_type == "camera"

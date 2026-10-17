import os
from pathlib import Path


TEST_DB = Path(__file__).resolve().parent / "test_huitian.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["MQTT_ENABLED"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if TEST_DB.exists():
        TEST_DB.unlink(missing_ok=True)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_farm(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/farms",
        json={"name": "测试农场", "location": "上海", "description": "测试"},
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def sample_plot(client: TestClient, sample_farm: dict) -> dict:
    response = client.post(
        "/api/v1/plots",
        json={
            "farm_id": sample_farm["id"],
            "name": "测试地块",
            "crop_type": "番茄",
            "area": 2.5,
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def sample_device(client: TestClient, sample_plot: dict) -> dict:
    response = client.post(
        "/api/v1/devices",
        json={
            "plot_id": sample_plot["id"],
            "device_code": "test-device-001",
            "name": "测试设备",
            "device_type": "weather_station",
            "communication_type": "http",
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def sample_pump_device(client: TestClient, sample_plot: dict) -> dict:
    response = client.post(
        "/api/v1/devices",
        json={
            "plot_id": sample_plot["id"],
            "device_code": "test-pump-001",
            "name": "测试灌溉水泵",
            "device_type": "pump",
            "communication_type": "http",
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def sample_light_device(client: TestClient, sample_plot: dict) -> dict:
    response = client.post(
        "/api/v1/devices",
        json={
            "plot_id": sample_plot["id"],
            "device_code": "test-grow-light-001",
            "name": "测试作物补光灯",
            "device_type": "grow_light",
            "communication_type": "http",
        },
    )
    assert response.status_code == 201
    return response.json()

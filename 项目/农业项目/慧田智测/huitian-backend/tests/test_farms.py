def test_farm_crud(client):
    create = client.post(
        "/api/v1/farms",
        json={"name": "金山农场", "location": "上海", "description": "番茄基地"},
    )
    assert create.status_code == 201
    farm_id = create.json()["id"]

    assert client.get(f"/api/v1/farms/{farm_id}").status_code == 200

    update = client.put(
        f"/api/v1/farms/{farm_id}",
        json={"name": "金山智慧农场"},
    )
    assert update.status_code == 200
    assert update.json()["name"] == "金山智慧农场"

    assert client.delete(f"/api/v1/farms/{farm_id}").status_code == 204
    assert client.get(f"/api/v1/farms/{farm_id}").status_code == 404


def test_missing_farm_returns_404(client):
    response = client.get("/api/v1/farms/9999")
    assert response.status_code == 404


def test_plot_and_device_creation(client, sample_plot, sample_device):
    assert sample_plot["crop_type"] == "番茄"
    assert sample_device["device_code"] == "test-device-001"


def test_duplicate_device_code_returns_409(client, sample_plot, sample_device):
    response = client.post(
        "/api/v1/devices",
        json={
            "plot_id": sample_plot["id"],
            "device_code": sample_device["device_code"],
            "name": "重复设备",
            "device_type": "soil_sensor",
            "communication_type": "http",
        },
    )
    assert response.status_code == 409


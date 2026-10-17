from fastapi.testclient import TestClient

from app.routers import camera


def registration_payload() -> dict:
    return {
        "user_id": 4,
        "device_code": "edge-orin-001",
        "device_name": "Jetson D435i 智能巡检节点",
        "camera_model": "Intel RealSense D435i",
        "stream_url": "http://172.20.10.4:8081/video",
        "ip_address": "172.20.10.4",
        "service_port": 8081,
        "camera_online": True,
        "capabilities": ["realsense_camera", "yolo_detection"],
        "metadata": {"model_classes": ["healthy", "late_blight"]},
    }


def detection_payload() -> dict:
    return {
        "user_id": 4,
        "device_code": "edge-orin-001",
        "class_name": "late_blight",
        "disease_name": "番茄晚疫病",
        "cause": "检测到疑似晚疫病特征",
        "severity": "severe",
        "treatment": ["隔离病株", "请农技人员复核"],
        "confidence": 0.9231,
        "distance_m": 0.84,
        "bbox": {"x1": 10, "y1": 20, "x2": 220, "y2": 300},
        "image_url": "http://172.20.10.4:8081/snapshot.jpg",
        "detected_at": "2026-07-22T19:30:00+08:00",
    }


def test_camera_registration_creates_device_and_updates_stream(
    client: TestClient, sample_plot: dict
):
    response = client.post("/camera/edge/register", json=registration_payload())

    assert response.status_code == 200
    assert response.json()["success"] is True

    devices = client.get(f"/api/v1/devices?plot_id={sample_plot['id']}").json()
    camera = next(device for device in devices if device["device_code"] == "edge-orin-001")
    assert camera["device_type"] == "camera"
    assert camera["is_online"] is True
    assert camera["camera_model"] == "Intel RealSense D435i"
    assert camera["stream_url"] == "http://172.20.10.4:8081/video"


def test_camera_registration_tracks_hotplug_state(
    client: TestClient, sample_plot: dict
):
    payload = registration_payload()
    payload["camera_online"] = False

    offline_response = client.post("/camera/edge/register", json=payload)
    assert offline_response.status_code == 200
    device_id = offline_response.json()["device_id"]

    devices = client.get(f"/api/v1/devices?plot_id={sample_plot['id']}").json()
    offline_camera = next(device for device in devices if device["id"] == device_id)
    assert offline_camera["is_online"] is False

    payload["camera_online"] = True
    online_response = client.post("/camera/edge/register", json=payload)
    assert online_response.status_code == 200
    assert online_response.json()["device_id"] == device_id

    devices = client.get(f"/api/v1/devices?plot_id={sample_plot['id']}").json()
    online_camera = next(device for device in devices if device["id"] == device_id)
    assert online_camera["is_online"] is True
    assert online_camera["stream_url"] == payload["stream_url"]


def test_detection_ingest_and_plot_query(client: TestClient, sample_plot: dict):
    client.post("/camera/edge/register", json=registration_payload())

    response = client.post("/camera/edge/detections", json=detection_payload())
    assert response.status_code == 200
    assert response.json()["success"] is True

    result = client.get(
        f"/api/v1/detections?plot_id={sample_plot['id']}&limit=10"
    )
    assert result.status_code == 200
    detections = result.json()
    assert len(detections) == 1
    assert detections[0]["device_code"] == "edge-orin-001"
    assert detections[0]["disease_name"] == "番茄晚疫病"
    assert detections[0]["confidence"] == 0.9231
    assert detections[0]["distance_m"] == 0.84
    assert detections[0]["treatment"] == ["隔离病株", "请农技人员复核"]


def test_detection_rejects_invalid_bbox(client: TestClient, sample_plot: dict):
    client.post("/camera/edge/register", json=registration_payload())
    payload = detection_payload()
    payload["bbox"] = {"x1": 200, "y1": 20, "x2": 10, "y2": 300}

    response = client.post("/camera/edge/detections", json=payload)

    assert response.status_code == 422


def test_camera_proxy_rejects_unknown_device(client: TestClient):
    response = client.get("/api/v1/camera/missing-camera/health")

    assert response.status_code == 404


def test_camera_health_proxy_recovers_stale_offline_state(
    client: TestClient, sample_plot: dict, monkeypatch
):
    payload = registration_payload()
    payload["camera_online"] = False
    client.post("/camera/edge/register", json=payload)

    class FakeResponse:
        headers = {"content-type": "application/json"}

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "status": "online",
                "camera": "Intel RealSense D435I",
                "frames": 42,
                "last_frame_seconds": 0.02,
                "message": "D435i 视频流正常",
            }

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

        async def get(self, url, headers):
            assert url == "http://172.20.10.4:8081/health"
            assert headers["Accept"] == "application/json"
            return FakeResponse()

    monkeypatch.setattr(camera.httpx, "AsyncClient", FakeAsyncClient)

    response = client.get("/api/v1/camera/edge-orin-001/health")

    assert response.status_code == 200
    assert response.json()["status"] == "online"
    devices = client.get(f"/api/v1/devices?plot_id={sample_plot['id']}").json()
    registered_camera = next(
        device for device in devices if device["device_code"] == "edge-orin-001"
    )
    assert registered_camera["is_online"] is True

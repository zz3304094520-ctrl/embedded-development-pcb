def test_heartbeat_optionally_reports_actuator_state(client, sample_pump_device):
    initial = client.get(f"/api/v1/devices/{sample_pump_device['id']}").json()
    assert initial["actuator_state"] == "unknown"
    assert initial["state_updated_at"] is None

    heartbeat = client.post("/api/v1/devices/test-pump-001/heartbeat")
    assert heartbeat.status_code == 200
    assert heartbeat.json()["is_online"] is True
    assert heartbeat.json()["actuator_state"] == "unknown"
    assert heartbeat.json()["state_updated_at"] is None

    reported = client.post(
        "/api/v1/devices/test-pump-001/heartbeat",
        json={"actuator_state": "off"},
    )
    assert reported.status_code == 200
    assert reported.json()["actuator_state"] == "off"
    assert reported.json()["state_updated_at"] is not None

    stored = client.get(f"/api/v1/devices/{sample_pump_device['id']}").json()
    assert stored["actuator_state"] == "off"
    assert stored["state_updated_at"] == reported.json()["state_updated_at"]


def test_heartbeat_rejects_unknown_actuator_state(client, sample_pump_device):
    response = client.post(
        "/api/v1/devices/test-pump-001/heartbeat",
        json={"actuator_state": "broken"},
    )
    assert response.status_code == 422


def test_status_reports_online_and_offline_without_overwriting_last_seen(
    client, sample_device
):
    with client.websocket_connect("/ws") as websocket:
        assert websocket.receive_json()["event"] == "system.connected"

        online = client.post(
            "/api/v1/devices/test-device-001/status",
            json={"is_online": True},
        )
        assert online.status_code == 200
        online_body = online.json()
        assert online_body["device_code"] == "test-device-001"
        assert online_body["is_online"] is True
        assert online_body["last_seen_at"] is not None
        assert websocket.receive_json() == {
            "event": "device.status_changed",
            "data": online_body,
        }

        offline = client.post(
            "/api/v1/devices/test-device-001/status",
            json={"is_online": False},
        )
        assert offline.status_code == 200
        offline_body = offline.json()
        assert offline_body == {
            "device_code": "test-device-001",
            "is_online": False,
            "last_seen_at": online_body["last_seen_at"],
        }
        assert websocket.receive_json() == {
            "event": "device.status_changed",
            "data": offline_body,
        }

    stored = client.get(f"/api/v1/devices/{sample_device['id']}")
    assert stored.status_code == 200
    assert stored.json()["is_online"] is False
    assert stored.json()["last_seen_at"] == online_body["last_seen_at"]


def test_status_returns_404_for_unknown_device(client):
    response = client.post(
        "/api/v1/devices/missing-sensor/status",
        json={"is_online": False},
    )
    assert response.status_code == 404

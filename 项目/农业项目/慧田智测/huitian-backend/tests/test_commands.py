import pytest


def command_payload(device_id: int, command_type: str, parameters: dict) -> dict:
    return {
        "device_id": device_id,
        "command_type": command_type,
        "parameters": parameters,
    }


def test_http_command_lifecycle_updates_device_and_websocket(
    client, sample_pump_device
):
    created = client.post(
        "/api/v1/commands",
        json=command_payload(
            sample_pump_device["id"],
            "pump_on",
            {"duration_seconds": 30},
        ),
    )
    assert created.status_code == 201
    assert created.json()["status"] == "pending"
    command_id = created.json()["id"]

    with client.websocket_connect("/ws") as websocket:
        assert websocket.receive_json()["event"] == "system.connected"
        acknowledged = client.post(
            f"/api/v1/commands/{command_id}/ack",
            json={"status": "acknowledged", "actuator_state": "on"},
        )
        assert acknowledged.status_code == 200
        assert acknowledged.json()["status"] == "acknowledged"

        command_event = websocket.receive_json()
        device_event = websocket.receive_json()
        assert command_event == {
            "event": "command.status_changed",
            "data": {"id": command_id, "status": "acknowledged"},
        }
        assert device_event["event"] == "device.status_changed"
        assert device_event["data"]["device_code"] == "test-pump-001"
        assert device_event["data"]["actuator_state"] == "on"

    device = client.get(f"/api/v1/devices/{sample_pump_device['id']}")
    assert device.status_code == 200
    assert device.json()["is_online"] is True
    assert device.json()["actuator_state"] == "on"
    assert device.json()["last_seen_at"] is not None
    assert device.json()["state_updated_at"] is not None

    succeeded = client.post(
        f"/api/v1/commands/{command_id}/ack",
        json={"status": "succeeded", "actuator_state": "off"},
    )
    assert succeeded.status_code == 200
    assert succeeded.json()["status"] == "succeeded"
    assert client.get(f"/api/v1/devices/{sample_pump_device['id']}").json()[
        "actuator_state"
    ] == "off"


@pytest.mark.parametrize(
    ("parameters", "expected_message"),
    [
        ({}, "duration_seconds"),
        ({"duration_seconds": 0}, "1 到 300"),
        ({"duration_seconds": 301}, "1 到 300"),
        ({"duration_seconds": 1.5}, "必须是整数"),
        ({"duration_seconds": True}, "必须是整数"),
        ({"duration_seconds": 30, "channel": 1}, "仅允许 duration_seconds"),
        ({"duration_seconds": 30, "relay": 1}, "仅允许 duration_seconds"),
    ],
)
def test_on_command_rejects_unsafe_parameters(
    client, sample_pump_device, parameters, expected_message
):
    response = client.post(
        "/api/v1/commands",
        json=command_payload(sample_pump_device["id"], "pump_on", parameters),
    )
    assert response.status_code == 422
    assert expected_message in str(response.json()["detail"])


def test_off_command_requires_empty_parameters_but_allows_duplicates(
    client, sample_pump_device
):
    invalid = client.post(
        "/api/v1/commands",
        json=command_payload(
            sample_pump_device["id"], "pump_off", {"duration_seconds": 1}
        ),
    )
    assert invalid.status_code == 422

    first = client.post(
        "/api/v1/commands",
        json=command_payload(sample_pump_device["id"], "pump_off", {}),
    )
    second = client.post(
        "/api/v1/commands",
        json=command_payload(sample_pump_device["id"], "pump_off", {}),
    )
    assert first.status_code == 201
    assert second.status_code == 201


def test_command_requires_matching_actuator_device(
    client, sample_device, sample_pump_device, sample_light_device
):
    wrong_pump = client.post(
        "/api/v1/commands",
        json=command_payload(
            sample_device["id"], "pump_on", {"duration_seconds": 30}
        ),
    )
    wrong_light = client.post(
        "/api/v1/commands",
        json=command_payload(
            sample_pump_device["id"], "light_on", {"duration_seconds": 30}
        ),
    )
    valid_light = client.post(
        "/api/v1/commands",
        json=command_payload(
            sample_light_device["id"], "light_on", {"duration_seconds": 300}
        ),
    )

    assert wrong_pump.status_code == 409
    assert "device_type=pump" in wrong_pump.json()["detail"]
    assert wrong_light.status_code == 409
    assert "device_type=grow_light" in wrong_light.json()["detail"]
    assert valid_light.status_code == 201


def test_duplicate_on_is_blocked_until_previous_command_is_terminal(
    client, sample_pump_device
):
    payload = command_payload(
        sample_pump_device["id"], "pump_on", {"duration_seconds": 30}
    )
    first = client.post("/api/v1/commands", json=payload)
    assert first.status_code == 201
    assert client.post("/api/v1/commands", json=payload).status_code == 409

    command_id = first.json()["id"]
    acknowledged = client.post(
        f"/api/v1/commands/{command_id}/ack",
        json={"status": "acknowledged"},
    )
    assert acknowledged.status_code == 200
    assert client.post("/api/v1/commands", json=payload).status_code == 409

    failed = client.post(
        f"/api/v1/commands/{command_id}/ack",
        json={"status": "failed", "actuator_state": "off"},
    )
    assert failed.status_code == 200
    assert client.post("/api/v1/commands", json=payload).status_code == 201


def test_command_cannot_skip_acknowledged_state(client, sample_pump_device):
    created = client.post(
        "/api/v1/commands",
        json=command_payload(
            sample_pump_device["id"], "pump_on", {"duration_seconds": 1}
        ),
    )
    response = client.post(
        f"/api/v1/commands/{created.json()['id']}/ack",
        json={"status": "succeeded", "actuator_state": "off"},
    )
    assert response.status_code == 409


def test_device_creation_rejects_non_http_transport(client, sample_plot):
    response = client.post(
        "/api/v1/devices",
        json={
            "plot_id": sample_plot["id"],
            "device_code": "mqtt-pump-001",
            "name": "错误通信设备",
            "device_type": "pump",
            "communication_type": "mqtt",
        },
    )
    assert response.status_code == 422

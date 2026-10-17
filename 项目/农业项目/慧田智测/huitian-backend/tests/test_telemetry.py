from datetime import datetime, timezone


def telemetry_payload(device_code: str, value: float = 28.0) -> dict:
    return {
        "device_code": device_code,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "readings": [
            {
                "metric": "air_temperature",
                "value": value,
                "unit": "celsius",
                "quality": "good",
            }
        ],
    }


def test_http_telemetry_and_latest(client, sample_device):
    response = client.post(
        "/api/v1/telemetry",
        json=telemetry_payload(sample_device["device_code"]),
    )
    assert response.status_code == 201
    assert response.json()["saved_count"] == 1

    latest = client.get(f"/api/v1/telemetry/latest/{sample_device['device_code']}")
    assert latest.status_code == 200
    assert latest.json()["readings"][0]["value"] == 28.0


def test_unknown_device_telemetry_returns_404(client):
    response = client.post(
        "/api/v1/telemetry",
        json=telemetry_payload("missing-device"),
    )
    assert response.status_code == 404


from datetime import datetime, timezone


def test_threshold_creates_and_updates_alert(client, sample_plot, sample_device):
    rule = client.post(
        "/api/v1/alerts/rules",
        json={
            "plot_id": sample_plot["id"],
            "name": "高温告警",
            "metric": "air_temperature",
            "operator": "gt",
            "threshold": 32,
            "severity": "warning",
            "enabled": True,
            "message": "空气温度过高",
        },
    )
    assert rule.status_code == 201

    telemetry = client.post(
        "/api/v1/telemetry",
        json={
            "device_code": sample_device["device_code"],
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "readings": [
                {
                    "metric": "air_temperature",
                    "value": 35,
                    "unit": "celsius",
                    "quality": "good",
                }
            ],
        },
    )
    assert telemetry.status_code == 201
    assert telemetry.json()["alert_count"] == 1

    alerts = client.get("/api/v1/alerts").json()
    assert len(alerts) == 1
    alert_id = alerts[0]["id"]

    acknowledged = client.post(f"/api/v1/alerts/{alert_id}/acknowledge")
    assert acknowledged.status_code == 200
    assert acknowledged.json()["status"] == "acknowledged"

    resolved = client.post(f"/api/v1/alerts/{alert_id}/resolve")
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"


def test_repeated_or_suspect_readings_do_not_duplicate_active_alerts(
    client, sample_plot, sample_device
):
    client.post(
        "/api/v1/alerts/rules",
        json={
            "plot_id": sample_plot["id"],
            "name": "缺水告警",
            "metric": "soil_moisture",
            "operator": "lt",
            "threshold": 30,
            "severity": "critical",
            "enabled": True,
            "message": "土壤湿度过低",
        },
    )

    def post_reading(quality: str):
        return client.post(
            "/api/v1/telemetry",
            json={
                "device_code": sample_device["device_code"],
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "readings": [
                    {
                        "metric": "soil_moisture",
                        "value": 0,
                        "unit": "percent",
                        "quality": quality,
                    }
                ],
            },
        )

    assert post_reading("suspect").json()["alert_count"] == 0
    assert post_reading("good").json()["alert_count"] == 1
    assert post_reading("good").json()["alert_count"] == 0
    assert len(client.get("/api/v1/alerts").json()) == 1

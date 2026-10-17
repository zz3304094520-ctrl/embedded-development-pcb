import json
import random
import signal
import time
from datetime import datetime, timezone
from threading import Event
from typing import Any

import httpx
import paho.mqtt.client as mqtt

from device_gateway.config import gateway_settings


stop_event = Event()


def generate_readings(device_code: str) -> list[dict[str, Any]]:
    if "soil" in device_code.lower():
        return [
            {
                "metric": "soil_temperature",
                "value": round(random.uniform(18, 28), 1),
                "unit": "celsius",
                "quality": "good",
            },
            {
                "metric": "soil_moisture",
                "value": round(random.uniform(25, 70), 1),
                "unit": "percent",
                "quality": "good",
            },
            {
                "metric": "soil_ec",
                "value": round(random.uniform(0.5, 2.2), 2),
                "unit": "mS/cm",
                "quality": "good",
            },
        ]
    return [
        {
            "metric": "air_temperature",
            "value": round(random.uniform(20, 36), 1),
            "unit": "celsius",
            "quality": "good",
        },
        {
            "metric": "air_humidity",
            "value": round(random.uniform(45, 90), 1),
            "unit": "percent",
            "quality": "good",
        },
        {
            "metric": "light_intensity",
            "value": round(random.uniform(5000, 60000), 0),
            "unit": "lux",
            "quality": "good",
        },
    ]


def build_payload() -> dict[str, Any]:
    return {
        "device_code": gateway_settings.device_code,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "readings": generate_readings(gateway_settings.device_code),
    }


def ensure_http_device(client: httpx.Client) -> None:
    response = client.get("/api/v1/devices")
    response.raise_for_status()
    if any(item["device_code"] == gateway_settings.device_code for item in response.json()):
        return

    farms = client.get("/api/v1/farms").json()
    if farms:
        farm_id = farms[0]["id"]
    else:
        farm = client.post(
            "/api/v1/farms",
            json={
                "name": "模拟器自动创建农场",
                "location": "本地演示",
                "description": "由设备模拟器创建",
            },
        )
        farm.raise_for_status()
        farm_id = farm.json()["id"]

    plots = client.get("/api/v1/plots", params={"farm_id": farm_id}).json()
    if plots:
        plot_id = plots[0]["id"]
    else:
        plot = client.post(
            "/api/v1/plots",
            json={
                "farm_id": farm_id,
                "name": "模拟器地块",
                "crop_type": "番茄",
                "area": 1,
            },
        )
        plot.raise_for_status()
        plot_id = plot.json()["id"]

    device_type = "soil_sensor" if "soil" in gateway_settings.device_code else "weather_station"
    device = client.post(
        "/api/v1/devices",
        json={
            "plot_id": plot_id,
            "device_code": gateway_settings.device_code,
            "name": f"模拟设备 {gateway_settings.device_code}",
            "device_type": device_type,
            "communication_type": gateway_settings.mode,
        },
    )
    device.raise_for_status()
    print(f"已自动创建设备：{gateway_settings.device_code}")


def run_http_mode() -> None:
    print(
        f"HTTP 模拟器启动：{gateway_settings.device_code} -> "
        f"{gateway_settings.api_base_url}，按 Ctrl+C 停止"
    )
    with httpx.Client(base_url=gateway_settings.api_base_url, timeout=10) as client:
        while not stop_event.is_set():
            try:
                ensure_http_device(client)
                response = client.post("/api/v1/telemetry", json=build_payload())
                response.raise_for_status()
                result = response.json()
                print(
                    f"上报成功：保存 {result['saved_count']} 条，"
                    f"触发 {result['alert_count']} 条告警"
                )
            except httpx.HTTPError as exc:
                print(f"上报失败：{exc}。请确认 FastAPI 已启动。")
            stop_event.wait(gateway_settings.interval_seconds)


def run_mqtt_mode() -> None:
    try:
        with httpx.Client(base_url=gateway_settings.api_base_url, timeout=5) as http_client:
            ensure_http_device(http_client)
    except httpx.HTTPError as exc:
        print(f"无法通过 API 自动确认设备：{exc}。将继续尝试 MQTT 上报。")

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"simulator-{gateway_settings.device_code}",
    )
    prefix = gateway_settings.mqtt_topic_prefix
    command_topic = f"{prefix}/{gateway_settings.device_code}/command"
    ack_topic = f"{prefix}/{gateway_settings.device_code}/command_ack"

    def on_connect(
        mqtt_client: mqtt.Client,
        _userdata: Any,
        _flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        _properties: mqtt.Properties | None,
    ) -> None:
        if reason_code.is_failure:
            print(f"MQTT 连接失败：{reason_code}")
            return
        mqtt_client.subscribe(command_topic, qos=1)
        mqtt_client.publish(
            f"{prefix}/{gateway_settings.device_code}/status",
            json.dumps({"is_online": True}),
            qos=1,
            retain=True,
        )
        print(f"MQTT 已连接并监听命令：{command_topic}")

    def on_message(
        mqtt_client: mqtt.Client, _userdata: Any, message: mqtt.MQTTMessage
    ) -> None:
        command = json.loads(message.payload.decode("utf-8"))
        print(f"收到控制命令：{command}")
        mqtt_client.publish(
            ack_topic,
            json.dumps(
                {"command_id": command["command_id"], "status": "succeeded"},
                ensure_ascii=False,
            ),
            qos=1,
        )

    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(gateway_settings.mqtt_host, gateway_settings.mqtt_port, 60)
    client.loop_start()
    print(f"MQTT 模拟器启动：{gateway_settings.device_code}，按 Ctrl+C 停止")
    try:
        while not stop_event.is_set():
            topic = f"{prefix}/{gateway_settings.device_code}/telemetry"
            client.publish(topic, json.dumps(build_payload(), ensure_ascii=False), qos=1)
            stop_event.wait(gateway_settings.interval_seconds)
    finally:
        client.publish(
            f"{prefix}/{gateway_settings.device_code}/status",
            json.dumps({"is_online": False}),
            qos=1,
            retain=True,
        )
        client.disconnect()
        client.loop_stop()


def read_modbus_registers() -> list[dict[str, Any]]:
    """未来接入 pymodbus 时替换此函数，返回格式与 generate_readings 相同。"""
    return generate_readings(gateway_settings.device_code)


def request_stop(_signum: int, _frame: Any) -> None:
    stop_event.set()


def main() -> None:
    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    if gateway_settings.mode.lower() == "mqtt":
        run_mqtt_mode()
    else:
        run_http_mode()
    time.sleep(0.1)
    print("设备模拟器已停止")


if __name__ == "__main__":
    main()

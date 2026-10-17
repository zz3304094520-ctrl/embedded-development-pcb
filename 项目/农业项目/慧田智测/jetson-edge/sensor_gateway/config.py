"""Configuration loader for the sensor gateway."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .drivers import DRIVERS


@dataclass(frozen=True)
class SensorConfig:
    name: str
    device_code: str
    driver: str
    port: str
    baudrate: int
    slave_address: int
    timeout_seconds: float = 1.2
    enabled: bool = True
    disabled_reason: str = ""


@dataclass(frozen=True)
class GatewayConfig:
    backend_url: str
    poll_interval_seconds: float
    http_timeout_seconds: float
    offline_after_failures: int
    sensors: tuple[SensorConfig, ...]


def _positive_number(data: dict[str, Any], key: str, default: float) -> float:
    value = float(data.get(key, default))
    if value <= 0:
        raise ValueError(f"{key} 必须大于 0")
    return value


def load_config(path: str | Path) -> GatewayConfig:
    config_path = Path(path)
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    backend_url = str(raw.get("backend_url", "")).rstrip("/")
    if not backend_url.startswith(("http://", "https://")):
        raise ValueError("backend_url 必须使用 http:// 或 https://")

    sensors: list[SensorConfig] = []
    seen_codes: set[str] = set()
    seen_bus_addresses: set[tuple[str, int, int]] = set()
    for item in raw.get("sensors", []):
        enabled = bool(item.get("enabled", True))
        driver = str(item.get("driver", ""))
        if enabled and driver not in DRIVERS:
            raise ValueError(f"已启用设备使用未知驱动: {driver}")
        device_code = str(item.get("device_code", "")).strip()
        if not device_code or device_code in seen_codes:
            raise ValueError("device_code 不能为空且不能重复")
        seen_codes.add(device_code)
        sensor = SensorConfig(
                name=str(item.get("name", device_code)),
                device_code=device_code,
                driver=driver,
                port=str(item.get("port", "")),
                baudrate=int(item.get("baudrate", 4800)),
                slave_address=int(item.get("slave_address", 1)),
                timeout_seconds=_positive_number(item, "timeout_seconds", 1.2),
                enabled=enabled,
                disabled_reason=str(item.get("disabled_reason", "")),
            )
        bus_address = (sensor.port.casefold(), sensor.baudrate, sensor.slave_address)
        if sensor.enabled and bus_address in seen_bus_addresses:
            raise ValueError(
                "同一RS485端口和波特率上的从机地址不能重复: "
                f"{sensor.port}, {sensor.baudrate}bps, slave={sensor.slave_address}"
            )
        if sensor.enabled:
            seen_bus_addresses.add(bus_address)
        sensors.append(sensor)
    if not sensors:
        raise ValueError("至少需要配置一个传感器")

    failures = int(raw.get("offline_after_failures", 2))
    if failures < 1:
        raise ValueError("offline_after_failures 必须大于等于 1")
    return GatewayConfig(
        backend_url=backend_url,
        poll_interval_seconds=_positive_number(raw, "poll_interval_seconds", 5),
        http_timeout_seconds=_positive_number(raw, "http_timeout_seconds", 3),
        offline_after_failures=failures,
        sensors=tuple(sensors),
    )

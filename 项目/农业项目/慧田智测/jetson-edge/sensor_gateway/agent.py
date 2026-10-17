"""Polling loop that isolates sensor failures and publishes only verified readings."""

from __future__ import annotations

import logging
import os
import signal
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from serial.tools import list_ports

from .config import GatewayConfig, SensorConfig
from .drivers import Reading, get_driver
from .http_client import BackendClient, BackendError
from .modbus_rtu import ModbusError, ModbusRtuClient


LOGGER = logging.getLogger("huitian.sensor_gateway")


def serial_port_exists(port: str) -> bool:
    """Return whether a POSIX device path or Windows COM port is present."""
    if os.path.exists(port):
        return True
    if os.name != "nt":
        return False
    expected = port.casefold()
    try:
        return any(item.device.casefold() == expected for item in list_ports.comports())
    except OSError:
        return False


@dataclass
class SensorState:
    online: bool | None = None
    consecutive_failures: int = 0


class SensorAgent:
    def __init__(
        self,
        config: GatewayConfig,
        backend: BackendClient | None = None,
        reader: Callable[[SensorConfig], list[Reading]] | None = None,
        port_exists: Callable[[str], bool] = serial_port_exists,
    ) -> None:
        self.config = config
        self.backend = backend or BackendClient(
            config.backend_url, config.http_timeout_seconds
        )
        self.clients: dict[str, ModbusRtuClient] = {}
        self.reader = reader or self._read_sensor
        self.port_exists = port_exists
        self.states = {sensor.device_code: SensorState() for sensor in config.sensors}
        self.stop_event = threading.Event()

    def _read_sensor(self, sensor: SensorConfig) -> list[Reading]:
        driver = get_driver(sensor.driver)
        client = self.clients.get(sensor.device_code)
        if client is None:
            client = ModbusRtuClient(
                port=sensor.port,
                baudrate=sensor.baudrate,
                slave_address=sensor.slave_address,
                timeout_seconds=sensor.timeout_seconds,
                # Open for one request and close immediately. This allows several
                # slave addresses to share one USB-RS485 adapter safely.
                persistent=False,
            )
            self.clients[sensor.device_code] = client
        return driver.read(client)

    def _discard_client(self, sensor: SensorConfig) -> None:
        client = self.clients.pop(sensor.device_code, None)
        if client is not None:
            client.close()

    def _report_offline(self, sensor: SensorConfig, state: SensorState) -> None:
        if state.online is False:
            return
        try:
            self.backend.post_status(sensor.device_code, False)
        except BackendError as exc:
            LOGGER.warning("%s 离线状态上报失败: %s", sensor.name, exc)
            return
        state.online = False
        LOGGER.warning("%s 已标记离线", sensor.name)

    def _record_sensor_failure(
        self, sensor: SensorConfig, state: SensorState, error: Exception
    ) -> str:
        state.consecutive_failures += 1
        LOGGER.warning(
            "%s 读取失败 (%s/%s): %s",
            sensor.name,
            state.consecutive_failures,
            self.config.offline_after_failures,
            error,
        )
        if state.consecutive_failures >= self.config.offline_after_failures:
            self._report_offline(sensor, state)
        return "sensor_error"

    def poll_sensor(self, sensor: SensorConfig) -> str:
        state = self.states[sensor.device_code]
        if not sensor.enabled:
            return "disabled"
        if not self.port_exists(sensor.port):
            self._discard_client(sensor)
            return self._record_sensor_failure(
                sensor, state, FileNotFoundError(f"串口不存在: {sensor.port}")
            )
        try:
            readings = self.reader(sensor)
        except (ModbusError, OSError, ValueError) as exc:
            self._discard_client(sensor)
            return self._record_sensor_failure(sensor, state, exc)

        state.consecutive_failures = 0
        recorded_at = datetime.now(timezone.utc)
        try:
            self.backend.post_telemetry(
                sensor.device_code,
                recorded_at,
                [reading.as_payload() for reading in readings],
            )
        except BackendError as exc:
            LOGGER.warning("%s 已采样但上报失败: %s", sensor.name, exc)
            return "upload_error"

        state.online = True
        values = ", ".join(f"{item.metric}={item.value}" for item in readings)
        LOGGER.info("%s 上报成功: %s", sensor.name, values)
        return "ok"

    def run_once(self) -> dict[str, str]:
        outcomes: dict[str, str] = {}
        for sensor in self.config.sensors:
            outcomes[sensor.device_code] = self.poll_sensor(sensor)
        return outcomes

    def run_forever(self) -> None:
        for sensor in self.config.sensors:
            if sensor.enabled:
                LOGGER.info(
                    "启用 %s: %s, %sbps, slave=%s",
                    sensor.name,
                    sensor.port,
                    sensor.baudrate,
                    sensor.slave_address,
                )
            else:
                LOGGER.warning(
                    "停用 %s: %s",
                    sensor.name,
                    sensor.disabled_reason or "协议尚未确认",
                )
        while not self.stop_event.is_set():
            started = time.monotonic()
            self.run_once()
            remaining = self.config.poll_interval_seconds - (time.monotonic() - started)
            self.stop_event.wait(max(0, remaining))

    def stop(self, *_args) -> None:
        self.stop_event.set()
        for client in self.clients.values():
            client.close()
        self.clients.clear()

    def install_signal_handlers(self) -> None:
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)

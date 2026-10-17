from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sensor_gateway.agent import SensorAgent, serial_port_exists
from sensor_gateway.config import GatewayConfig, SensorConfig, load_config
from sensor_gateway.drivers import (
    EightDirectionWindDirectionDriver,
    Reading,
    RenkeFsxcsDriver,
    SoilTempMoistureEcNpkDriver,
    WindSpeedDriver,
)
from sensor_gateway.modbus_rtu import (
    ModbusNoResponse,
    ModbusRtuClient,
    build_read_request,
    crc16,
)


class FakeSerial:
    def __init__(self, response: bytes, **_kwargs) -> None:
        self.response = bytearray(response)
        self.written = b""
        self.closed = False

    def reset_input_buffer(self) -> None:
        pass

    def write(self, data: bytes) -> None:
        self.written = data

    def flush(self) -> None:
        pass

    def read(self, size: int) -> bytes:
        result = bytes(self.response[:size])
        del self.response[:size]
        return result

    def close(self) -> None:
        self.closed = True


class FakeRegisterReader:
    def __init__(self, registers: list[int], expected_range: tuple[int, int] = (500, 14)) -> None:
        self.registers = registers
        self.expected_range = expected_range

    def read_holding_registers(self, start_register: int, count: int) -> list[int]:
        assert (start_register, count) == self.expected_range
        return self.registers


class FakeBackend:
    def __init__(self) -> None:
        self.telemetry: list[tuple[str, datetime, list[dict]]] = []
        self.statuses: list[tuple[str, bool]] = []

    def post_telemetry(self, device_code, recorded_at, readings):
        self.telemetry.append((device_code, recorded_at, readings))
        return {}

    def post_status(self, device_code, is_online):
        self.statuses.append((device_code, is_online))
        return {}


def gateway_config(enabled: bool = True, failures: int = 2) -> GatewayConfig:
    return GatewayConfig(
        backend_url="http://172.20.10.5:8000",
        poll_interval_seconds=5,
        http_timeout_seconds=3,
        offline_after_failures=failures,
        sensors=(
            SensorConfig(
                name="气象站",
                device_code="weather-001",
                driver="renke_fsxcs",
                port="/dev/weather",
                baudrate=4800,
                slave_address=1,
                enabled=enabled,
            ),
        ),
    )


class ModbusTests(unittest.TestCase):
    def test_known_request_crc(self) -> None:
        self.assertEqual(build_read_request(1, 0, 10).hex(), "01030000000ac5cd")

    def test_client_parses_valid_response_and_closes_port(self) -> None:
        body = bytes.fromhex("010304000a000b")
        response = body + crc16(body).to_bytes(2, "little")
        fake = FakeSerial(response)
        client = ModbusRtuClient("COM1", 4800, 1, serial_factory=lambda **_: fake)
        self.assertEqual(client.read_holding_registers(0, 2), [10, 11])
        self.assertEqual(fake.written, build_read_request(1, 0, 2))
        self.assertTrue(fake.closed)

    def test_client_rejects_no_response(self) -> None:
        fake = FakeSerial(b"")
        client = ModbusRtuClient(
            "COM1", 4800, 1, timeout_seconds=0.001, serial_factory=lambda **_: fake
        )
        with self.assertRaises(ModbusNoResponse):
            client.read_holding_registers(0, 1)
        self.assertTrue(fake.closed)


class DriverTests(unittest.TestCase):
    def test_weather_driver_only_exposes_verified_metrics(self) -> None:
        registers = [0, 0, 0, 0, 440, 252, 300, 0, 0, 0, 0, 6, 0, 0]
        readings = RenkeFsxcsDriver().read(FakeRegisterReader(registers))
        self.assertEqual(
            [(item.metric, item.value, item.unit) for item in readings],
            [
                ("air_temperature", 25.2, "celsius"),
                ("air_humidity", 44.0, "percent"),
                ("illumination", 6.0, "lux"),
                ("rainfall", 0.0, "millimeter"),
            ],
        )

    def test_weather_driver_decodes_negative_temperature(self) -> None:
        registers = [0, 0, 0, 0, 500, 0xFFF1, 0, 0, 0, 0, 0, 1, 0, 0]
        readings = RenkeFsxcsDriver().read(FakeRegisterReader(registers))
        self.assertEqual(readings[0].value, -1.5)

    def test_soil_six_parameter_driver_decodes_connected_register_map(self) -> None:
        registers = [187, 426, 812, 41, 23, 96]
        readings = SoilTempMoistureEcNpkDriver().read(
            FakeRegisterReader(registers, expected_range=(0, 6))
        )
        self.assertEqual(
            [(item.metric, item.value, item.unit) for item in readings],
            [
                ("soil_temperature", 18.7, "celsius"),
                ("soil_moisture", 42.6, "percent"),
                ("soil_ec", 812.0, "microsiemens_per_centimeter"),
                ("soil_nitrogen", 41.0, "milligram_per_kilogram"),
                ("soil_phosphorus", 23.0, "milligram_per_kilogram"),
                ("soil_potassium", 96.0, "milligram_per_kilogram"),
            ],
        )

    def test_soil_six_parameter_driver_decodes_negative_temperature(self) -> None:
        registers = [0xFFF1, 0, 0, 0, 0, 0]
        readings = SoilTempMoistureEcNpkDriver().read(
            FakeRegisterReader(registers, expected_range=(0, 6))
        )
        self.assertEqual(readings[0].value, -1.5)
        self.assertEqual(readings[0].quality, "good")
        self.assertTrue(all(reading.quality == "suspect" for reading in readings[1:]))

    def test_wind_speed_driver_decodes_tenths_of_meter_per_second(self) -> None:
        readings = WindSpeedDriver().read(
            FakeRegisterReader([123], expected_range=(0, 1))
        )
        self.assertEqual(
            [(item.metric, item.value, item.unit) for item in readings],
            [("wind_speed", 12.3, "meters_per_second")],
        )

    def test_eight_direction_driver_decodes_degrees(self) -> None:
        readings = EightDirectionWindDirectionDriver().read(
            FakeRegisterReader([2, 90], expected_range=(0, 2))
        )
        self.assertEqual(
            [(item.metric, item.value, item.unit, item.quality) for item in readings],
            [("wind_direction", 90.0, "degree", "good")],
        )

    def test_eight_direction_driver_flags_inconsistent_registers(self) -> None:
        readings = EightDirectionWindDirectionDriver().read(
            FakeRegisterReader([2, 135], expected_range=(0, 2))
        )
        self.assertEqual(readings[0].quality, "suspect")


class AgentTests(unittest.TestCase):
    def test_windows_com_port_is_discovered_through_pyserial(self) -> None:
        with (
            patch("sensor_gateway.agent.os.path.exists", return_value=False),
            patch(
                "sensor_gateway.agent.list_ports.comports",
                return_value=[SimpleNamespace(device="COM6")],
            ),
        ):
            self.assertTrue(serial_port_exists("com6"))
            self.assertFalse(serial_port_exists("COM7"))

    def test_agent_posts_verified_readings(self) -> None:
        backend = FakeBackend()
        agent = SensorAgent(
            gateway_config(),
            backend=backend,
            reader=lambda _sensor: [Reading("air_temperature", 25.2, "celsius")],
            port_exists=lambda _path: True,
        )
        self.assertEqual(agent.run_once(), {"weather-001": "ok"})
        self.assertEqual(backend.telemetry[0][0], "weather-001")
        self.assertEqual(backend.telemetry[0][2][0]["value"], 25.2)

    def test_agent_marks_offline_after_failure_threshold(self) -> None:
        backend = FakeBackend()

        def fail(_sensor):
            raise ModbusNoResponse("no response")

        agent = SensorAgent(
            gateway_config(failures=2),
            backend=backend,
            reader=fail,
            port_exists=lambda _path: True,
        )
        agent.run_once()
        self.assertEqual(backend.statuses, [])
        agent.run_once()
        self.assertEqual(backend.statuses, [("weather-001", False)])
        agent.run_once()
        self.assertEqual(backend.statuses, [("weather-001", False)])

    def test_disabled_sensor_never_touches_hardware(self) -> None:
        backend = FakeBackend()
        touched = []
        agent = SensorAgent(
            gateway_config(enabled=False),
            backend=backend,
            reader=lambda sensor: touched.append(sensor) or [],
            port_exists=lambda _path: True,
        )
        self.assertEqual(agent.run_once(), {"weather-001": "disabled"})
        self.assertEqual(touched, [])


class ConfigTests(unittest.TestCase):
    def test_disabled_unconfigured_sensor_is_allowed(self) -> None:
        raw = {
            "backend_url": "http://172.20.10.5:8000",
            "sensors": [
                {
                    "name": "土壤",
                    "device_code": "soil-001",
                    "driver": "unconfigured",
                    "port": "/dev/soil",
                    "enabled": False,
                }
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            config = load_config(path)
        self.assertFalse(config.sensors[0].enabled)

    def test_duplicate_modbus_address_on_same_bus_is_rejected(self) -> None:
        raw = {
            "backend_url": "http://172.20.10.5:8000",
            "sensors": [
                {
                    "name": "风速",
                    "device_code": "wind-speed-001",
                    "driver": "wind_speed_fsjt_n01",
                    "port": "/dev/weather",
                    "baudrate": 4800,
                    "slave_address": 1,
                },
                {
                    "name": "风向",
                    "device_code": "wind-direction-001",
                    "driver": "wind_direction_fxjt_n01_8",
                    "port": "/dev/weather",
                    "baudrate": 4800,
                    "slave_address": 1,
                },
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "从机地址不能重复"):
                load_config(path)


if __name__ == "__main__":
    unittest.main()

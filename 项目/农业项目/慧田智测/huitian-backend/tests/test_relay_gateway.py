from __future__ import annotations

import pytest

from edge.relay_gateway.agent import RelayAgent
from edge.relay_gateway.cli import _report_relay_offline
from edge.relay_gateway.config import DEPLOYMENT_BACKEND_URL, Settings
from edge.relay_gateway.protocol import (
    ALL_QUERY,
    CH1_OFF,
    CH1_ON,
    CH2_OFF,
    CH2_ON,
    RelayProtocolError,
    build_frame,
    parse_status_response,
)
from edge.relay_gateway.serial_driver import RelaySerial, RelaySerialError


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class FakeRelay:
    def __init__(self) -> None:
        self.actions: list[tuple[int, bool]] = []
        self.force_off_calls = 0
        self.fail_actions: set[tuple[int, bool]] = set()
        self.query_error: Exception | None = None
        self.query_calls = 0
        self.closed = False

    def set_channel(self, channel: int, enabled: bool) -> None:
        if (channel, enabled) in self.fail_actions:
            raise OSError("injected serial failure")
        self.actions.append((channel, enabled))

    def force_all_off(self) -> None:
        self.force_off_calls += 1

    def query_all(self) -> dict[int, bool]:
        self.query_calls += 1
        if self.query_error is not None:
            raise self.query_error
        return {1: False, 2: False}

    def close(self) -> None:
        self.closed = True


class FakeBackend:
    def __init__(self) -> None:
        self.devices = {
            "pump-001": {
                "id": 1,
                "device_code": "pump-001",
                "device_type": "pump",
                "communication_type": "http",
            },
            "grow-light-001": {
                "id": 2,
                "device_code": "grow-light-001",
                "device_type": "grow_light",
                "communication_type": "http",
            },
        }
        self.commands: dict[int, dict] = {}
        self.acks: list[tuple[int, str, str | None]] = []
        self.heartbeats: list[tuple[str, str]] = []
        self.status_reports: list[tuple[str, bool]] = []

    def add_command(
        self,
        command_id: int,
        device_id: int,
        command_type: str,
        *,
        status: str = "pending",
        duration: int | None = None,
    ) -> None:
        parameters = {} if duration is None else {"duration_seconds": duration}
        self.commands[command_id] = {
            "id": command_id,
            "device_id": device_id,
            "command_type": command_type,
            "parameters_json": parameters,
            "status": status,
            "created_at": f"2026-07-22T00:00:{command_id:02d}",
        }

    def resolve_devices(self, expected: dict[str, str]) -> dict[str, dict]:
        assert expected == {"pump-001": "pump", "grow-light-001": "grow_light"}
        return self.devices

    def list_commands(self, device_id: int, status: str) -> list[dict]:
        return [
            command.copy()
            for command in sorted(
                self.commands.values(), key=lambda item: item["id"], reverse=True
            )
            if command["device_id"] == device_id and command["status"] == status
        ]

    def acknowledge(
        self, command_id: int, status: str, actuator_state: str | None = None
    ) -> dict:
        self.acks.append((command_id, status, actuator_state))
        self.commands[command_id]["status"] = status
        return self.commands[command_id].copy()

    def heartbeat(self, device_code: str, actuator_state: str) -> dict:
        self.heartbeats.append((device_code, actuator_state))
        return {"device_code": device_code, "actuator_state": actuator_state}

    def report_status(self, device_code: str, is_online: bool) -> dict:
        self.status_reports.append((device_code, is_online))
        return {"device_code": device_code, "is_online": is_online}


def settings(**overrides) -> Settings:
    values = {
        "api_base_url": DEPLOYMENT_BACKEND_URL,
        "dry_run": False,
        "heartbeat_interval_seconds": 120,
    }
    values.update(overrides)
    return Settings(**values)


def make_agent(
    backend: FakeBackend | None = None,
    relay: FakeRelay | None = None,
    clock: Clock | None = None,
) -> tuple[RelayAgent, FakeBackend, FakeRelay, Clock]:
    backend = backend or FakeBackend()
    relay = relay or FakeRelay()
    clock = clock or Clock()
    agent = RelayAgent(settings(), backend, relay, monotonic=clock)
    agent.initialize()
    return agent, backend, relay, clock


def test_protocol_frames_and_query_parser() -> None:
    assert CH1_ON == bytes.fromhex("A0 01 01 A2")
    assert CH1_OFF == bytes.fromhex("A0 01 00 A1")
    assert CH2_ON == bytes.fromhex("A0 02 01 A3")
    assert CH2_OFF == bytes.fromhex("A0 02 00 A2")
    assert ALL_QUERY == bytes.fromhex("A0 0F 02 B1")
    assert build_frame(2, 2) == bytes.fromhex("A0 02 02 A4")
    assert parse_status_response(b"CH1:OFF\r\nCH2:ON\r\n") == {1: False, 2: True}
    with pytest.raises(RelayProtocolError):
        parse_status_response(b"CH1:OFF\r\n")


def test_settings_require_env_and_reject_legacy_backend(monkeypatch) -> None:
    monkeypatch.delenv("RELAY_API_BASE_URL", raising=False)
    with pytest.raises(ValueError, match="RELAY_API_BASE_URL is required"):
        Settings.from_env()
    with pytest.raises(ValueError, match="legacy backend"):
        Settings(api_base_url="http://192.168.10.77:8000")
    with pytest.raises(ValueError, match="115200"):
        Settings(api_base_url=DEPLOYMENT_BACKEND_URL, baud_rate=9600)


def test_serial_driver_writes_binary_frames_and_probe_only_queries() -> None:
    class FakeConnection:
        def __init__(self) -> None:
            self.is_open = False
            self.writes: list[bytes] = []
            self.response = bytearray(b"CH1:OFF\r\nCH2:ON\r\n")

        def open(self) -> None:
            self.is_open = True

        def close(self) -> None:
            self.is_open = False

        def reset_input_buffer(self) -> None:
            pass

        def write(self, payload: bytes) -> int:
            self.writes.append(payload)
            return len(payload)

        def flush(self) -> None:
            pass

        @property
        def in_waiting(self) -> int:
            return len(self.response)

        def read(self, count: int) -> bytes:
            payload = bytes(self.response[:count])
            del self.response[:count]
            return payload

    connection = FakeConnection()
    relay = RelaySerial(
        port="test-port",
        dry_run=False,
        serial_factory=lambda: connection,
    )
    relay.set_channel(1, True)
    assert relay.query_all() == {1: False, 2: True}
    assert connection.writes == [CH1_ON, ALL_QUERY]


def test_serial_driver_reopens_after_usb_file_descriptor_fails() -> None:
    class FakeConnection:
        def __init__(self, *, fail_reset: bool) -> None:
            self.fail_reset = fail_reset
            self.is_open = False
            self.writes: list[bytes] = []

        def open(self) -> None:
            self.is_open = True

        def close(self) -> None:
            self.is_open = False

        def reset_input_buffer(self) -> None:
            if self.fail_reset:
                raise OSError("stale USB file descriptor")

        def write(self, payload: bytes) -> int:
            self.writes.append(payload)
            return len(payload)

        def flush(self) -> None:
            pass

    stale = FakeConnection(fail_reset=True)
    reconnected = FakeConnection(fail_reset=False)
    connections = iter((stale, reconnected))
    relay = RelaySerial(
        port="/dev/serial/by-id/test-relay",
        dry_run=False,
        serial_factory=lambda: next(connections),
    )

    with pytest.raises(Exception, match="serial write failed"):
        relay.set_channel(1, False)

    assert not stale.is_open
    relay.set_channel(1, False)
    assert reconnected.writes == [CH1_OFF]


def test_startup_forces_off_and_fails_interrupted_commands() -> None:
    backend = FakeBackend()
    backend.add_command(9, 1, "pump_on", status="acknowledged", duration=30)
    agent, backend, relay, _clock = make_agent(backend=backend)
    assert relay.force_off_calls == 1
    assert (9, "failed", "off") in backend.acks
    assert ("pump-001", "off") in backend.heartbeats
    assert ("grow-light-001", "off") in backend.heartbeats
    agent.shutdown()


def test_two_channels_use_independent_non_blocking_deadlines() -> None:
    agent, backend, relay, clock = make_agent()
    backend.add_command(1, 1, "pump_on", duration=10)
    backend.add_command(2, 2, "light_on", duration=20)

    agent.step()
    assert relay.actions == [(1, True), (2, True)]
    assert backend.commands[1]["status"] == "acknowledged"
    assert backend.commands[2]["status"] == "acknowledged"

    clock.advance(10)
    agent.step()
    assert (1, False) in relay.actions
    assert backend.commands[1]["status"] == "succeeded"
    assert backend.commands[2]["status"] == "acknowledged"
    assert agent.channels[2].is_active

    clock.advance(10)
    agent.step()
    assert (2, False) in relay.actions
    assert backend.commands[2]["status"] == "succeeded"
    agent.shutdown()


def test_off_command_interrupts_active_timer() -> None:
    agent, backend, relay, clock = make_agent()
    backend.add_command(10, 1, "pump_on", duration=60)
    agent.step()
    clock.advance(3)
    backend.add_command(11, 1, "pump_off")
    agent.step()

    assert relay.actions == [(1, True), (1, False)]
    assert backend.commands[10]["status"] == "succeeded"
    assert backend.commands[11]["status"] == "succeeded"
    assert not agent.channels[1].is_active
    agent.shutdown()


def test_serial_exception_forces_all_off_and_fails_command() -> None:
    relay = FakeRelay()
    relay.fail_actions.add((1, True))
    agent, backend, relay, _clock = make_agent(relay=relay)
    backend.add_command(20, 1, "pump_on", duration=30)

    agent.step()

    assert relay.force_off_calls == 2  # startup plus emergency recovery
    assert backend.commands[20]["status"] == "failed"
    assert agent.channels[1].actuator_state == "off"
    assert agent.channels[2].actuator_state == "off"
    agent.shutdown()


def test_shutdown_forces_off_and_fails_active_command() -> None:
    agent, backend, relay, _clock = make_agent()
    backend.add_command(30, 2, "light_on", duration=30)
    agent.step()
    agent.shutdown()

    assert relay.force_off_calls == 2
    assert backend.commands[30]["status"] == "failed"
    assert relay.closed


def test_periodic_heartbeat_probes_usb_relay() -> None:
    agent, _backend, relay, clock = make_agent(
        clock=Clock(),
    )
    agent.settings = settings(heartbeat_interval_seconds=1)
    clock.advance(1)

    agent.step()

    assert relay.query_calls == 1
    agent.shutdown()


def test_periodic_probe_exposes_usb_unplug() -> None:
    agent, _backend, relay, clock = make_agent()
    agent.settings = settings(heartbeat_interval_seconds=1)
    relay.query_error = RelaySerialError("USB relay disconnected")
    clock.advance(1)

    with pytest.raises(RelaySerialError, match="disconnected"):
        agent.step()
    agent.shutdown()


def test_offline_report_marks_both_actuators_offline() -> None:
    backend = FakeBackend()

    _report_relay_offline(backend)

    assert backend.status_reports == [
        ("pump-001", False),
        ("grow-light-001", False),
    ]

"""Single-process, non-blocking HTTP relay Agent."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from threading import Event
from typing import Any

from .config import LIGHT_DEVICE_CODE, PUMP_DEVICE_CODE, Settings
from .http_client import BackendClient, BackendError
from .serial_driver import RelaySerial


LOGGER = logging.getLogger("huitian.relay.agent")


@dataclass(frozen=True, slots=True)
class ChannelSpec:
    channel: int
    device_code: str
    device_type: str
    on_command: str
    off_command: str


PUMP_SPEC = ChannelSpec(1, PUMP_DEVICE_CODE, "pump", "pump_on", "pump_off")
LIGHT_SPEC = ChannelSpec(
    2, LIGHT_DEVICE_CODE, "grow_light", "light_on", "light_off"
)
CHANNEL_SPECS = (PUMP_SPEC, LIGHT_SPEC)


@dataclass(slots=True)
class ChannelRuntime:
    spec: ChannelSpec
    device_id: int | None = None
    actuator_state: str = "off"
    active_command_id: int | None = None
    deadline: float | None = None

    @property
    def is_active(self) -> bool:
        return self.active_command_id is not None

    def clear_timer(self) -> None:
        self.active_command_id = None
        self.deadline = None


class RelayAgent:
    def __init__(
        self,
        settings: Settings,
        backend: BackendClient,
        relay: RelaySerial,
        *,
        monotonic: Any = time.monotonic,
        stop_event: Event | None = None,
    ) -> None:
        self.settings = settings
        self.backend = backend
        self.relay = relay
        self.monotonic = monotonic
        self.stop_event = stop_event or Event()
        self.channels = {
            spec.channel: ChannelRuntime(spec=spec) for spec in CHANNEL_SPECS
        }
        self._initialized = False
        self._shutdown = False
        self._last_heartbeat = 0.0

    @property
    def has_active_timers(self) -> bool:
        return any(runtime.is_active for runtime in self.channels.values())

    def initialize(self) -> None:
        if self._initialized:
            return

        # Hardware safety comes before any network recovery work.
        self.relay.force_all_off()
        for runtime in self.channels.values():
            runtime.actuator_state = "off"
            runtime.clear_timer()

        expected = {
            runtime.spec.device_code: runtime.spec.device_type
            for runtime in self.channels.values()
        }
        devices = self.backend.resolve_devices(expected)
        for runtime in self.channels.values():
            runtime.device_id = int(devices[runtime.spec.device_code]["id"])
            self.backend.heartbeat(runtime.spec.device_code, "off")

        # An acknowledged command was interrupted by a prior Agent exit. The
        # physical startup OFF above makes "failed/off" the only honest state.
        for runtime in self.channels.values():
            assert runtime.device_id is not None
            for command in self.backend.list_commands(
                runtime.device_id, "acknowledged"
            ):
                command_id = self._command_id(command)
                self.backend.acknowledge(command_id, "failed", "off")

        self._last_heartbeat = self.monotonic()
        self._initialized = True
        LOGGER.info(
            "relay Agent initialized: backend=%s dry_run=%s",
            self.settings.api_base_url,
            self.settings.dry_run,
        )

    @staticmethod
    def _command_id(command: dict[str, Any]) -> int:
        try:
            return int(command["id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise BackendError(f"command has no valid integer id: {command!r}") from exc

    def _duration(self, command: dict[str, Any]) -> int:
        parameters = command.get("parameters_json")
        if not isinstance(parameters, dict):
            raise ValueError("ON command parameters_json must be an object")
        value = parameters.get("duration_seconds")
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("duration_seconds must be an integer")
        if not 1 <= value <= self.settings.max_duration_seconds:
            raise ValueError(
                "duration_seconds must be in "
                f"[1, {self.settings.max_duration_seconds}]"
            )
        return value

    def _runtime_by_device_id(self) -> dict[int, ChannelRuntime]:
        return {
            runtime.device_id: runtime
            for runtime in self.channels.values()
            if runtime.device_id is not None
        }

    @staticmethod
    def _sort_key(command: dict[str, Any]) -> tuple[str, int]:
        created_at = str(command.get("created_at") or "")
        try:
            command_id = int(command.get("id", 0))
        except (TypeError, ValueError):
            command_id = 0
        return created_at, command_id

    def _pending_commands(self) -> list[dict[str, Any]]:
        commands: list[dict[str, Any]] = []
        for runtime in self.channels.values():
            assert runtime.device_id is not None
            commands.extend(
                self.backend.list_commands(runtime.device_id, "pending")
            )
        return sorted(commands, key=self._sort_key)

    def _execute_on(
        self,
        runtime: ChannelRuntime,
        command_id: int,
        command: dict[str, Any],
    ) -> None:
        if runtime.is_active:
            raise RuntimeError(
                f"{runtime.spec.device_code} already has active ON command "
                f"{runtime.active_command_id}"
            )
        duration = self._duration(command)
        self.relay.set_channel(runtime.spec.channel, True)
        runtime.actuator_state = "on"
        self.backend.heartbeat(runtime.spec.device_code, "on")
        runtime.active_command_id = command_id
        runtime.deadline = self.monotonic() + duration
        LOGGER.info(
            "command %s started %s for %ss",
            command_id,
            runtime.spec.device_code,
            duration,
        )

    def _execute_off(self, runtime: ChannelRuntime, command_id: int) -> None:
        interrupted_id = runtime.active_command_id
        self.relay.set_channel(runtime.spec.channel, False)
        runtime.actuator_state = "off"
        self.backend.heartbeat(runtime.spec.device_code, "off")
        if interrupted_id is not None:
            self.backend.acknowledge(interrupted_id, "succeeded", "off")
            runtime.clear_timer()
        self.backend.acknowledge(command_id, "succeeded", "off")
        LOGGER.info("command %s stopped %s", command_id, runtime.spec.device_code)

    def _execute_acknowledged(
        self,
        runtime: ChannelRuntime,
        command_id: int,
        command: dict[str, Any],
    ) -> None:
        command_type = command.get("command_type")
        if command_type == runtime.spec.on_command:
            self._execute_on(runtime, command_id, command)
            return
        if command_type == runtime.spec.off_command:
            self._execute_off(runtime, command_id)
            return
        raise ValueError(
            f"command {command_type!r} is invalid for {runtime.spec.device_code}"
        )

    def _best_effort_heartbeat(self, runtime: ChannelRuntime, state: str) -> None:
        if runtime.device_id is None:
            return
        try:
            self.backend.heartbeat(runtime.spec.device_code, state)
        except Exception as exc:
            LOGGER.error(
                "failed to heartbeat %s=%s during recovery: %s",
                runtime.spec.device_code,
                state,
                exc,
            )

    def _best_effort_fail(self, command_id: int, state: str) -> None:
        try:
            self.backend.acknowledge(command_id, "failed", state)
        except Exception as exc:
            LOGGER.error("failed to mark command %s failed: %s", command_id, exc)

    def _emergency_fail(self, primary_command_id: int, error: Exception) -> None:
        LOGGER.exception(
            "command %s failed; forcing both relay channels OFF",
            primary_command_id,
            exc_info=error,
        )
        state = "off"
        try:
            self.relay.force_all_off()
        except Exception as off_error:
            state = "unknown"
            LOGGER.critical("emergency OFF failed: %s", off_error)

        command_ids = {primary_command_id}
        for runtime in self.channels.values():
            if runtime.active_command_id is not None:
                command_ids.add(runtime.active_command_id)
            runtime.actuator_state = state
            runtime.clear_timer()
            self._best_effort_heartbeat(runtime, state)
        for command_id in sorted(command_ids):
            self._best_effort_fail(command_id, state)

    def _handle_pending(
        self,
        runtime: ChannelRuntime,
        command: dict[str, Any],
    ) -> None:
        command_id = self._command_id(command)
        # This ACK must succeed before any serial operation is permitted.
        self.backend.acknowledge(
            command_id, "acknowledged", runtime.actuator_state
        )
        try:
            self._execute_acknowledged(runtime, command_id, command)
        except Exception as exc:
            self._emergency_fail(command_id, exc)

    def _complete_due(self) -> None:
        now = self.monotonic()
        for runtime in self.channels.values():
            if (
                runtime.active_command_id is None
                or runtime.deadline is None
                or runtime.deadline > now
            ):
                continue
            command_id = runtime.active_command_id
            try:
                self.relay.set_channel(runtime.spec.channel, False)
                runtime.actuator_state = "off"
                self.backend.heartbeat(runtime.spec.device_code, "off")
                self.backend.acknowledge(command_id, "succeeded", "off")
                runtime.clear_timer()
                LOGGER.info(
                    "command %s reached deadline; %s is OFF",
                    command_id,
                    runtime.spec.device_code,
                )
            except Exception as exc:
                self._emergency_fail(command_id, exc)

    def _periodic_heartbeat(self) -> None:
        now = self.monotonic()
        if now - self._last_heartbeat < self.settings.heartbeat_interval_seconds:
            return
        # A heartbeat must prove that the USB relay is still reachable. This
        # also drops a stale tty file descriptor after an unplug so systemd can
        # restart the Agent and reconnect through the stable by-id path.
        self.relay.query_all()
        for runtime in self.channels.values():
            self._best_effort_heartbeat(runtime, runtime.actuator_state)
        self._last_heartbeat = now

    def step(self, *, allow_new_on: bool = True) -> int:
        if not self._initialized:
            raise RuntimeError("Agent is not initialized")
        self._complete_due()
        runtime_by_device = self._runtime_by_device_id()
        processed = 0
        for command in self._pending_commands():
            try:
                device_id = int(command["device_id"])
            except (KeyError, TypeError, ValueError) as exc:
                raise BackendError(f"command has invalid device_id: {command!r}") from exc
            runtime = runtime_by_device.get(device_id)
            if runtime is None:
                raise BackendError(f"command targets unexpected device_id={device_id}")
            if not allow_new_on and command.get("command_type") == runtime.spec.on_command:
                continue
            self._handle_pending(runtime, command)
            processed += 1
        self._complete_due()
        self._periodic_heartbeat()
        return processed

    def _next_wait(self) -> float:
        wait = self.settings.poll_interval_seconds
        now = self.monotonic()
        remaining = [
            runtime.deadline - now
            for runtime in self.channels.values()
            if runtime.deadline is not None
        ]
        if remaining:
            wait = min(wait, max(0.0, min(remaining)))
        return max(0.01, wait)

    def run(self, *, once: bool = False) -> None:
        initial_poll_complete = False
        try:
            self.initialize()
            while not self.stop_event.is_set():
                try:
                    self.step(allow_new_on=not once or not initial_poll_complete)
                    initial_poll_complete = True
                except BackendError:
                    LOGGER.exception("backend temporarily unavailable")
                    if once and not initial_poll_complete:
                        raise

                if once and initial_poll_complete and not self.has_active_timers:
                    break
                self.stop_event.wait(self._next_wait())
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        if self._shutdown:
            return
        self._shutdown = True
        state = "off"
        try:
            self.relay.force_all_off()
        except Exception as exc:
            state = "unknown"
            LOGGER.critical("shutdown OFF failed: %s", exc)

        active_command_ids: set[int] = set()
        for runtime in self.channels.values():
            if runtime.active_command_id is not None:
                active_command_ids.add(runtime.active_command_id)
            runtime.actuator_state = state
            runtime.clear_timer()
            if self._initialized:
                self._best_effort_heartbeat(runtime, state)
        if self._initialized:
            for command_id in sorted(active_command_ids):
                self._best_effort_fail(command_id, state)
        self.relay.close()
        LOGGER.info("relay Agent stopped with actuator_state=%s", state)

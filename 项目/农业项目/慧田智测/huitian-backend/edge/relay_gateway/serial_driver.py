"""Fail-safe serial access for the two-channel USB relay."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from .protocol import ALL_QUERY, OP_OFF, OP_ON, build_frame, parse_status_response


LOGGER = logging.getLogger("huitian.relay.serial")


class RelaySerialError(RuntimeError):
    """Raised when the relay serial port cannot be controlled safely."""


class RelaySerial:
    """Own the serial port and expose only mapped relay operations."""

    def __init__(
        self,
        *,
        port: str,
        baud_rate: int = 115200,
        timeout_seconds: float = 0.35,
        dry_run: bool = True,
        serial_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.port = port
        self.baud_rate = baud_rate
        self.timeout_seconds = timeout_seconds
        self.dry_run = dry_run
        self._serial_factory = serial_factory
        self._connection: Any | None = None
        self.logical_states = {1: False, 2: False}

    def _new_connection(self) -> Any:
        if self._serial_factory is not None:
            return self._serial_factory()
        try:
            import serial
        except ImportError as exc:  # pragma: no cover - deployment dependency
            raise RelaySerialError(
                "pyserial is not installed; install relay_gateway/requirements.txt"
            ) from exc
        return serial.Serial()

    def _open(self) -> Any:
        if self._connection is not None and self._connection.is_open:
            return self._connection

        connection = self._new_connection()
        try:
            connection.port = self.port
            connection.baudrate = self.baud_rate
            connection.bytesize = 8
            connection.parity = "N"
            connection.stopbits = 1
            connection.timeout = self.timeout_seconds
            connection.write_timeout = 2
            connection.xonxoff = False
            connection.rtscts = False
            connection.dsrdtr = False
            connection.dtr = False
            connection.rts = False
            if hasattr(connection, "exclusive"):
                connection.exclusive = True
            connection.open()
        except Exception as exc:
            try:
                connection.close()
            except Exception:
                pass
            raise RelaySerialError(f"cannot open relay serial port {self.port}: {exc}") from exc

        self._connection = connection
        return connection

    @staticmethod
    def _reset_input(connection: Any) -> None:
        if hasattr(connection, "reset_input_buffer"):
            connection.reset_input_buffer()

    def _write_frame(self, frame: bytes) -> None:
        connection = self._open()
        try:
            self._reset_input(connection)
            written = connection.write(frame)
            connection.flush()
        except Exception as exc:
            # USB CDC keeps the old file descriptor after an unplug/replug.
            # Drop it immediately so the next retry resolves the stable
            # /dev/serial/by-id path and opens the newly enumerated ttyACM.
            self.close()
            raise RelaySerialError(f"relay serial write failed: {exc}") from exc
        if written != len(frame):
            raise RelaySerialError(
                f"relay serial write incomplete: {written}/{len(frame)} bytes"
            )

    def set_channel(self, channel: int, enabled: bool) -> bytes:
        if channel not in (1, 2):
            raise ValueError("relay channel must be 1 or 2")
        frame = build_frame(channel, OP_ON if enabled else OP_OFF)
        if self.dry_run:
            LOGGER.warning(
                "DRY-RUN: CH%s %s; serial frame not written",
                channel,
                "ON" if enabled else "OFF",
            )
        else:
            self._write_frame(frame)
        self.logical_states[channel] = enabled
        return frame

    def force_all_off(self, *, retries: int = 3) -> None:
        """Try every channel even if another channel fails."""
        if retries < 1:
            raise ValueError("retries must be positive")
        if self.dry_run:
            self.set_channel(1, False)
            self.set_channel(2, False)
            return

        pending = {1, 2}
        last_errors: dict[int, Exception] = {}
        for attempt in range(retries):
            for channel in tuple(sorted(pending)):
                try:
                    self.set_channel(channel, False)
                    pending.remove(channel)
                except Exception as exc:  # continue so the other channel is attempted
                    last_errors[channel] = exc
            if not pending:
                return
            if attempt + 1 < retries:
                time.sleep(0.1)

        details = "; ".join(
            f"CH{channel}: {last_errors.get(channel, 'unknown error')}"
            for channel in sorted(pending)
        )
        raise RelaySerialError(f"failed to force all relays OFF after {retries} tries: {details}")

    def query_all(self) -> dict[int, bool]:
        """Send only QUERY ALL and return the two firmware states.

        This intentionally bypasses ``dry_run`` because ``--probe`` is an
        explicit, read-only hardware diagnostic. It never sends ON or OFF.
        """
        connection = self._open()
        self._reset_input(connection)
        try:
            written = connection.write(ALL_QUERY)
            connection.flush()
            if written != len(ALL_QUERY):
                raise RelaySerialError(
                    f"relay query write incomplete: {written}/{len(ALL_QUERY)} bytes"
                )

            deadline = time.monotonic() + max(0.25, self.timeout_seconds * 3)
            payload = bytearray()
            while time.monotonic() < deadline:
                waiting = int(getattr(connection, "in_waiting", 0) or 0)
                chunk = connection.read(waiting or 1)
                if chunk:
                    payload.extend(chunk)
                    try:
                        return parse_status_response(bytes(payload))
                    except ValueError:
                        pass
            return parse_status_response(bytes(payload))
        except RelaySerialError:
            self.close()
            raise
        except Exception as exc:
            self.close()
            raise RelaySerialError(f"relay query failed: {exc}") from exc

    def close(self) -> None:
        connection, self._connection = self._connection, None
        if connection is not None and getattr(connection, "is_open", False):
            try:
                connection.close()
            except Exception as exc:
                LOGGER.warning("failed to close relay serial port: %s", exc)

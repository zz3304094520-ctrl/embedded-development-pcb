"""Environment-only configuration for the Jetson relay Agent."""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse


DEPLOYMENT_BACKEND_URL = "http://172.20.10.2:8000"
LEGACY_BACKEND_HOST = "192.168.10.77"
DEFAULT_SERIAL_PORT = (
    "/dev/serial/by-id/"
    "usb-STMicroelectronics_STM32_Virtual_ComPort_in_FS_Mode_"
    "7E7A69E21138-if00"
)
PUMP_DEVICE_CODE = "pump-001"
LIGHT_DEVICE_CODE = "grow-light-001"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false")


@dataclass(frozen=True, slots=True)
class Settings:
    api_base_url: str
    serial_port: str = DEFAULT_SERIAL_PORT
    baud_rate: int = 115200
    poll_interval_seconds: float = 1.0
    request_timeout_seconds: float = 5.0
    serial_timeout_seconds: float = 0.35
    heartbeat_interval_seconds: float = 15.0
    max_duration_seconds: int = 300
    dry_run: bool = True

    def __post_init__(self) -> None:
        if self.api_base_url:
            parsed = urlparse(self.api_base_url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                raise ValueError("RELAY_API_BASE_URL must be an absolute HTTP URL")
            if parsed.hostname == LEGACY_BACKEND_HOST:
                raise ValueError(
                    "legacy backend 192.168.10.77 is forbidden; use the current HTTP backend"
                )
        if not self.serial_port.strip():
            raise ValueError("RELAY_PORT must not be empty")
        if self.baud_rate != 115200:
            raise ValueError("this STM32 relay must use 115200 baud")
        if not 0 < self.poll_interval_seconds <= 60:
            raise ValueError("RELAY_POLL_INTERVAL_SECONDS must be in (0, 60]")
        if not 0 < self.request_timeout_seconds <= 60:
            raise ValueError("RELAY_REQUEST_TIMEOUT_SECONDS must be in (0, 60]")
        if not 0 < self.serial_timeout_seconds <= 10:
            raise ValueError("RELAY_SERIAL_TIMEOUT_SECONDS must be in (0, 10]")
        if not 0 < self.heartbeat_interval_seconds <= 300:
            raise ValueError("RELAY_HEARTBEAT_INTERVAL_SECONDS must be in (0, 300]")
        if not 1 <= self.max_duration_seconds <= 300:
            raise ValueError("RELAY_MAX_DURATION_SECONDS must be in [1, 300]")

    @classmethod
    def from_env(cls, *, require_backend: bool = True) -> "Settings":
        api_base_url = os.getenv("RELAY_API_BASE_URL", "").strip().rstrip("/")
        if require_backend and not api_base_url:
            raise ValueError(
                "RELAY_API_BASE_URL is required; deployment value is "
                f"{DEPLOYMENT_BACKEND_URL}"
            )
        return cls(
            api_base_url=api_base_url,
            serial_port=os.getenv("RELAY_PORT", DEFAULT_SERIAL_PORT).strip(),
            baud_rate=int(os.getenv("RELAY_BAUD_RATE", "115200")),
            poll_interval_seconds=float(
                os.getenv("RELAY_POLL_INTERVAL_SECONDS", "1")
            ),
            request_timeout_seconds=float(
                os.getenv("RELAY_REQUEST_TIMEOUT_SECONDS", "5")
            ),
            serial_timeout_seconds=float(
                os.getenv("RELAY_SERIAL_TIMEOUT_SECONDS", "0.35")
            ),
            heartbeat_interval_seconds=float(
                os.getenv("RELAY_HEARTBEAT_INTERVAL_SECONDS", "15")
            ),
            max_duration_seconds=int(
                os.getenv("RELAY_MAX_DURATION_SECONDS", "300")
            ),
            dry_run=_env_bool("RELAY_DRY_RUN", True),
        )

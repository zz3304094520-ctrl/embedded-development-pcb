"""HTTP transport for telemetry and online/offline state."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class BackendError(RuntimeError):
    pass


class BackendClient:
    def __init__(self, base_url: str, timeout_seconds: float = 3) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise BackendError(f"后端 HTTP {exc.code}: {detail}") from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise BackendError(f"后端请求失败: {exc}") from exc

    def post_telemetry(
        self,
        device_code: str,
        recorded_at: datetime,
        readings: list[dict[str, str | float]],
    ) -> dict[str, Any]:
        return self._post(
            "/api/v1/telemetry",
            {
                "device_code": device_code,
                "recorded_at": recorded_at.isoformat(),
                "readings": readings,
            },
        )

    def post_status(self, device_code: str, is_online: bool) -> dict[str, Any]:
        return self._post(
            f"/api/v1/devices/{device_code}/status",
            {"is_online": is_online},
        )

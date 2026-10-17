"""HTTP client limited to the relay Agent's existing-resource API contract."""

from __future__ import annotations

from typing import Any


class BackendError(RuntimeError):
    """Raised for network, HTTP, or response-contract failures."""


class BackendClient:
    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float,
        session: Any | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        if session is None:
            try:
                import requests
            except ImportError as exc:  # pragma: no cover - deployment dependency
                raise BackendError(
                    "requests is not installed; install relay_gateway/requirements.txt"
                ) from exc
            session = requests.Session()
        self.session = session

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = self.session.request(
                method,
                f"{self.base_url}{path}",
                timeout=self.timeout_seconds,
                **kwargs,
            )
            response.raise_for_status()
            return response
        except Exception as exc:
            raise BackendError(f"{method} {path} failed: {exc}") from exc

    @staticmethod
    def _json(response: Any, expected_type: type) -> Any:
        try:
            payload = response.json()
        except Exception as exc:
            raise BackendError(f"backend returned invalid JSON: {exc}") from exc
        if not isinstance(payload, expected_type):
            raise BackendError(
                f"backend JSON must be {expected_type.__name__}, got "
                f"{type(payload).__name__}"
            )
        return payload

    def resolve_devices(
        self, expected: dict[str, str]
    ) -> dict[str, dict[str, Any]]:
        """Resolve existing devices without ever creating backend resources."""
        devices = self._json(self._request("GET", "/api/v1/devices"), list)
        by_code = {
            item.get("device_code"): item
            for item in devices
            if isinstance(item, dict) and isinstance(item.get("device_code"), str)
        }
        resolved: dict[str, dict[str, Any]] = {}
        for code, expected_type in expected.items():
            item = by_code.get(code)
            if item is None:
                raise BackendError(
                    f"required device {code!r} does not exist; create it in the backend first"
                )
            if item.get("device_type") != expected_type:
                raise BackendError(
                    f"device {code!r} must have device_type={expected_type!r}, "
                    f"got {item.get('device_type')!r}"
                )
            if item.get("communication_type") != "http":
                raise BackendError(f"device {code!r} must use communication_type='http'")
            try:
                int(item["id"])
            except (KeyError, TypeError, ValueError) as exc:
                raise BackendError(f"device {code!r} has no valid integer id") from exc
            resolved[code] = item
        return resolved

    def list_commands(self, device_id: int, status: str) -> list[dict[str, Any]]:
        response = self._request(
            "GET",
            "/api/v1/commands",
            params={"device_id": device_id, "status_filter": status},
        )
        commands = self._json(response, list)
        if not all(isinstance(item, dict) for item in commands):
            raise BackendError("command list contains a non-object item")
        return commands

    def acknowledge(
        self,
        command_id: int,
        status: str,
        actuator_state: str | None = None,
    ) -> dict[str, Any]:
        if status not in {"acknowledged", "succeeded", "failed"}:
            raise ValueError(f"invalid command status: {status}")
        payload: dict[str, Any] = {"status": status}
        if actuator_state is not None:
            if actuator_state not in {"on", "off", "unknown"}:
                raise ValueError(f"invalid actuator state: {actuator_state}")
            payload["actuator_state"] = actuator_state
        response = self._request(
            "POST", f"/api/v1/commands/{command_id}/ack", json=payload
        )
        return self._json(response, dict)

    def heartbeat(self, device_code: str, actuator_state: str) -> dict[str, Any]:
        if actuator_state not in {"on", "off", "unknown"}:
            raise ValueError(f"invalid actuator state: {actuator_state}")
        response = self._request(
            "POST",
            f"/api/v1/devices/{device_code}/heartbeat",
            json={"actuator_state": actuator_state},
        )
        return self._json(response, dict)

    def report_status(self, device_code: str, is_online: bool) -> dict[str, Any]:
        response = self._request(
            "POST",
            f"/api/v1/devices/{device_code}/status",
            json={"is_online": is_online},
        )
        return self._json(response, dict)

    def close(self) -> None:
        close = getattr(self.session, "close", None)
        if close is not None:
            close()

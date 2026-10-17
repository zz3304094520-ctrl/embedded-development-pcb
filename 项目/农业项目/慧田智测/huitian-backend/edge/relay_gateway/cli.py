"""Command-line entry point for the Jetson relay Agent."""

from __future__ import annotations

import argparse
import json
import logging
import signal
from threading import Event
from typing import Sequence

from .agent import RelayAgent
from .config import LIGHT_DEVICE_CODE, PUMP_DEVICE_CODE, Settings
from .http_client import BackendClient
from .serial_driver import RelaySerial, RelaySerialError


LOGGER = logging.getLogger("huitian.relay")


def _report_relay_offline(backend: BackendClient | None) -> None:
    if backend is None:
        return
    for device_code in (PUMP_DEVICE_CODE, LIGHT_DEVICE_CODE):
        try:
            backend.report_status(device_code, False)
        except Exception as exc:
            LOGGER.error("failed to report %s offline: %s", device_code, exc)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="慧田智测 Jetson HTTP 双路继电器 Agent")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--probe",
        action="store_true",
        help="只发送串口 QUERY ALL；不访问后端、不发送 ON/OFF",
    )
    modes.add_argument(
        "--once",
        action="store_true",
        help="读取一次 ON；继续处理紧急 OFF，直到本轮定时任务结束",
    )
    return parser


def _serial_from_settings(settings: Settings) -> RelaySerial:
    return RelaySerial(
        port=settings.serial_port,
        baud_rate=settings.baud_rate,
        timeout_seconds=settings.serial_timeout_seconds,
        dry_run=settings.dry_run,
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    backend: BackendClient | None = None
    relay: RelaySerial | None = None
    try:
        settings = Settings.from_env(require_backend=not args.probe)
        relay = _serial_from_settings(settings)

        if args.probe:
            states = relay.query_all()
            print(
                json.dumps(
                    {f"CH{channel}": "ON" if enabled else "OFF" for channel, enabled in states.items()},
                    ensure_ascii=False,
                )
            )
            return 0

        backend = BackendClient(
            base_url=settings.api_base_url,
            timeout_seconds=settings.request_timeout_seconds,
        )
        stop_event = Event()

        def request_stop(signum: int, _frame: object) -> None:
            LOGGER.warning("received signal %s; requesting fail-safe shutdown", signum)
            stop_event.set()

        signal.signal(signal.SIGINT, request_stop)
        signal.signal(signal.SIGTERM, request_stop)

        agent = RelayAgent(
            settings,
            backend,
            relay,
            stop_event=stop_event,
        )
        agent.run(once=args.once)
        return 0
    except RelaySerialError:
        _report_relay_offline(backend)
        LOGGER.exception(
            "USB relay is offline; systemd will retry and reconnect automatically"
        )
        return 1
    except Exception:
        LOGGER.exception("relay Agent terminated with an error")
        return 1
    finally:
        if relay is not None:
            relay.close()
        if backend is not None:
            backend.close()

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from .agent import SensorAgent
from .config import load_config


def main() -> int:
    parser = argparse.ArgumentParser(description="慧田智测 Jetson RS485 传感器网关")
    parser.add_argument(
        "--config",
        default=str(Path(__file__).with_name("config.json")),
        help="JSON 配置文件路径",
    )
    parser.add_argument("--once", action="store_true", help="只采样一次后退出")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    agent = SensorAgent(load_config(args.config))
    if args.once:
        print(json.dumps(agent.run_once(), ensure_ascii=False))
        return 0
    agent.install_signal_handlers()
    agent.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx


ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

BASE_URL = "http://172.20.10.2:8000"


def show(title: str, response: httpx.Response) -> dict | list:
    response.raise_for_status()
    data = response.json()
    print(f"\n[{title}] HTTP {response.status_code}")
    print(data)
    return data


def main() -> None:
    try:
        with httpx.Client(base_url=BASE_URL, timeout=10) as client:
            show("健康检查", client.get("/api/v1/health"))
            devices = show("查询设备", client.get("/api/v1/devices"))
            weather = next(item for item in devices if item["device_code"] == "weather-001")

            normal_payload = {
                "device_code": "weather-001",
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "readings": [
                    {
                        "metric": "air_temperature",
                        "value": 27.5,
                        "unit": "celsius",
                        "quality": "good",
                    }
                ],
            }
            show("上报正常数据", client.post("/api/v1/telemetry", json=normal_payload))

            warning_payload = {
                **normal_payload,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "readings": [
                    {
                        "metric": "air_temperature",
                        "value": 35.2,
                        "unit": "celsius",
                        "quality": "good",
                    }
                ],
            }
            show("上报告警数据", client.post("/api/v1/telemetry", json=warning_payload))
            show("查询告警", client.get("/api/v1/alerts"))
            show(
                "创建水泵命令",
                client.post(
                    "/api/v1/commands",
                    json={
                        "device_id": weather["id"],
                        "command_type": "pump_on",
                        "parameters": {"duration_seconds": 30},
                    },
                ),
            )
            print("\n完整演示流程执行成功。")
    except (httpx.HTTPError, StopIteration) as exc:
        print(f"演示失败：{exc}")
        print("请先执行 start.ps1 或 uvicorn app.main:app --reload。")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()

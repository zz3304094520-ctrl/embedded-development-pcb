import sys
from pathlib import Path

from sqlalchemy import select


ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app import models  # noqa: E402
from app.database import SessionLocal, init_database  # noqa: E402


def main() -> None:
    init_database()
    with SessionLocal() as db:
        farm = db.scalar(select(models.Farm).where(models.Farm.name == "金山番茄示范农场"))
        if not farm:
            farm = models.Farm(
                name="金山番茄示范农场",
                location="上海市金山区",
                description="慧田智测本地演示农场",
            )
            db.add(farm)
            db.flush()

        plot = db.scalar(
            select(models.Plot).where(
                models.Plot.farm_id == farm.id,
                models.Plot.name == "A1 番茄试验田",
            )
        )
        if not plot:
            plot = models.Plot(
                farm_id=farm.id,
                name="A1 番茄试验田",
                crop_type="番茄",
                area=3.5,
            )
            db.add(plot)
            db.flush()

        devices = [
            ("weather-001", "A1 多功能气象仪", "weather_station", "http"),
            ("wind-speed-001", "A1 三杯式风速传感器", "wind_speed_sensor", "http"),
            ("wind-direction-001", "A1 八方位风向传感器", "wind_direction_sensor", "http"),
            ("soil-001", "A1 土壤传感器", "soil_sensor", "http"),
            ("pump-001", "A1 灌溉水泵", "pump", "http"),
            ("grow-light-001", "A1 作物补光灯", "grow_light", "http"),
            ("edge-orin-001", "Jetson D435i 智能巡检节点", "camera", "http"),
        ]
        for device_code, name, device_type, communication_type in devices:
            exists = db.scalar(
                select(models.Device).where(models.Device.device_code == device_code)
            )
            if not exists:
                db.add(
                    models.Device(
                        plot_id=plot.id,
                        device_code=device_code,
                        name=name,
                        device_type=device_type,
                        communication_type=communication_type,
                    )
                )

        rules = [
            (
                "空气高温预警",
                "air_temperature",
                "gt",
                32.0,
                "warning",
                "空气温度过高，请检查通风和遮阳",
            ),
            (
                "土壤缺水预警",
                "soil_moisture",
                "lt",
                30.0,
                "critical",
                "土壤湿度过低，请检查灌溉系统",
            ),
        ]
        for name, metric, op, threshold, severity, message in rules:
            exists = db.scalar(
                select(models.AlertRule).where(
                    models.AlertRule.plot_id == plot.id,
                    models.AlertRule.name == name,
                )
            )
            if not exists:
                db.add(
                    models.AlertRule(
                        plot_id=plot.id,
                        name=name,
                        metric=metric,
                        operator=op,
                        threshold=threshold,
                        severity=severity,
                        message=message,
                    )
                )

        db.commit()
        print("演示数据初始化完成（可重复执行，不会重复创建）。")
        print(f"农场 ID：{farm.id}，地块 ID：{plot.id}")


if __name__ == "__main__":
    main()

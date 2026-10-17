"""Register maps that have been verified against the connected hardware."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class RegisterReader(Protocol):
    def read_holding_registers(self, start_register: int, count: int) -> list[int]: ...


@dataclass(frozen=True)
class Reading:
    metric: str
    value: float
    unit: str
    quality: str = "good"

    def as_payload(self) -> dict[str, str | float]:
        return {
            "metric": self.metric,
            "value": self.value,
            "unit": self.unit,
            "quality": self.quality,
        }


def signed_int16(value: int) -> int:
    return value - 0x10000 if value & 0x8000 else value


class RenkeFsxcsDriver:
    """Verified subset of the RS-FSXCS-N01 register map used by SN-3003-FSXCS-MD1."""

    name = "renke_fsxcs"

    def read(self, client: RegisterReader) -> list[Reading]:
        registers = client.read_holding_registers(500, 14)
        humidity = registers[4] / 10.0
        temperature = signed_int16(registers[5]) / 10.0
        illumination = float((registers[10] << 16) | registers[11])
        rainfall = registers[13] / 10.0

        if not 0 <= humidity <= 100:
            raise ValueError(f"空气湿度越界: {humidity}")
        if not -60 <= temperature <= 100:
            raise ValueError(f"空气温度越界: {temperature}")

        return [
            Reading("air_temperature", temperature, "celsius"),
            Reading("air_humidity", humidity, "percent"),
            Reading("illumination", illumination, "lux"),
            Reading("rainfall", rainfall, "millimeter"),
        ]


class SoilTempMoistureEcNpkDriver:
    """Verified six-parameter map of the connected custom soil probe."""

    name = "soil_temp_moisture_ec_npk"

    def read(self, client: RegisterReader) -> list[Reading]:
        registers = client.read_holding_registers(0, 6)
        temperature = signed_int16(registers[0]) / 10.0
        moisture = registers[1] / 10.0
        conductivity = float(registers[2])
        nitrogen = float(registers[3])
        phosphorus = float(registers[4])
        potassium = float(registers[5])

        if not 0 <= moisture <= 100:
            raise ValueError(f"土壤湿度越界: {moisture}")
        if not -40 <= temperature <= 85:
            raise ValueError(f"土壤温度越界: {temperature}")

        contact_quality = (
            "suspect"
            if moisture == conductivity == nitrogen == phosphorus == potassium == 0
            else "good"
        )

        return [
            Reading("soil_temperature", temperature, "celsius"),
            Reading("soil_moisture", moisture, "percent", contact_quality),
            Reading("soil_ec", conductivity, "microsiemens_per_centimeter", contact_quality),
            Reading("soil_nitrogen", nitrogen, "milligram_per_kilogram", contact_quality),
            Reading("soil_phosphorus", phosphorus, "milligram_per_kilogram", contact_quality),
            Reading("soil_potassium", potassium, "milligram_per_kilogram", contact_quality),
        ]


class WindSpeedDriver:
    """ZTS/SN-3000-FSJT-N01 instantaneous wind speed register map."""

    name = "wind_speed_fsjt_n01"

    def read(self, client: RegisterReader) -> list[Reading]:
        (raw_speed,) = client.read_holding_registers(0, 1)
        speed = raw_speed / 10.0
        if not 0 <= speed <= 70:
            raise ValueError(f"风速越界: {speed}")
        return [Reading("wind_speed", speed, "meters_per_second")]


class EightDirectionWindDirectionDriver:
    """SN/ZTS-3000-FXJT-N01 eight-direction register map."""

    name = "wind_direction_fxjt_n01_8"

    def read(self, client: RegisterReader) -> list[Reading]:
        direction_index, degrees = client.read_holding_registers(0, 2)
        if not 0 <= direction_index <= 7:
            raise ValueError(f"风向档位越界: {direction_index}")
        if degrees not in range(0, 360, 45):
            raise ValueError(f"八方位角度无效: {degrees}")
        quality = "good" if degrees == direction_index * 45 else "suspect"
        return [Reading("wind_direction", float(degrees), "degree", quality)]


DRIVERS = {
    RenkeFsxcsDriver.name: RenkeFsxcsDriver(),
    SoilTempMoistureEcNpkDriver.name: SoilTempMoistureEcNpkDriver(),
    WindSpeedDriver.name: WindSpeedDriver(),
    EightDirectionWindDirectionDriver.name: EightDirectionWindDirectionDriver(),
}


def get_driver(name: str):
    try:
        return DRIVERS[name]
    except KeyError as exc:
        raise ValueError(f"未配置传感器驱动: {name}") from exc

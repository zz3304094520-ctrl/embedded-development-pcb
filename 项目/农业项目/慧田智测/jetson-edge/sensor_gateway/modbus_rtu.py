"""Small read-only Modbus RTU client used by the Jetson sensor agent."""

from __future__ import annotations

import struct
import time
from collections.abc import Callable
from typing import Any

import serial


class ModbusError(RuntimeError):
    """Base error for a rejected or missing Modbus response."""


class ModbusNoResponse(ModbusError):
    """Raised when the sensor does not return a response before timeout."""


class ModbusProtocolError(ModbusError):
    """Raised when a response has invalid addressing, length, CRC, or function."""


class ModbusDeviceError(ModbusError):
    """Raised when the slave returns a Modbus exception response."""

    def __init__(self, exception_code: int) -> None:
        self.exception_code = exception_code
        super().__init__(f"Modbus slave exception 0x{exception_code:02X}")


def crc16(data: bytes) -> int:
    """Return Modbus CRC16 as an integer; frames store it low byte first."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def build_read_request(slave_address: int, start_register: int, count: int) -> bytes:
    if not 1 <= slave_address <= 247:
        raise ValueError("slave_address 必须在 1..247")
    if not 0 <= start_register <= 0xFFFF:
        raise ValueError("start_register 必须在 0..65535")
    if not 1 <= count <= 125:
        raise ValueError("count 必须在 1..125")
    body = bytes(
        [
            slave_address,
            0x03,
            start_register >> 8,
            start_register & 0xFF,
            count >> 8,
            count & 0xFF,
        ]
    )
    return body + struct.pack("<H", crc16(body))


def parse_read_response(frame: bytes, slave_address: int, count: int) -> list[int]:
    if len(frame) < 5:
        raise ModbusProtocolError("Modbus 响应过短")
    if crc16(frame[:-2]) != int.from_bytes(frame[-2:], "little"):
        raise ModbusProtocolError("Modbus CRC 校验失败")
    if frame[0] != slave_address:
        raise ModbusProtocolError(
            f"响应地址 {frame[0]} 与请求地址 {slave_address} 不一致"
        )
    if frame[1] == 0x83:
        raise ModbusDeviceError(frame[2])
    if frame[1] != 0x03:
        raise ModbusProtocolError(f"不支持的响应功能码 0x{frame[1]:02X}")
    expected_bytes = count * 2
    if frame[2] != expected_bytes or len(frame) != expected_bytes + 5:
        raise ModbusProtocolError("Modbus 数据长度与请求寄存器数量不一致")
    return [
        int.from_bytes(frame[index : index + 2], "big")
        for index in range(3, 3 + expected_bytes, 2)
    ]


def _read_exact(connection: Any, size: int, timeout_seconds: float) -> bytes:
    deadline = time.monotonic() + timeout_seconds
    data = bytearray()
    while len(data) < size:
        chunk = connection.read(size - len(data))
        if chunk:
            data.extend(chunk)
            continue
        if time.monotonic() >= deadline:
            break
    return bytes(data)


class ModbusRtuClient:
    """Open a port for one request so USB unplug/replug cannot leave stale handles."""

    def __init__(
        self,
        port: str,
        baudrate: int,
        slave_address: int,
        timeout_seconds: float = 1.2,
        serial_factory: Callable[..., Any] = serial.Serial,
        persistent: bool = False,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.slave_address = slave_address
        self.timeout_seconds = timeout_seconds
        self.serial_factory = serial_factory
        self.persistent = persistent
        self.connection: Any | None = None

    def close(self) -> None:
        connection, self.connection = self.connection, None
        if connection is not None:
            connection.close()

    def read_holding_registers(self, start_register: int, count: int) -> list[int]:
        request = build_read_request(self.slave_address, start_register, count)
        connection = self.connection
        if connection is None:
            connection = self.serial_factory(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout_seconds,
                write_timeout=self.timeout_seconds,
            )
            if self.persistent:
                self.connection = connection
        try:
            if hasattr(connection, "reset_input_buffer"):
                connection.reset_input_buffer()
            connection.write(request)
            connection.flush()
            header = _read_exact(connection, 3, self.timeout_seconds)
            if not header:
                raise ModbusNoResponse("传感器未返回 Modbus 响应")
            if len(header) != 3:
                raise ModbusProtocolError("Modbus 响应头不完整")
            tail_size = 2 if header[1] & 0x80 else header[2] + 2
            tail = _read_exact(connection, tail_size, self.timeout_seconds)
            if len(tail) != tail_size:
                raise ModbusProtocolError("Modbus 响应体不完整")
            return parse_read_response(header + tail, self.slave_address, count)
        except Exception:
            if self.persistent:
                self.close()
            raise
        finally:
            if not self.persistent:
                connection.close()

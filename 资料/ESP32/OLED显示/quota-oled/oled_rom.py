"""Host-driven OLED on the verified ESP32-S3. No flash/eFuse writes.

GPIO/I2C register layout and timing follow ESP-IDF v5.3 for ESP32-S3.
While connected, the ESP32 is in its ROM loader; close restores and resets it.
"""
import contextlib
import time
from esptool.cmds import detect_chip
from serial.tools import list_ports

GPIO = 0x60004000
I2C = 0x60013000
SYS_CLK, SYS_RST = 0x600C0018, 0x600C0020
PERIPH_BIT = 1 << 7
BOTH = (1 << 7) | (1 << 8)
CTR_BASE = (1 << 8) | (1 << 4) | 3
FIFO_BASE = (1 << 14) | (4 << 5) | 11
NACK = 1 << 10
TIMEOUT = (1 << 8) | (1 << 13) | (1 << 14)
ARBITRATION, COMPLETE = 1 << 5, 1 << 7
PINS = {
    7: (0x60009020, GPIO + 0x90, GPIO + 0x570, 0x600084A0),
    8: (0x60009024, GPIO + 0x94, GPIO + 0x574, 0x600084A4),
}
IN_SCL, IN_SDA = GPIO + 0x2B8, GPIO + 0x2BC
EXPECTED_MAC = '28:84:85:60:dd:48'


def choose_port(preferred='COM12'):
    ports = list(list_ports.comports())
    for port in ports:
        if port.device.upper() == preferred.upper():
            return port.device
    candidates = [p.device for p in ports if (p.vid, p.pid) in
                  ((0x0403, 0x6001), (0x303A, 0x1001), (0x1A86, 0x55D3),
                   (0x1A86, 0x55D4), (0x1A86, 0x7523))]
    if len(candidates) == 1:
        return candidates[0]
    raise RuntimeError('ESP32 serial port unavailable or ambiguous')


class RomOled:
    def __init__(self, port='COM12', baud=460800):
        self.esp = None
        self.saved = {}
        self.port = choose_port(port)
        try:
            self.esp = detect_chip(port=self.port, baud=115200, connect_attempts=3)
            if self.esp.CHIP_NAME != 'ESP32-S3':
                raise RuntimeError('Unexpected chip; GPIO access refused')
            mac = ':'.join(f'{b:02x}' for b in self.esp.read_mac())
            if mac != EXPECTED_MAC:
                raise RuntimeError('Unexpected ESP32 MAC; GPIO access refused')
            if baud != 115200:
                self.esp.change_baud(baud)
                if ':'.join(f'{b:02x}' for b in self.esp.read_mac()) != EXPECTED_MAC:
                    raise RuntimeError('Baud-rate verification failed')
            self._configure()
            self.commands([0xAE, 0xD5, 0x80, 0xA8, 0x3F, 0xD3, 0, 0x40,
                           0x8D, 0x14, 0x20, 2, 0xA1, 0xC8, 0xDA, 0x12,
                           0x81, 0x7F, 0xD9, 0xF1, 0xDB, 0x40, 0xA4, 0xA6, 0x2E])
        except BaseException:
            self.close()
            raise

    def _write(self, offset, value):
        self.esp.write_reg(I2C + offset, value)

    def _read(self, offset):
        return self.esp.read_reg(I2C + offset)

    def _reset_controller(self):
        self.esp.write_reg(SYS_RST, PERIPH_BIT, mask=PERIPH_BIT)
        self.esp.write_reg(SYS_RST, 0, mask=PERIPH_BIT)

    def _configure(self):
        regs = [SYS_CLK, SYS_RST, GPIO + 4, GPIO + 0x20, IN_SCL, IN_SDA]
        regs += [reg for group in PINS.values() for reg in group]
        self.saved = {reg: self.esp.read_reg(reg) for reg in regs}
        self.esp.write_reg(SYS_CLK, PERIPH_BIT, mask=PERIPH_BIT)
        self._reset_controller()
        self._write(4, CTR_BASE)
        self.esp.write_reg(GPIO + 0x28, BOTH)
        self.esp.write_reg(GPIO + 8, BOTH)
        for pin, (mux, config, matrix, rtc) in PINS.items():
            self.esp.write_reg(rtc, self.saved[rtc] & ~(1 << 19))
            mux_value = (self.saved[mux] & ~((7 << 12) | (1 << 7)))
            mux_value |= (1 << 12) | (1 << 9) | (1 << 8)
            self.esp.write_reg(mux, mux_value)
            self.esp.write_reg(config, 1 << 2)
            self.esp.write_reg(matrix, 90 if pin == 7 else 89)
        self.esp.write_reg(IN_SDA, (1 << 7) | 7)
        self.esp.write_reg(IN_SCL, (1 << 7) | 8)
        self.esp.write_reg(GPIO + 0x24, BOTH)
        levels = self.esp.read_reg(GPIO + 0x3C)
        if levels & BOTH != BOTH:
            raise RuntimeError('I2C bus is held low')
        # 100kHz from 40MHz XTAL; same timing as the successful diagnostic.
        half, wait_high, high = 200, 98, 102
        self._write(0x54, 1 << 21)
        self._write(0, half - 1)
        self._write(0x38, high | (wait_high << 9))
        self._write(0x30, half // 4 - 1)
        self._write(0x34, half // 2 - 1)
        for offset in (0x40, 0x44, 0x48, 0x4C):
            self._write(offset, half - 1)
        self._write(0x0C, (1 << 5) | 20)
        self._write(0x78, 20)
        self._write(0x7C, 20)
        self._write(0x50, (1 << 9) | (1 << 8) | (3 << 4) | 3)
        self._write(0x28, 0)
        self._write(0x18, FIFO_BASE | (1 << 12) | (1 << 13))
        self._write(0x18, FIFO_BASE)
        self._write(0x24, 0x3FFFF)
        self._write(4, CTR_BASE | (1 << 11))

    def send(self, control, payload):
        packet = bytes([0x3C << 1, control]) + bytes(payload)
        if not 2 <= len(packet) <= 32:
            raise ValueError('Packet exceeds I2C FIFO capacity')
        self._write(4, CTR_BASE | (1 << 10))
        self._write(0x18, FIFO_BASE | (1 << 12) | (1 << 13))
        self._write(0x18, FIFO_BASE)
        self._write(0x24, 0x3FFFF)
        self._write(0x58, 6 << 11)
        self._write(0x5C, (1 << 11) | (1 << 8) | len(packet))
        self._write(0x60, 2 << 11)
        self._write(0x64, 4 << 11)
        for byte in packet:
            self._write(0x1C, byte)
        self._write(4, CTR_BASE | (1 << 11))
        self._write(4, CTR_BASE | (1 << 5))
        deadline = time.monotonic() + 0.5
        while True:
            raw = self._read(0x20)
            if raw & (NACK | TIMEOUT | ARBITRATION | COMPLETE):
                break
            if time.monotonic() >= deadline:
                raise TimeoutError('OLED I2C transfer stalled')
        done = all(self._read(offset) & (1 << 31) for offset in (0x58, 0x5C, 0x60))
        if raw & (NACK | TIMEOUT | ARBITRATION) or not raw & COMPLETE or not done:
            raise RuntimeError(f'OLED transfer not acknowledged (status 0x{raw:X})')

    def commands(self, commands):
        self.send(0, commands)

    def show(self, image):
        if image.mode != '1' or image.size != (128, 64):
            raise ValueError('Expected 128x64 monochrome image')
        for page in range(8):
            self.commands([0xB0 | page, 2, 0x10])
            row = bytes(sum(1 << bit for bit in range(8)
                            if image.getpixel((x, page * 8 + bit))) for x in range(128))
            for start in range(0, 128, 30):
                self.send(0x40, row[start:start + 30])
        self.commands([0xA4, 0xAF])

    def close(self):
        if self.esp is None:
            return
        try:
            if self.saved:
                self.esp.write_reg(GPIO + 0x28, BOTH)
                self._reset_controller()
                for reg in (IN_SCL, IN_SDA):
                    self.esp.write_reg(reg, self.saved[reg])
                for regs in PINS.values():
                    for reg in regs:
                        self.esp.write_reg(reg, self.saved[reg])
                self.esp.write_reg(GPIO + 4, self.saved[GPIO + 4], mask=BOTH)
                self.esp.write_reg(GPIO + 0x20, self.saved[GPIO + 0x20], mask=BOTH)
                self.esp.write_reg(SYS_RST, self.saved[SYS_RST], mask=PERIPH_BIT)
                self.esp.write_reg(SYS_CLK, self.saved[SYS_CLK], mask=PERIPH_BIT)
        finally:
            with contextlib.suppress(Exception):
                self.esp.hard_reset()
            self.esp._port.close()
            self.esp = None

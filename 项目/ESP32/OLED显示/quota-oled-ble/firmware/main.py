"""Power-on OLED display and optional BLE receiver for the verified board."""
import bluetooth
import framebuf
import machine
import struct
import time
import binascii
from micropython import const

# Rendering happens on the PC; 80 MHz is sufficient for BLE and OLED transfers.
machine.freq(80000000)

SERVICE = bluetooth.UUID('df8792b0-13e4-4d02-a91c-b2d1fc879b45')
RX = bluetooth.UUID('df8792b1-13e4-4d02-a91c-b2d1fc879b45')
INFO = bluetooth.UUID('df8792b2-13e4-4d02-a91c-b2d1fc879b45')
ACK = bluetooth.UUID('df8792b3-13e4-4d02-a91c-b2d1fc879b45')
NAME = 'CodexOLED-DD48'
EXPECTED_ID = '28848560dd48'
_CONNECT = const(1)
_DISCONNECT = const(2)
_WRITE = const(3)


class Oled:
    def __init__(self):
        self.i2c = machine.I2C(0, sda=machine.Pin(7), scl=machine.Pin(8), freq=100000)
        if 0x3c not in self.i2c.scan():
            raise OSError('OLED 0x3C not found')
        self.command(bytes((0xAE, 0xD5, 0x80, 0xA8, 0x3F, 0xD3, 0, 0x40,
                            0x8D, 0x14, 0x20, 2, 0xA1, 0xC8, 0xDA, 0x12,
                            0x81, 0x7F, 0xD9, 0xF1, 0xDB, 0x40, 0xA4, 0xA6, 0x2E)))

    def command(self, data):
        self.i2c.writeto(0x3c, b'\x00' + data)

    def show(self, data):
        if len(data) != 1024:
            raise ValueError('Frame must be 1024 bytes')
        for page in range(8):
            self.command(bytes((0xb0 | page, 2, 0x10)))
            self.i2c.writeto(0x3c, b'\x40' + data[page * 128:(page + 1) * 128])
        self.command(b'\xa4\xaf')


def power_on_display():
    # Show the waiting frame before enabling a radio or relying on a PC program.
    try:
        with open('boot_frame.bin', 'rb') as source:
            waiting = source.read()
        if len(waiting) != 1024:
            raise ValueError('Invalid boot framebuffer')
    except (OSError, ValueError):
        waiting = bytearray(1024)
        fb = framebuf.FrameBuffer(waiting, 128, 64, framebuf.MONO_VLSB)
        fb.text('Codex OLED', 8, 8, 1)
        fb.text('Waiting for PC', 8, 28, 1)
        fb.text('USB mode', 8, 48, 1)
    # The OLED power rail can settle slightly later than the ESP32 at plug-in.
    for attempt in range(15):
        try:
            display = Oled()
            display.show(waiting)
            print('OLED startup ready: 128x64 col2')
            return display
        except OSError as exc:
            if attempt == 14:
                print('OLED startup failed:', exc)
            time.sleep_ms(200)
    return None


class Receiver:
    def __init__(self, display=None):
        if binascii.hexlify(machine.unique_id()).decode() != EXPECTED_ID:
            raise RuntimeError('Unexpected board identity')
        self.display = display
        self.last_frame = None
        self.last_update = time.ticks_ms()
        self.marked_old = False
        self.frame_id = 0
        self.expected_crc = 0
        self.received = 0
        self.incoming = bytearray(1024)
        self.frames = 0
        self.queue = []
        self.connections = set()
        self.ble = bluetooth.BLE()
        print('Starting BLE at', machine.freq(), 'Hz')
        self.ble.active(True)
        self.ble.config(gap_name=NAME, rxbuf=4096, mtu=247)
        ((self.rx, self.info, self.ack),) = self.ble.gatts_register_services((
            (SERVICE, ((RX, bluetooth.FLAG_WRITE),
                       (INFO, bluetooth.FLAG_READ),
                       (ACK, bluetooth.FLAG_READ | bluetooth.FLAG_NOTIFY))),))
        self.ble.gatts_set_buffer(self.rx, 256)
        self.ble.gatts_set_buffer(self.info, 64)
        self.ble.gatts_write(self.info, ('CQ1|' + EXPECTED_ID + '|128x64|col2').encode())
        self.status(0)
        self.ble.irq(self.irq)
        self.advertise()
        try:
            if self.display is None:
                self.display = Oled()
            waiting = bytearray(1024)
            fb = framebuf.FrameBuffer(waiting, 128, 64, framebuf.MONO_VLSB)
            fb.text('Codex BLE', 8, 8, 1)
            fb.text('Waiting for PC', 8, 28, 1)
            fb.text('GPIO7 / GPIO8', 8, 48, 1)
            self.display.show(waiting)
        except Exception as exc:
            print('OLED init:', exc)
        print('BLE ready:', NAME, binascii.hexlify(self.ble.config('mac')[1]).decode())

    def advertise(self):
        self.ble.gap_advertise(200000,
            adv_data=b'\x02\x01\x06' + b'\x11\x07' + bytes(SERVICE),
            resp_data=bytes((len(NAME) + 1, 9)) + NAME.encode())

    def irq(self, event, data):
        if event == _CONNECT:
            self.connections.add(data[0])
            self.queue = []
            self.received = 0
        elif event == _DISCONNECT:
            self.connections.discard(data[0])
            self.queue = []
            self.received = 0
            self.advertise()
        elif event == _WRITE and data[1] == self.rx:
            packet = self.ble.gatts_read(self.rx)
            if len(self.queue) < 64:
                self.queue.append(packet)
            else:
                self.queue = []
                self.received = 0
                self.status(2)

    def status(self, code, checksum=0):
        packet = struct.pack('<2sBIII', b'QA', code, self.frame_id, checksum, self.frames)
        self.ble.gatts_write(self.ack, packet)
        for connection in self.connections:
            try:
                self.ble.gatts_notify(connection, self.ack, packet)
            except OSError:
                pass

    def accept(self, packet):
        if len(packet) < 7 or packet[:2] != b'QF':
            self.status(2)
            return
        op = packet[2]
        frame_id = struct.unpack_from('<I', packet, 3)[0]
        if op == 1 and len(packet) == 11:
            self.frame_id = frame_id
            self.expected_crc = struct.unpack_from('<I', packet, 7)[0]
            self.received = 0
            self.status(0)
        elif op == 2 and frame_id == self.frame_id and len(packet) > 9:
            offset = struct.unpack_from('<H', packet, 7)[0]
            data = packet[9:]
            if offset != self.received or offset + len(data) > 1024:
                self.status(2)
                return
            self.incoming[offset:offset + len(data)] = data
            self.received += len(data)
        elif op == 3 and frame_id == self.frame_id and len(packet) == 7:
            if self.received != 1024:
                self.status(2)
                return
            checksum = binascii.crc32(self.incoming) & 0xffffffff
            if checksum != self.expected_crc:
                self.status(4)
                return
            try:
                if self.display is None:
                    self.display = Oled()
                self.display.show(self.incoming)
                self.last_frame = bytes(self.incoming)
                self.last_update = time.ticks_ms()
                self.marked_old = False
                self.frames += 1
                self.status(1, checksum)
            except Exception as exc:
                print('OLED transfer:', exc)
                self.display = None
                self.status(3)
        else:
            self.status(2)

    def poll(self):
        while self.queue:
            self.accept(self.queue.pop(0))
        if (self.last_frame is not None and not self.marked_old and
                time.ticks_diff(time.ticks_ms(), self.last_update) > 150000):
            try:
                old = bytearray(self.last_frame)
                fb = framebuf.FrameBuffer(old, 128, 64, framebuf.MONO_VLSB)
                fb.text('OLD', 100, 20, 1)
                fb.text('OLD', 100, 54, 1)
                if self.display is None:
                    self.display = Oled()
                self.display.show(old)
                self.marked_old = True
            except OSError:
                self.display = None


if binascii.hexlify(machine.unique_id()).decode() != EXPECTED_ID:
    raise RuntimeError('Unexpected board identity')
try:
    with open('startup_mode.txt') as settings:
        startup_mode = settings.read().strip()
except OSError:
    startup_mode = 'usb'

display = power_on_display()
if startup_mode == 'ble':
    receiver = Receiver(display)
    while True:
        receiver.poll()
        time.sleep_ms(10)
else:
    # The USB ROM monitor takes over on connection. Standalone power stays lit.
    print('OLED USB standby ready')
    while True:
        time.sleep_ms(1000)
        if display is None:
            display = power_on_display()

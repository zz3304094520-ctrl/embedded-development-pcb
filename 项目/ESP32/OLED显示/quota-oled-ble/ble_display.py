"""Send a full frame over BLE and require an OLED completion acknowledgment."""
import asyncio
import secrets
import struct
import time
import zlib
from bleak import BleakClient, BleakScanner

SERVICE = 'df8792b0-13e4-4d02-a91c-b2d1fc879b45'
RX = 'df8792b1-13e4-4d02-a91c-b2d1fc879b45'
INFO = 'df8792b2-13e4-4d02-a91c-b2d1fc879b45'
ACK = 'df8792b3-13e4-4d02-a91c-b2d1fc879b45'
NAME = 'CodexOLED-DD48'
EXPECTED_INFO = b'CQ1|28848560dd48|128x64|col2'


def pack_frame(image):
    if image.mode != '1' or image.size != (128, 64):
        raise ValueError('Expected 128x64 monochrome image')
    return bytes(sum(1 << bit for bit in range(8)
                     if image.getpixel((x, page * 8 + bit)))
                 for page in range(8) for x in range(128))


class BleDisplay:
    def __init__(self):
        self.client = None
        self.address = None
        self.last_ack = None
        self.ack_event = asyncio.Event()

    async def connect(self):
        device = await BleakScanner.find_device_by_filter(
            lambda d, a: (a.local_name == NAME and
                          SERVICE in [uuid.lower() for uuid in a.service_uuids]),
            timeout=12)
        if device is None:
            raise RuntimeError('CodexOLED-DD48 Bluetooth device not found')
        client = BleakClient(device, timeout=20, winrt={'use_cached_services': False})
        self.client = client
        try:
            await client.connect()
            if bytes(await client.read_gatt_char(INFO, use_cached=False)) != EXPECTED_INFO:
                raise RuntimeError('Unexpected OLED identity; frame send refused')
            self.address = device.address
            await client.start_notify(ACK, self._notify)
        except BaseException:
            await self.close()
            raise

    def _notify(self, characteristic, data):
        if len(data) == 15 and data[:2] == b'QA':
            self.last_ack = struct.unpack('<2sBIII', data)
            self.ack_event.set()

    async def show(self, image):
        if self.client is None or not self.client.is_connected:
            await self.close()
            await self.connect()
        frame = pack_frame(image)
        checksum = zlib.crc32(frame) & 0xffffffff
        frame_id = secrets.randbits(32)
        self.last_ack = None
        self.ack_event.clear()
        await self.client.write_gatt_char(RX, struct.pack('<2sBII', b'QF', 1, frame_id, checksum), response=True)
        # Conservative ATT sizing also works when the peer keeps the 23-byte MTU.
        chunk_size = max(1, min(180, self.client.mtu_size - 3) - 9)
        for offset in range(0, len(frame), chunk_size):
            packet = struct.pack('<2sBIH', b'QF', 2, frame_id, offset) + frame[offset:offset + chunk_size]
            await self.client.write_gatt_char(RX, packet, response=True)
        await self.client.write_gatt_char(RX, struct.pack('<2sBI', b'QF', 3, frame_id), response=True)
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            ack = self.last_ack
            if ack and ack[2] == frame_id:
                if ack[1] == 1 and ack[3] == checksum:
                    return {'frame_id': frame_id, 'crc32': checksum,
                            'device_frames': ack[4], 'address': self.address,
                            'mtu': self.client.mtu_size}
                if ack[1] not in (0, 1):
                    raise RuntimeError(f'OLED rejected BLE frame (code {ack[1]})')
            self.ack_event.clear()
            try:
                await asyncio.wait_for(self.ack_event.wait(), timeout=0.5)
            except asyncio.TimeoutError:
                self._notify(None, await self.client.read_gatt_char(ACK, use_cached=False))
        raise TimeoutError('BLE frame was not confirmed by the OLED')

    async def close(self):
        client, self.client = self.client, None
        if client is not None:
            await client.disconnect()

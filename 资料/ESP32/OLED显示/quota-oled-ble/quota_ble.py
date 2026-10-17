"""Read local Codex quotas every minute and update the OLED over BLE."""
import argparse
import asyncio
import contextlib
import json
import logging
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DEPENDENCIES = ROOT / 'work/ble-runtime'
if DEPENDENCIES.is_dir():
    sys.path.insert(0, str(DEPENDENCIES))
from PIL import Image
from ble_display import BleDisplay
from codex_usage import UsageClient, summarize
from display_layout import EXPECTED_ACCOUNT, render, save_json


def placeholder():
    return {'fetched_at': int(time.time()), 'ordinary_usage_allowed': None,
            'five_hour': {'remaining_percent': None, 'resets_at': None},
            'weekly': {'remaining_percent': None, 'resets_at': None}}


async def run(args, runtime):
    stop = runtime / 'stop'
    with contextlib.suppress(FileNotFoundError):
        stop.unlink()
    display, reader = BleDisplay(), None
    snapshot = placeholder()
    stale, quota_error, ble_error = True, None, None
    next_read, next_send = 0, 0
    needs_send = True
    cycles, reads = 0, 0
    last_update, ack = None, None
    state = {}
    try:
        while not stop.exists():
            now = time.monotonic()
            if now >= next_read:
                try:
                    if reader is None:
                        reader = await asyncio.to_thread(UsageClient)
                    snapshot = summarize(await asyncio.to_thread(reader.read), EXPECTED_ACCOUNT)
                    save_json(runtime / 'usage.json', snapshot)
                    stale, quota_error = False, None
                except Exception as exc:
                    stale, quota_error = True, str(exc)
                    logging.warning('Quota read failed: %s', type(exc).__name__)
                    if reader is not None:
                        with contextlib.suppress(Exception):
                            await asyncio.to_thread(reader.close)
                        reader = None
                reads += 1
                frame = render(snapshot, stale)
                frame.save(runtime / 'preview.png')
                frame.resize((640, 320), Image.Resampling.NEAREST).save(runtime / 'preview_large.png')
                next_read = time.monotonic() + args.interval
                needs_send, next_send = True, 0
            connected = bool(display.client and display.client.is_connected)
            if (needs_send or not connected) and time.monotonic() >= next_send:
                try:
                    ack = await display.show(frame)
                    cycles += 1
                    last_update = int(time.time())
                    ble_error, needs_send, connected = None, False, True
                    logging.info('Frame %s: BLE=%s OLED ACK=%s fresh=%s',
                                 cycles, display.address, ack['device_frames'], not stale)
                except Exception as exc:
                    ble_error, connected = str(exc), False
                    logging.warning('BLE send failed: %s: %s', type(exc).__name__, exc)
                    with contextlib.suppress(Exception):
                        await display.close()
                    next_send = time.monotonic() + 10
                state = {'pid': os.getpid(), 'running': True, 'transport': 'BLE',
                         'cycle': cycles, 'quota_reads': reads, 'data_stale': stale,
                         'last_display_update': last_update, 'ble_connected': connected,
                         'oled_confirmed': connected and ack is not None,
                         'device_name': 'CodexOLED-DD48', 'address': display.address,
                         'last_ack': ack, 'interval_seconds': args.interval,
                         'error': ble_error or quota_error}
                save_json(runtime / 'status.json', state)
                if args.once:
                    print(json.dumps(state, ensure_ascii=False))
                    return 0 if connected and not stale else 1
            await asyncio.sleep(0.5)
    finally:
        with contextlib.suppress(Exception):
            await display.close()
        if reader is not None:
            with contextlib.suppress(Exception):
                await asyncio.to_thread(reader.close)
        state.update(pid=os.getpid(), running=False, ble_connected=False)
        save_json(runtime / 'status.json', state)
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--interval', type=int, default=60)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    if args.interval < 30:
        parser.error('Quota refresh interval must be at least 30 seconds')
    runtime = HERE / 'runtime'
    runtime.mkdir(exist_ok=True)
    logging.basicConfig(filename=runtime / 'monitor.log', level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(message)s', encoding='utf-8')
    with (runtime / 'monitor.lock').open('a+b') as lock:
        if os.name == 'nt':
            import msvcrt
            lock.seek(0)
            if not lock.read(1):
                lock.write(b'0')
                lock.flush()
            lock.seek(0)
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RuntimeError('Bluetooth monitor is already running') from exc
        return asyncio.run(run(args, runtime))


if __name__ == '__main__':
    raise SystemExit(main())

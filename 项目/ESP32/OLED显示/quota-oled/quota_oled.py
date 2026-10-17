"""Automatically show the signed-in Codex account's quotas on this OLED."""
import argparse
import contextlib
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from codex_usage import UsageClient, summarize

HERE = Path(__file__).resolve().parent
# Use the already-tested, locally installed esptool runtime when necessary.
import sys
LOCAL_RUNTIME = HERE.parent.parent / 'work/esptool-runtime'
if LOCAL_RUNTIME.is_dir():
    sys.path.insert(0, str(LOCAL_RUNTIME))
from oled_rom import RomOled

BJT = timezone(timedelta(hours=8))
EXPECTED_ACCOUNT = '1a6ded72-6b5f-4ab5-b264-af415064757f'

# Single-pixel strokes keep the dense horizontal lines in 置 separated.
RESET_ZHI = (
    '0111111111110',
    '0100100010010',
    '0111111111110',
    '0000001000000',
    '0111111111110',
    '0000001000000',
    '0011111111100',
    '0010000000100',
    '0011111111100',
    '0010000000100',
    '0011111111100',
    '0010000000100',
    '1111111111111',
)


def font(size):
    candidates = [Path(os.environ.get('WINDIR', r'C:\Windows')) / 'Fonts/msyh.ttc',
                  Path(os.environ.get('WINDIR', r'C:\Windows')) / 'Fonts/simhei.ttf']
    for path in candidates:
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    raise RuntimeError('A Chinese Windows font (Microsoft YaHei or SimHei) is required')


def percent(value):
    return '--' if value is None else f'{value:g}%'


def reset_text(value):
    if value is None:
        return '--'
    return datetime.fromtimestamp(value, BJT).strftime('%m-%d %H:%M')


def reset_label_font():
    path = Path(os.environ.get('WINDIR', r'C:\Windows')) / 'Fonts/simsun.ttc'
    return ImageFont.truetype(str(path), 13) if path.is_file() else font(13)


def render(snapshot, stale=False):
    image = Image.new('1', (128, 64), 0)
    draw = ImageDraw.Draw(image)
    body, detail, reset_face = font(15), font(10), reset_label_font()

    def write(x, y, text, face):
        bounds = draw.textbbox((x, y), text, font=face, anchor='lt')
        if bounds[0] < 0 or bounds[2] > 128 or bounds[3] > 64:
            raise RuntimeError(f'Display text does not fit: {text}')
        draw.text((x, y), text, font=face, fill=1, anchor='lt')
        return bounds

    # Four rows leave room around each quota, with percentages aligned right.
    for label, key, body_y, detail_y in [
        ('5小时', 'five_hour', 1, 18),
        ('周额度', 'weekly', 34, 51),
    ]:
        window = snapshot[key]
        value = percent(window['remaining_percent'])
        value_width = draw.textbbox((0, 0), value, font=body, anchor='lt')[2]
        label_bounds = write(4, body_y, label, body)
        value_x = 124 - value_width
        if value_x < label_bounds[2] + 4:
            raise RuntimeError('Quota label and percentage overlap')
        write(value_x, body_y, value, body)
        status = ' 旧' if stale else (' 暂停' if snapshot.get('ordinary_usage_allowed') is False else '')
        # Render 置 directly rather than squeezing its strokes into a TTF glyph.
        bounds = draw.textbbox((0, 0), '重', font=reset_face, anchor='lt')
        zhong_y = detail_y + max(0, len(RESET_ZHI) - (bounds[3] - bounds[1]))
        bounds = write(4, zhong_y, '重', reset_face)
        cursor = bounds[2] + 2
        glyph_width = len(RESET_ZHI[0])
        if cursor + glyph_width > 128 or detail_y + len(RESET_ZHI) > 64:
            raise RuntimeError('Reset glyph does not fit')
        for row, pixels in enumerate(RESET_ZHI):
            for column, pixel in enumerate(pixels):
                if pixel == '1':
                    draw.point((cursor + column, detail_y + row), fill=1)
        label_height = max(len(RESET_ZHI), bounds[3] - detail_y)
        cursor += glyph_width + 2
        text = reset_text(window['resets_at']) + status
        bounds = draw.textbbox((0, 0), text, font=detail, anchor='lt')
        detail_height = bounds[3] - bounds[1]
        date_y = detail_y + max(0, (label_height - detail_height) // 2)
        write(cursor + 2, date_y, text, detail)
    return image


def save_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', default='COM12')
    parser.add_argument('--interval', type=int, default=60)
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--preview-only', action='store_true')
    parser.add_argument('--baud', type=int, default=460800)
    args = parser.parse_args()
    if args.interval < 30:
        parser.error('Refresh interval must be at least 30 seconds')
    runtime = HERE / 'runtime'
    runtime.mkdir(exist_ok=True)
    logging.basicConfig(filename=runtime / 'monitor.log', level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(message)s', encoding='utf-8')
    lock = (runtime / 'monitor.lock').open('a+b')
    if os.name == 'nt':
        import msvcrt
        lock.seek(0)
        if not lock.read(1):
            lock.write(b'0')
            lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            lock.close()
            raise RuntimeError('The OLED quota monitor is already running')
    stop_file = runtime / 'stop'
    with contextlib.suppress(FileNotFoundError):
        stop_file.unlink()
    client = None
    display = None
    snapshot = None
    cycle = 0
    try:
        while not stop_file.exists():
            start = time.monotonic()
            stale = False
            error = None
            try:
                if client is None:
                    client = UsageClient()
                snapshot = summarize(client.read(), EXPECTED_ACCOUNT)
                save_json(runtime / 'usage.json', snapshot)
            except Exception as exc:
                # Keep old values explicitly marked as stale; never invent a reset.
                stale, error = True, str(exc)
                logging.warning('Quota read failed: %s', type(exc).__name__)
                if client is not None:
                    with contextlib.suppress(Exception):
                        client.close()
                    client = None
                if snapshot is None:
                    snapshot = {'fetched_at': int(time.time()),
                                'ordinary_usage_allowed': None,
                                'five_hour': {'remaining_percent': None, 'resets_at': None},
                                'weekly': {'remaining_percent': None, 'resets_at': None}}
            frame = render(snapshot, stale)
            frame.save(runtime / 'preview.png')
            frame.resize((640, 320), Image.Resampling.NEAREST).save(runtime / 'preview_large.png')
            connected = False
            if not args.preview_only:
                try:
                    if display is None:
                        display = RomOled(args.port, args.baud)
                    display.show(frame)
                    connected = True
                except Exception as exc:
                    error = str(exc)
                    logging.warning('OLED update failed: %s', type(exc).__name__)
                    if display is not None:
                        with contextlib.suppress(Exception):
                            display.close()
                        display = None
            cycle += 1
            state = {'pid': os.getpid(), 'running': True, 'cycle': cycle,
                     'last_display_update': int(time.time()) if connected else None,
                     'oled_connected': connected, 'data_stale': stale,
                     'interval_seconds': args.interval,
                     'port': display.port if display else None,
                     'error': error, 'flash_written': False}
            save_json(runtime / 'status.json', state)
            logging.info('Cycle %s: OLED=%s fresh=%s', cycle, connected, not stale)
            if args.once or args.preview_only:
                print(json.dumps({'snapshot': snapshot, 'status': state}, ensure_ascii=False))
                return 0 if (args.preview_only or connected) and not stale else 1
            delay = max(0, args.interval - (time.monotonic() - start))
            deadline = time.monotonic() + delay
            while not stop_file.exists() and time.monotonic() < deadline:
                time.sleep(min(0.5, max(0, deadline - time.monotonic())))
    finally:
        if display is not None:
            with contextlib.suppress(Exception):
                display.close()
        if client is not None:
            with contextlib.suppress(Exception):
                client.close()
        save_json(runtime / 'status.json', {'pid': os.getpid(), 'running': False,
                                          'cycle': cycle, 'flash_written': False})
        lock.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

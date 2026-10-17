"""Preserved four-row layout from the working USB display."""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
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


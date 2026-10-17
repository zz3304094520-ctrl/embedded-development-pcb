"""Backup, install and restore only the previously verified ESP32-S3."""
import argparse
import hashlib
import json
import struct
import sys
import time
import types
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / 'work/esptool-runtime'))
sys.path.insert(0, str(HERE.parent / 'quota-oled'))
from esptool.cmds import detect_chip, read_flash, erase_flash, write_flash
from esptool.loader import StubFlasher
from oled_rom import choose_port, EXPECTED_MAC

SIZE = 16 * 1024 * 1024
BACKUP = HERE / 'backups'


def paced_read_flash(esp, address, length, progress_fn=None):
    # The official READ_FLASH protocol permits an explicit in-flight limit.
    # One packet per acknowledgment prevents this USB UART dropping burst data.
    esp.check_command('read flash', esp.ESP_CMDS['READ_FLASH'],
                      struct.pack('<IIII', address, length, esp.FLASH_SECTOR_SIZE, 1))
    chunks, count = [], 0
    esp._port.timeout = 10
    while count < length:
        packet = esp.read()
        if len(packet) != min(esp.FLASH_SECTOR_SIZE, length - count):
            raise RuntimeError(f'Unexpected flash packet length {len(packet)} at {address + count:#x}')
        chunks.append(packet)
        count += len(packet)
        esp.write(struct.pack('<I', count))
        if progress_fn:
            progress_fn(count, length, address)
    data = b''.join(chunks)
    digest = esp.read()
    if len(digest) != 16 or digest.hex() != hashlib.md5(data).hexdigest():
        raise RuntimeError('Flash read digest mismatch')
    return data


def connect(port, baud):
    StubFlasher.set_stub_subdir('1')
    esp = detect_chip(port=choose_port(port), baud=115200, connect_attempts=3)
    try:
        mac = ':'.join(f'{b:02x}' for b in esp.read_mac())
        if esp.CHIP_NAME != 'ESP32-S3' or mac != EXPECTED_MAC:
            raise RuntimeError('Unexpected chip or MAC; flash operation refused')
        if esp.get_secure_boot_enabled() or esp.get_flash_encryption_enabled():
            raise RuntimeError('Secure boot/encrypted flash: operation refused')
        esp = esp.run_stub()
        esp.change_baud(baud)
        if ':'.join(f'{b:02x}' for b in esp.read_mac()) != EXPECTED_MAC:
            raise RuntimeError('Serial speed verification failed')
        esp._port.set_buffer_size(rx_size=1024 * 1024, tx_size=65536)
        esp.read_flash = types.MethodType(paced_read_flash, esp)
        esp.FLASH_WRITE_SIZE = 4096
        return esp
    except BaseException:
        esp._port.close()
        raise


def checked_backup():
    manifest = json.loads((BACKUP / 'manifest.json').read_text(encoding='utf-8'))
    path = BACKUP / manifest['flash_file']
    if (manifest['mac'] != EXPECTED_MAC or path.stat().st_size != SIZE or
            hashlib.sha256(path.read_bytes()).hexdigest() != manifest['flash_sha256'] or
            not manifest['flash_verified']):
        raise RuntimeError('Original full flash backup failed validation')
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['backup', 'install', 'restore'])
    parser.add_argument('--port', default='COM12')
    parser.add_argument('--baud', type=int, default=115200)
    parser.add_argument('--image', type=Path)
    args = parser.parse_args()
    BACKUP.mkdir(exist_ok=True)
    if args.action == 'backup' and (BACKUP / 'manifest.json').exists():
        checked_backup()
        print('Verified original backup already exists; keeping it')
        return
    if args.action != 'backup':
        original = checked_backup()
    if args.action == 'install' and (not args.image or not args.image.is_file()):
        raise RuntimeError('Official firmware file is required')
    esp = connect(args.port, args.baud)
    try:
        if args.action == 'backup':
            original = BACKUP / 'original_esp32s3_16MB.bin'
            partial = original.with_suffix('.partial')
            md5, sha = hashlib.md5(), hashlib.sha256()
            offset = 0
            if partial.exists():
                prior = partial.read_bytes()
                if len(prior) % (1024 * 1024) or len(prior) > SIZE:
                    raise RuntimeError('Partial backup has invalid length')
                for block_start in range(0, len(prior), 1024 * 1024):
                    block = prior[block_start:block_start + 1024 * 1024]
                    if esp.flash_md5sum(block_start, len(block)) != hashlib.md5(block).hexdigest():
                        raise RuntimeError('Partial backup no longer matches this board')
                md5.update(prior)
                sha.update(prior)
                offset = len(prior)
                print(f'Verified {offset // (1024 * 1024)} MiB already backed up', flush=True)
            with partial.open('ab') as out:
                for offset in range(offset, SIZE, 1024 * 1024):
                    blank = b'\xff' * (1024 * 1024)
                    expected_digest = esp.flash_md5sum(offset, len(blank))
                    if expected_digest == hashlib.md5(blank).hexdigest():
                        # Exact device digest identifies an entirely erased block;
                        # the final per-block device checks also verify this copy.
                        data = blank
                        print('Verified erased flash block', flush=True)
                    else:
                        data = read_flash(esp, offset, 1024 * 1024, no_progress=True)
                        if hashlib.md5(data).hexdigest() != expected_digest:
                            raise RuntimeError('Flash block digest mismatch')
                    if len(data) != 1024 * 1024:
                        raise RuntimeError('Incomplete flash read')
                    out.write(data)
                    md5.update(data)
                    sha.update(data)
                    print(f'BACKUP {offset // (1024 * 1024) + 1}/16 MiB', flush=True)
            # Check every address in bounded blocks; very long digest commands
            # can trigger the RAM stub watchdog on this board.
            all_data = partial.read_bytes()
            for block_start in range(0, SIZE, 1024 * 1024):
                block = all_data[block_start:block_start + 1024 * 1024]
                if esp.flash_md5sum(block_start, len(block)) != hashlib.md5(block).hexdigest():
                    raise RuntimeError('Backup digest differs from ESP32 flash')
            partial.replace(original)
            source = HERE.parent / 'quota-oled'
            archive = BACKUP / 'usb_version.zip'
            with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as out:
                for file in source.iterdir():
                    if file.is_file():
                        out.write(file, 'quota-oled/' + file.name)
            manifest = {'created_at': int(time.time()), 'chip': esp.CHIP_NAME,
                        'mac': EXPECTED_MAC, 'flash_size': SIZE,
                        'flash_file': original.name, 'flash_sha256': sha.hexdigest(),
                        'flash_md5': md5.hexdigest(), 'flash_verified': True,
                        'verification': 'All 16 MiB verified against device in 1 MiB MD5 blocks',
                        'usb_archive': archive.name,
                        'usb_archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest()}
            (BACKUP / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
            print('BACKUP VERIFIED; USB source archived', flush=True)
        else:
            image = args.image if args.action == 'install' else original
            # All prior flash contents are recoverable from the verified full backup.
            erase_flash(esp)
            write_flash(esp, [(0, str(image))], flash_size='keep')
            data = image.read_bytes()
            for offset in range(0, len(data), 1024 * 1024):
                block = data[offset:offset + 1024 * 1024]
                if esp.flash_md5sum(offset, len(block)) != hashlib.md5(block).hexdigest():
                    raise RuntimeError('Written image digest verification failed')
            print(f'{args.action.upper()} VERIFIED', flush=True)
    finally:
        try:
            esp.hard_reset()
        finally:
            esp._port.close()


if __name__ == '__main__':
    main()

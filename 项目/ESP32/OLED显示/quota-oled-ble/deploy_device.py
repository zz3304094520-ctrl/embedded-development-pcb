"""Copy and verify the boot program over MicroPython's USB/UART REPL."""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / 'work/ble-runtime'))
from mpremote.transport_serial import SerialTransport


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', default='COM12')
    parser.add_argument('--mode', choices=('usb', 'ble'), default='usb')
    args = parser.parse_args()
    transport = SerialTransport(args.port, baudrate=115200, timeout=2)
    try:
        # This FTDI adapter must release both reset/control lines for the REPL.
        transport.serial.rts = False
        transport.serial.dtr = False
        # Interrupt boot promptly; the previous radio startup can reset the board.
        transport.serial.rts = True
        time.sleep(0.1)
        transport.serial.rts = False
        for _ in range(50):
            transport.serial.write(b'\x03')
            time.sleep(0.02)
        transport.enter_raw_repl(soft_reset=True)
        identity = transport.exec("import machine,binascii;print(binascii.hexlify(machine.unique_id()).decode())").decode().strip()
        if identity != '28848560dd48':
            raise RuntimeError('Unexpected MicroPython board; program copy refused')
        print(transport.exec("import os,gc,esp;print(os.uname());print('heap',gc.mem_free(),'flash',esp.flash_size())").decode())
        sources = {
            'boot_frame.bin': (HERE / 'firmware/boot_frame.bin').read_bytes(),
            'startup_mode.txt': (args.mode + '\n').encode(),
            'main.py': (HERE / 'firmware/main.py').read_bytes(),
        }
        if len(sources['boot_frame.bin']) != 1024:
            raise RuntimeError('Boot framebuffer must be 1024 bytes')
        # Preserve what is actually on this board before replacing boot files.
        backup = HERE / 'backups' / ('device-before-startup-' + str(time.time_ns()))
        backup.mkdir(parents=True)
        present = json.loads(transport.exec("import json;print(json.dumps(os.listdir()))").decode())
        for filename in sources:
            if filename in present:
                encoded = transport.exec('print(binascii.hexlify(open(' + repr(filename) + ",'rb').read()).decode())").decode().strip()
                (backup / filename).write_bytes(bytes.fromhex(encoded))
        digests = {}
        # Verify every staged file; install main.py last so boot stays recoverable.
        for filename, source in sources.items():
            staged = '.' + filename + '.new'
            transport.exec('f=open(' + repr(staged) + ",'wb')")
            for offset in range(0, len(source), 256):
                transport.exec('f.write(' + repr(source[offset:offset + 256]) + ')')
            transport.exec('f.close()')
            digest = transport.exec("import hashlib;print(binascii.hexlify(hashlib.sha256(open(" + repr(staged) + ",'rb').read()).digest()).decode())").decode().strip()
            if digest != hashlib.sha256(source).hexdigest():
                raise RuntimeError('Device checksum failed: ' + filename)
            digests[filename] = digest
            print('Device SHA256 verified:', filename, digest)
        for filename in sources:
            transport.exec('os.rename(' + repr('.' + filename + '.new') + ',' + repr(filename) + ')')
        transport.exit_raw_repl()
        transport.serial.write(b'\x04')
        # Capture startup errors without interrupting the running firmware.
        deadline = time.monotonic() + 6
        output = bytearray()
        while time.monotonic() < deadline:
            if transport.serial.in_waiting:
                output.extend(transport.serial.read(transport.serial.in_waiting))
            time.sleep(0.1)
        boot_log = output.decode('utf-8', errors='replace')
        print(boot_log)
        runtime = HERE / 'runtime'
        runtime.mkdir(exist_ok=True)
        (runtime / 'power_on_boot.log').write_text(boot_log, encoding='utf-8')
        expected = b'BLE ready:' if args.mode == 'ble' else b'OLED USB standby ready'
        ready = (b'OLED startup ready:' in output and expected in output and
                 b'Traceback' not in output and b'Brownout' not in output)
        (HERE / 'firmware/deployed.json').write_text(json.dumps({
            'port': args.port, 'device_id': identity,
            'main_sha256': digests['main.py'], 'files_sha256': digests,
            'startup_mode': args.mode, 'deployed_at': int(time.time()),
            'verified': True, 'boot_ready': ready,
            'previous_device_files': str(backup.relative_to(HERE)),
        }, indent=2), encoding='utf-8')
        if not ready:
            raise RuntimeError('Boot program did not report OLED and mode ready')
    finally:
        transport.close()


if __name__ == '__main__':
    main()

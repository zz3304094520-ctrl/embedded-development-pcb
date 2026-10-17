"""Read account limits through the documented local Codex app-server RPC."""
import json
import os
import queue
import shutil
import subprocess
import threading
import time
from pathlib import Path


def find_codex():
    direct = shutil.which('codex.exe')
    if direct:
        return direct
    npm = Path(os.environ.get('APPDATA', '')) / 'npm/node_modules/@openai/codex'
    for suffix in (
        'node_modules/@openai/codex-win32-x64/vendor/x86_64-pc-windows-msvc/bin/codex.exe',
        'node_modules/@openai/codex-win32-x64/vendor/x86_64-pc-windows-msvc/codex/codex.exe',
        'vendor/x86_64-pc-windows-msvc/codex/codex.exe',
    ):
        candidate = npm / suffix
        if candidate.is_file():
            return str(candidate)
    raise RuntimeError('Cannot locate the installed Codex executable')


class UsageClient:
    def __init__(self):
        self.process = subprocess.Popen(
            [find_codex(), 'app-server', '--listen', 'stdio://'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding='utf-8', bufsize=1,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        self.messages = queue.Queue()
        self.next_id = 0
        threading.Thread(target=self._reader, daemon=True).start()
        try:
            self.request('initialize', {
                'clientInfo': {'name': 'codex_quota_oled',
                               'title': 'Codex OLED Quota Display', 'version': '1.0.0'},
            })
            self._send({'method': 'initialized', 'params': {}})
        except BaseException:
            self.close()
            raise

    def _reader(self):
        try:
            for line in self.process.stdout:
                try:
                    self.messages.put(json.loads(line))
                except json.JSONDecodeError:
                    pass
        finally:
            self.messages.put(None)

    def _send(self, message):
        self.process.stdin.write(json.dumps(message) + '\n')
        self.process.stdin.flush()

    def request(self, method, params=None, timeout=30):
        assert method in ('initialize', 'account/rateLimits/read')
        self.next_id += 1
        request_id = self.next_id
        message = {'method': method, 'id': request_id}
        if params is not None:
            message['params'] = params
        self._send(message)
        deadline = time.monotonic() + timeout
        while True:
            wait = deadline - time.monotonic()
            if wait <= 0:
                raise TimeoutError('Codex quota read timed out')
            try:
                response = self.messages.get(timeout=wait)
            except queue.Empty as exc:
                raise TimeoutError('Codex quota read timed out') from exc
            if response is None:
                raise RuntimeError('Codex app-server exited')
            if response.get('id') != request_id or 'method' in response:
                continue
            if 'error' in response:
                error = response['error']
                raise RuntimeError(f"Codex RPC error {error.get('code')}: {error.get('message')}")
            return response['result']

    def read(self):
        return self.request('account/rateLimits/read')

    def close(self):
        if self.process.poll() is None:
            self.process.stdin.close()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try:
                    self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=3)


def summarize(raw, expected_account=None):
    account_id = raw.get('accountId')
    if expected_account and account_id and account_id != expected_account:
        raise RuntimeError('Codex CLI account differs from the desktop account')
    buckets = raw.get('rateLimitsByLimitId') or {}
    bucket = buckets.get('codex')
    if bucket is None:
        legacy = raw.get('rateLimits')
        if legacy and legacy.get('limitId') in (None, 'codex'):
            bucket = legacy
    if bucket is None:
        raise RuntimeError('Codex quota bucket is unavailable')
    windows = {}
    for key in ('primary', 'secondary'):
        window = bucket.get(key)
        if window:
            windows[window.get('windowDurationMins')] = window
    result = {'fetched_at': int(time.time()), 'source': 'codex',
              'ordinary_usage_allowed': raw.get('ordinaryUsageAllowed'),
              'account_verified': bool(expected_account and account_id == expected_account)}
    for label, duration in (('five_hour', 300), ('weekly', 10080)):
        window = windows.get(duration) or {}
        used = window.get('usedPercent')
        remaining = None if used is None else max(0, min(100, 100 - float(used)))
        result[label] = {'remaining_percent': remaining, 'resets_at': window.get('resetsAt')}
    return result


if __name__ == '__main__':
    client = UsageClient()
    try:
        print(json.dumps(summarize(client.read(), '1a6ded72-6b5f-4ab5-b264-af415064757f')))
    finally:
        client.close()

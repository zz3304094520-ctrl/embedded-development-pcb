$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'Stop.ps1')
$statusPath = Join-Path $PSScriptRoot 'runtime/status.json'
if (Test-Path -LiteralPath $statusPath) {
    $status = Get-Content -LiteralPath $statusPath -Raw | ConvertFrom-Json
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($status.pid)" -ErrorAction SilentlyContinue
    $script = Join-Path $PSScriptRoot 'quota_ble.py'
    if ($status.running -and $process -and $process.CommandLine -like ('*' + $script + '*')) {
        $stopDeadline = (Get-Date).AddSeconds(45)
        while (Get-Process -Id $status.pid -ErrorAction SilentlyContinue) {
            if ((Get-Date) -ge $stopDeadline) { throw 'Bluetooth monitor did not stop; USB start aborted.' }
            Start-Sleep -Milliseconds 500
        }
    }
}
& (Join-Path (Split-Path $PSScriptRoot -Parent) 'quota-oled/Start.ps1')

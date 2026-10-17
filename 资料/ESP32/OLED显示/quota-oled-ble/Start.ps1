param([ValidateRange(30,3600)][int]$Interval = 60)
$ErrorActionPreference = 'Stop'
$monitorScript = Join-Path $PSScriptRoot 'quota_ble.py'
$runtimeDirectory = Join-Path $PSScriptRoot 'runtime'
New-Item -ItemType Directory -Path $runtimeDirectory -Force | Out-Null
$statusPath = Join-Path $runtimeDirectory 'status.json'
if (Test-Path -LiteralPath $statusPath) {
    $previousStatus = Get-Content -LiteralPath $statusPath -Raw | ConvertFrom-Json
    if ($previousStatus.running) {
        $monitorProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $($previousStatus.pid)" -ErrorAction SilentlyContinue
        if ($monitorProcess -and $monitorProcess.CommandLine -like ('*' + $monitorScript + '*')) {
            Write-Output ('Bluetooth quota monitor already running, PID ' + $previousStatus.pid)
            exit 0
        }
    }
}
# Stop the USB ROM driver so the firmware can execute and advertise BLE.
$usbDirectory = Join-Path (Split-Path $PSScriptRoot -Parent) 'quota-oled'
$usbStatusPath = Join-Path $usbDirectory 'runtime/status.json'
if (Test-Path -LiteralPath $usbStatusPath) {
    $usbStatus = Get-Content -LiteralPath $usbStatusPath -Raw | ConvertFrom-Json
    $usbScript = Join-Path $usbDirectory 'quota_oled.py'
    $usbProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $($usbStatus.pid)" -ErrorAction SilentlyContinue
    if ($usbStatus.running -and $usbProcess -and $usbProcess.CommandLine -like ('*' + $usbScript + '*')) {
        & (Join-Path $usbDirectory 'Stop.ps1')
        $stopDeadline = (Get-Date).AddSeconds(45)
        while (Get-Process -Id $usbStatus.pid -ErrorAction SilentlyContinue) {
            if ((Get-Date) -ge $stopDeadline) { throw 'USB monitor did not stop; Bluetooth start aborted.' }
            Start-Sleep -Milliseconds 500
        }
    }
}
$pythonCommand = (Get-Command python.exe -ErrorAction Stop).Source
$monitorArguments = @('-u', ('"' + $monitorScript + '"'), '--interval', $Interval)
$backgroundProcess = Start-Process -FilePath $pythonCommand -ArgumentList $monitorArguments -WindowStyle Hidden -WorkingDirectory $PSScriptRoot -RedirectStandardOutput (Join-Path $runtimeDirectory 'console.log') -RedirectStandardError (Join-Path $runtimeDirectory 'errors.log') -PassThru
Write-Output ('Started Bluetooth quota monitor, PID ' + $backgroundProcess.Id)

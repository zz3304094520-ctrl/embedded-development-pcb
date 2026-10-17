param(
    [ValidatePattern('^COM[0-9]+$')][string]$Port = 'COM12',
    [ValidateRange(30,3600)][int]$Interval = 60
)
$ErrorActionPreference = 'Stop'
$monitorScript = Join-Path $PSScriptRoot 'quota_oled.py'
$runtimeDirectory = Join-Path $PSScriptRoot 'runtime'
New-Item -ItemType Directory -Path $runtimeDirectory -Force | Out-Null
$statusPath = Join-Path $runtimeDirectory 'status.json'
if (Test-Path -LiteralPath $statusPath) {
    $previousStatus = Get-Content -LiteralPath $statusPath -Raw | ConvertFrom-Json
    if ($previousStatus.running) {
        $monitorProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $($previousStatus.pid)" -ErrorAction SilentlyContinue
        if ($monitorProcess -and $monitorProcess.CommandLine -like ('*' + $monitorScript + '*')) {
            Write-Output ('OLED quota monitor already running, PID ' + $previousStatus.pid)
            exit 0
        }
    }
}
$pythonCommand = (Get-Command python.exe -ErrorAction Stop).Source
$monitorArguments = @('-u', ('"' + $monitorScript + '"'), '--port', $Port, '--interval', $Interval)
$backgroundProcess = Start-Process -FilePath $pythonCommand -ArgumentList $monitorArguments -WindowStyle Hidden -WorkingDirectory $PSScriptRoot -RedirectStandardOutput (Join-Path $runtimeDirectory 'console.log') -RedirectStandardError (Join-Path $runtimeDirectory 'errors.log') -PassThru
Write-Output ('Started OLED quota monitor, PID ' + $backgroundProcess.Id)

$ErrorActionPreference = 'Stop'
$runtimeDirectory = Join-Path $PSScriptRoot 'runtime'
New-Item -ItemType Directory -Path $runtimeDirectory -Force | Out-Null
Set-Content -LiteralPath (Join-Path $runtimeDirectory 'stop') -Value 'stop' -Encoding utf8
Write-Output 'Stop requested. The monitor will close the serial port and reset the ESP32 to its original firmware.'

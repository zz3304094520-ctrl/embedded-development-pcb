$ErrorActionPreference = 'Stop'
$runtimeDirectory = Join-Path $PSScriptRoot 'runtime'
New-Item -ItemType Directory -Path $runtimeDirectory -Force | Out-Null
Set-Content -LiteralPath (Join-Path $runtimeDirectory 'stop') -Value 'stop' -Encoding utf8
Write-Output 'Stop requested. Bluetooth connection will be released.'

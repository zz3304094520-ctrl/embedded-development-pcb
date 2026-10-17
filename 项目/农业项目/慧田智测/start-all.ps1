$ErrorActionPreference = 'Stop'

$projectRoot = $PSScriptRoot
$network = Get-Content -Raw -Encoding UTF8 (Join-Path $projectRoot 'network-config.json') | ConvertFrom-Json
$configuredServerIp = [string] $network.server_ip
$serverIp = $configuredServerIp
$apiPort = [int] $network.api_port
$h5Port = [int] $network.h5_port
$adminPort = [int] $network.admin_port
$logDirectory = Join-Path $projectRoot '.runtime-logs'
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null

$activeAddresses = @(
    Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object {
            $_.AddressState -eq 'Preferred' -and
            $_.IPAddress -ne '127.0.0.1' -and
            $_.IPAddress -notlike '169.254.*'
        }
)
if ($activeAddresses.IPAddress -notcontains $configuredServerIp) {
    $defaultNetwork = Get-NetIPConfiguration -ErrorAction SilentlyContinue |
        Where-Object { $_.IPv4DefaultGateway -and $_.IPv4Address } |
        Select-Object -First 1
    $detectedAddress = if ($defaultNetwork) {
        [string] (@($defaultNetwork.IPv4Address)[0].IPAddress)
    } else {
        [string] (@($activeAddresses)[0].IPAddress)
    }
    if ($detectedAddress) {
        $serverIp = $detectedAddress
        Write-Warning ("Configured server IP {0} is unavailable; using current IPv4 {1}." -f $configuredServerIp, $serverIp)
    } else {
        $serverIp = '127.0.0.1'
        Write-Warning ("Configured server IP {0} is unavailable; using localhost only." -f $configuredServerIp)
    }
}

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText(
    (Join-Path $projectRoot 'huitian-frontend\.env.local'),
    "VITE_API_BASE_URL=http://${serverIp}:$apiPort`nVITE_WS_URL=ws://${serverIp}:$apiPort/ws`n",
    $utf8NoBom
)
[System.IO.File]::WriteAllText(
    (Join-Path $projectRoot 'huitian-admin\.env.local'),
    "VITE_API_BASE_URL=http://${serverIp}:$apiPort`nVITE_H5_URL=http://${serverIp}:$h5Port`n",
    $utf8NoBom
)

function Start-ProjectService {
    param(
        [Parameter(Mandatory)] [string] $Name,
        [Parameter(Mandatory)] [int] $Port,
        [Parameter(Mandatory)] [string] $FilePath,
        [Parameter(Mandatory)] [string[]] $ArgumentList,
        [Parameter(Mandatory)] [string] $WorkingDirectory,
        [Parameter(Mandatory)] [string] $LogPrefix
    )

    $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    if ($listener) {
        Write-Host ("[RUNNING] {0}: http://{1}:{2}" -f $Name, $serverIp, $Port) -ForegroundColor Yellow
        return
    }

    Start-Process `
        -FilePath $FilePath `
        -ArgumentList $ArgumentList `
        -WorkingDirectory $WorkingDirectory `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $logDirectory "$LogPrefix.out.log") `
        -RedirectStandardError (Join-Path $logDirectory "$LogPrefix.err.log")

    Write-Host ("[STARTED] {0}: http://{1}:{2}" -f $Name, $serverIp, $Port) -ForegroundColor Green
}

$npmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
$bundledNode = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
$bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$venvPython = Join-Path $projectRoot 'huitian-backend\.venv\Scripts\python.exe'
$venvConfig = Join-Path $projectRoot 'huitian-backend\.venv\pyvenv.cfg'
$backendPython = $venvPython

if (Test-Path $venvConfig) {
    $venvHomeLine = Get-Content -Encoding UTF8 $venvConfig | Where-Object { $_ -like 'home = *' } | Select-Object -First 1
    $venvHome = if ($venvHomeLine) { $venvHomeLine.Substring(7).Trim() } else { '' }
    if ($venvHome -and -not (Test-Path (Join-Path $venvHome 'python.exe'))) {
        if (-not (Test-Path $bundledPython)) {
            throw 'The project virtual environment points to a missing Python installation and no bundled fallback was found.'
        }
        $backendPython = $bundledPython
        $env:PYTHONPATH = Join-Path $projectRoot 'huitian-backend\.venv\Lib\site-packages'
    }
}

if ($npmCommand) {
    $frontendRunner = $npmCommand.Source
    $frontendArguments = @('run', 'dev')
    $adminRunner = $npmCommand.Source
    $adminArguments = @('run', 'dev')
} else {
    if (-not (Test-Path $bundledNode)) {
        throw 'npm.cmd is unavailable and no bundled Node.js fallback was found.'
    }
    $frontendRunner = $bundledNode
    $frontendArguments = @('node_modules/vite/bin/vite.js', '--host', '0.0.0.0', '--port', [string] $h5Port, '--strictPort')
    $adminRunner = $bundledNode
    $adminArguments = @('node_modules/vite/bin/vite.js', '--host', '0.0.0.0', '--port', [string] $adminPort, '--strictPort')
}

Start-ProjectService `
    -Name 'FastAPI backend' `
    -Port $apiPort `
    -FilePath $backendPython `
    -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', [string] $apiPort) `
    -WorkingDirectory (Join-Path $projectRoot 'huitian-backend') `
    -LogPrefix 'backend'

Start-ProjectService `
    -Name 'H5 frontend' `
    -Port $h5Port `
    -FilePath $frontendRunner `
    -ArgumentList $frontendArguments `
    -WorkingDirectory (Join-Path $projectRoot 'huitian-frontend') `
    -LogPrefix 'frontend'

Start-ProjectService `
    -Name 'Admin frontend' `
    -Port $adminPort `
    -FilePath $adminRunner `
    -ArgumentList $adminArguments `
    -WorkingDirectory (Join-Path $projectRoot 'huitian-admin') `
    -LogPrefix 'admin'

$weatherPortCandidates = @(
    Get-PnpDevice -PresentOnly -Class Ports -ErrorAction SilentlyContinue |
        ForEach-Object {
            if ($_.FriendlyName -match 'CH340.*\((COM\d+)\)') {
                $Matches[1]
            }
        }
)

if ($weatherPortCandidates.Count -eq 1) {
    $weatherPort = $weatherPortCandidates[0]
    $sensorConfigPath = Join-Path $logDirectory 'sensor-gateway.windows.json'
    $sensorPidPath = Join-Path $logDirectory 'sensor-gateway.pid'
    $sensorConfig = [ordered]@{
        backend_url = "http://127.0.0.1:$apiPort"
        poll_interval_seconds = 5
        http_timeout_seconds = 3
        offline_after_failures = 2
        sensors = @(
            [ordered]@{
                name = 'Four-element ultrasonic weather station'
                device_code = 'weather-001'
                driver = 'renke_fsxcs'
                port = $weatherPort
                baudrate = 4800
                slave_address = 1
                timeout_seconds = 1.2
                enabled = $true
            },
            [ordered]@{
                name = 'Three-cup wind speed sensor'
                device_code = 'wind-speed-001'
                driver = 'wind_speed_fsjt_n01'
                port = $weatherPort
                baudrate = 4800
                slave_address = 2
                timeout_seconds = 1.2
                enabled = $true
            },
            [ordered]@{
                name = 'Eight-direction wind direction sensor'
                device_code = 'wind-direction-001'
                driver = 'wind_direction_fxjt_n01_8'
                port = $weatherPort
                baudrate = 4800
                slave_address = 3
                timeout_seconds = 1.2
                enabled = $true
            }
        )
    }
    [System.IO.File]::WriteAllText(
        $sensorConfigPath,
        ($sensorConfig | ConvertTo-Json -Depth 6),
        $utf8NoBom
    )

    $runningSensorProcess = $null
    if (Test-Path -LiteralPath $sensorPidPath) {
        $sensorPidText = (Get-Content -LiteralPath $sensorPidPath -Raw -ErrorAction SilentlyContinue).Trim()
        if ($sensorPidText -match '^\d+$') {
            $runningSensorProcess = Get-Process -Id ([int] $sensorPidText) -ErrorAction SilentlyContinue
        }
    }

    if ($runningSensorProcess) {
        Write-Host ("[RUNNING] Weather sensors: {0}, 4800bps, Modbus RTU, slaves 1/2/3" -f $weatherPort) -ForegroundColor Yellow
    } else {
        $pythonLauncher = Get-Command py.exe -ErrorAction SilentlyContinue
        $sensorArguments = @('-3', '-u', '-m', 'sensor_gateway', '--config', $sensorConfigPath)
        if (-not $pythonLauncher) {
            $pythonLauncher = Get-Command python.exe -ErrorAction SilentlyContinue
            $sensorArguments = @('-u', '-m', 'sensor_gateway', '--config', $sensorConfigPath)
        }
        if (-not $pythonLauncher) {
            throw 'Python launcher is unavailable; cannot start the weather sensor gateway.'
        }
        $sensorProcess = Start-Process `
            -FilePath $pythonLauncher.Source `
            -ArgumentList $sensorArguments `
            -WorkingDirectory (Join-Path $projectRoot 'jetson-edge') `
            -WindowStyle Hidden `
            -RedirectStandardOutput (Join-Path $logDirectory 'sensor-gateway.out.log') `
            -RedirectStandardError (Join-Path $logDirectory 'sensor-gateway.err.log') `
            -PassThru
        [System.IO.File]::WriteAllText($sensorPidPath, [string] $sensorProcess.Id, $utf8NoBom)
        Write-Host ("[STARTED] Weather sensors: {0}, 4800bps, Modbus RTU, slaves 1/2/3" -f $weatherPort) -ForegroundColor Green
    }
} elseif ($weatherPortCandidates.Count -eq 0) {
    Write-Warning 'No CH340 serial port found; weather station gateway was not started.'
} else {
    Write-Warning ("Multiple CH340 serial ports found ({0}); weather station gateway was not started to avoid selecting the wrong device." -f ($weatherPortCandidates -join ', '))
}

Write-Host ''
Write-Host 'URLs:' -ForegroundColor Cyan
Write-Host ("  H5:      http://{0}:{1}" -f $serverIp, $h5Port)
Write-Host ("  Admin:   http://{0}:{1}" -f $serverIp, $adminPort)
Write-Host ("  Swagger: http://{0}:{1}/docs" -f $serverIp, $apiPort)

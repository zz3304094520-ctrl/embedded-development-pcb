$ErrorActionPreference = 'Stop'

$projectRoot = $PSScriptRoot
$relaySource = Join-Path $projectRoot 'huitian-backend\edge\relay_gateway'
$jetson = 'qiongyi@172.20.10.4'
$jetsonRoot = '/home/qiongyi/huitian-relay-gateway'

if (-not (Test-Path -LiteralPath $relaySource)) {
    throw "Relay package not found: $relaySource"
}

Write-Host '[1/3] Copying relay Agent to Jetson...' -ForegroundColor Cyan
ssh.exe $jetson "mkdir -p '$jetsonRoot'"
if ($LASTEXITCODE -ne 0) {
    throw 'Failed to create the Jetson deployment directory.'
}

scp.exe -r $relaySource "${jetson}:$jetsonRoot/"
if ($LASTEXITCODE -ne 0) {
    throw 'Failed to copy the relay Agent to the Jetson.'
}

Write-Host '[2/3] Installing systemd and udev hotplug services...' -ForegroundColor Cyan
ssh.exe -t $jetson "cd '$jetsonRoot' && sudo bash relay_gateway/install_jetson.sh"
if ($LASTEXITCODE -ne 0) {
    throw 'Jetson relay hotplug installation failed.'
}

Write-Host '[3/3] Reading service status...' -ForegroundColor Cyan
ssh.exe $jetson "systemctl is-enabled huitian-relay-agent.service; systemctl is-active huitian-relay-agent.service; systemctl --no-pager --full status huitian-relay-agent.service | tail -n 12"
if ($LASTEXITCODE -ne 0) {
    Write-Warning 'The package was installed, but the Agent is not active yet. Check whether the USB relay is inserted.'
}

Write-Host ''
Write-Host 'Deployment finished.' -ForegroundColor Green
Write-Host 'The default is RELAY_DRY_RUN=true. After a load-disconnected safety test, edit:'
Write-Host '  sudo nano /etc/huitian-relay-agent.env'
Write-Host 'Set RELAY_DRY_RUN=false, then run:'
Write-Host '  sudo systemctl restart huitian-relay-agent.service'

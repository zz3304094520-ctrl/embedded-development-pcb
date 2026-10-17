$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    $pythonCandidates = @(
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe",
        "python"
    )
    $pythonExe = $null
    foreach ($candidate in $pythonCandidates) {
        if ($candidate -eq "python") {
            $command = Get-Command python -ErrorAction SilentlyContinue
            if ($command) {
                $version = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
                if ($version -in @("3.11", "3.12")) {
                    $pythonExe = "python"
                    break
                }
            }
        } elseif (Test-Path $candidate) {
            $pythonExe = $candidate
            break
        }
    }
    if (-not $pythonExe) {
        throw "未找到 Python 3.11 或 3.12，请先安装 Python 3.12。"
    }
    & $pythonExe -m venv .venv
}

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r requirements.txt

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
}

& $venvPython scripts\init_demo_data.py
Write-Host "Swagger: http://172.20.10.5:8000/docs" -ForegroundColor Green
& $venvPython -m uvicorn app.main:app --host 0.0.0.0 --port 8000

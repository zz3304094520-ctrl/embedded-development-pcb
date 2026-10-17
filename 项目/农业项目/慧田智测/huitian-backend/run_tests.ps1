$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    throw "虚拟环境不存在，请先运行 .\start.ps1 完成环境安装。"
}

& ".\.venv\Scripts\python.exe" -m pytest -v


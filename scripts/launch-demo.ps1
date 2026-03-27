param(
  [string]$PythonExe = "python",
  [switch]$SkipAgent
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$agentDir = Join-Path $root "server-agent"
$backendDir = Join-Path $root "backend"

function Start-WindowProcess {
  param(
    [string]$Title,
    [string]$Workdir,
    [string]$Command
  )

  Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$Workdir'; `$Host.UI.RawUI.WindowTitle = '$Title'; $Command"
  )
}

if (-not $SkipAgent) {
  Start-WindowProcess `
    -Title "GPU Agent" `
    -Workdir $agentDir `
    -Command "$PythonExe .\main.py"
}

Start-WindowProcess `
  -Title "GPU Backend" `
  -Workdir $backendDir `
  -Command "$PythonExe -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

Start-Sleep -Seconds 3
Start-Process "http://localhost:8000/"

Write-Host "平台已启动。"
if ($SkipAgent) {
  Write-Host "当前未启动本机 Agent，请在首页“接入中心”切换到远程服务器模式。"
} else {
  Write-Host "当前适合演示本机模式；如果要切到服务器，请在首页“接入中心”改为远程服务器模式。"
}

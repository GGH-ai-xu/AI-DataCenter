param()

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $root ".venv\Scripts\python.exe"
$frontendNodeModules = Join-Path $root "frontend\node_modules"
$agentDir = Join-Path $root "server-agent"
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"

function Resolve-CommandPath {
  param([string]$CommandName)

  $command = Get-Command $CommandName -ErrorAction SilentlyContinue | Select-Object -First 1
  if (-not $command) {
    return $null
  }

  if ($command.Path) {
    return $command.Path
  }

  return $command.Source
}

function Get-FreePort {
  $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
  $listener.Start()
  try {
    return $listener.LocalEndpoint.Port
  } finally {
    $listener.Stop()
  }
}

function Wait-HttpReady {
  param(
    [string]$Name,
    [string]$Url,
    [int]$Port,
    [string]$LaunchCommand,
    [int]$TimeoutSeconds = 45
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    try {
      Invoke-WebRequest -Uri $Url -TimeoutSec 2 -UseBasicParsing | Out-Null
      return
    } catch {
      Start-Sleep -Milliseconds 500
    }
  }

  throw "$Name failed to become ready on port $Port. Launch command: $LaunchCommand"
}

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
  ) | Out-Null
}

if (-not (Test-Path $pythonExe)) {
  throw "Python virtual environment not found: $pythonExe. Run install-deps.bat first."
}

if (-not (Test-Path $frontendNodeModules)) {
  throw "Frontend dependencies not found: $frontendNodeModules. Run install-deps.bat first."
}

$npmCmd = Resolve-CommandPath "npm"
if (-not $npmCmd) {
  throw "npm not found. Please install Node.js first."
}

$pythonExe = (Resolve-Path $pythonExe).Path
$agentPort = Get-FreePort
$backendPort = Get-FreePort
while ($backendPort -eq $agentPort) {
  $backendPort = Get-FreePort
}

$frontendPort = Get-FreePort
while ($frontendPort -in @($agentPort, $backendPort)) {
  $frontendPort = Get-FreePort
}

$agentUrl = "http://127.0.0.1:$agentPort"
$backendUrl = "http://127.0.0.1:$backendPort"
$frontendUrl = "http://127.0.0.1:$frontendPort/"

$agentCommand = "`$env:GPU_AGENT_PORT='$agentPort'; & '$pythonExe' .\main.py"
$backendCommand = "`$env:PORT='$backendPort'; `$env:AGENT_URL='$agentUrl'; & '$pythonExe' -m uvicorn app.main:app --host 127.0.0.1 --port $backendPort"
$frontendCommand = "`$env:DEV_BACKEND_URL='$backendUrl'; `$env:DEV_BACKEND_WS_URL='ws://127.0.0.1:$backendPort'; & '$npmCmd' run dev -- --host 127.0.0.1 --port $frontendPort"

Write-Host "Starting Agent on $agentUrl"
Start-WindowProcess -Title "GPU Agent" -Workdir $agentDir -Command $agentCommand
Wait-HttpReady -Name "Agent" -Url "$agentUrl/api/health" -Port $agentPort -LaunchCommand $agentCommand

Write-Host "Starting Backend on $backendUrl"
Start-WindowProcess -Title "GPU Backend" -Workdir $backendDir -Command $backendCommand
Wait-HttpReady -Name "Backend" -Url "$backendUrl/api/health" -Port $backendPort -LaunchCommand $backendCommand

Write-Host "Starting Frontend on $frontendUrl"
Start-WindowProcess -Title "GPU Frontend" -Workdir $frontendDir -Command $frontendCommand
Wait-HttpReady -Name "Frontend" -Url $frontendUrl -Port $frontendPort -LaunchCommand $frontendCommand

Write-Host "Agent URL: $agentUrl"
Write-Host "Backend URL: $backendUrl"
Write-Host "Frontend URL: $frontendUrl"
Start-Process $frontendUrl

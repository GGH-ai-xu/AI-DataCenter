param()

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\dev-launch-helpers.ps1"
Initialize-ConsoleEncoding

$root = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $root ".venv\Scripts\python.exe"
$frontendNodeModules = Join-Path $root "frontend\node_modules"
$desktopShellNodeModules = Join-Path $root "desktop-shell\node_modules"
$desktopShellElectron = Join-Path $root "desktop-shell\node_modules\electron\dist\electron.exe"
$desktopShellLauncherPrep = Join-Path $root "scripts\prepare-electron-dev-launcher.js"
$desktopShellLauncherName = "GPUGovernanceWorkbench.exe"
$agentDir = Join-Path $root "server-agent"
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"
$desktopShellDir = Join-Path $root "desktop-shell"

function Start-DesktopShellProcess {
  param([hashtable]$LaunchSpec)

  $cmdStatements = @(
    "set ""DESKTOP_DEV_SERVER_URL=$($LaunchSpec.ServerUrl)""",
    "set ""DESKTOP_DEV_BACKEND_URL=$($LaunchSpec.BackendUrl)""",
    "set ""DESKTOP_DEV_AGENT_URL=$($LaunchSpec.AgentUrl)""",
    ('start "" /d "{0}" "{1}" .' -f $LaunchSpec.Workdir, $LaunchSpec.LauncherPath)
  )

  Start-Process cmd.exe -WindowStyle Hidden -ArgumentList @(
    "/d",
    "/c",
    ($cmdStatements -join " && ")
  ) | Out-Null
}

function Prepare-ElectronDevLauncher {
  param(
    [string]$NodePath,
    [string]$ScriptPath
  )

  $launcherPath = & $NodePath $ScriptPath
  if ($LASTEXITCODE -ne 0) {
    throw "Failed to prepare Electron dev launcher."
  }

  $resolved = $launcherPath.Trim()
  if (-not $resolved) {
    throw "Electron dev launcher path is empty."
  }

  if (-not (Test-Path $resolved)) {
    throw "Electron dev launcher not found: $resolved"
  }

  if ((Split-Path -Leaf $resolved) -ne $desktopShellLauncherName) {
    throw "Unexpected Electron dev launcher name: $resolved"
  }

  return $resolved
}

if (-not (Test-Path $pythonExe)) {
  throw "Python virtual environment not found: $pythonExe. Run install-deps.bat first."
}

if (-not (Test-Path $frontendNodeModules)) {
  throw "Frontend dependencies not found: $frontendNodeModules. Run install-deps.bat first."
}

if (-not (Test-Path $desktopShellNodeModules)) {
  throw "Desktop shell dependencies not found: $desktopShellNodeModules. Run install-deps.bat first."
}

if (-not (Test-Path $desktopShellElectron)) {
  throw "Electron executable not found: $desktopShellElectron. Run install-deps.bat first."
}

if (-not (Test-Path $desktopShellLauncherPrep)) {
  throw "Electron launcher preparation script not found: $desktopShellLauncherPrep"
}

$npmCmd = Resolve-CommandPath "npm"
if (-not $npmCmd) {
  throw "npm not found. Please install Node.js first."
}

$nodeCmd = Resolve-CommandPath "node"
if (-not $nodeCmd) {
  throw "node not found. Please install Node.js first."
}

$pythonExe = (Resolve-Path $pythonExe).Path
$npmCliPath = Resolve-NpmCliPath -NodePath $nodeCmd
$desktopLauncherExe = Prepare-ElectronDevLauncher -NodePath $nodeCmd -ScriptPath $desktopShellLauncherPrep
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

Register-ManagedServiceShutdown

Write-ServiceLog -ServiceName "Launcher" -Message "Starting Agent on $agentUrl"
$agentProcess = Start-ManagedServiceProcess `
  -ServiceName "Agent" `
  -FilePath $pythonExe `
  -ArgumentList @(".\main.py") `
  -WorkingDirectory $agentDir `
  -Environment @{
    PYTHONIOENCODING = "utf-8"
    PYTHONUTF8 = "1"
    GPU_AGENT_PORT = $agentPort
  }
Register-ProcessLogPump -ServiceName "Agent" -Process $agentProcess
Wait-HttpReady -Name "Agent" -Url "$agentUrl/api/health" -Port $agentPort -LaunchCommand "$pythonExe .\main.py"

Write-ServiceLog -ServiceName "Launcher" -Message "Starting Backend on $backendUrl"
$backendProcess = Start-ManagedServiceProcess `
  -ServiceName "Backend" `
  -FilePath $pythonExe `
  -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$backendPort") `
  -WorkingDirectory $backendDir `
  -Environment @{
    PYTHONIOENCODING = "utf-8"
    PYTHONUTF8 = "1"
    PORT = $backendPort
    AGENT_URL = $agentUrl
  }
Register-ProcessLogPump -ServiceName "Backend" -Process $backendProcess
Wait-HttpReady -Name "Backend" -Url "$backendUrl/api/health" -Port $backendPort -LaunchCommand "$pythonExe -m uvicorn app.main:app"

Write-ServiceLog -ServiceName "Launcher" -Message "Starting Frontend on $frontendUrl"
$frontendProcess = Start-ManagedServiceProcess `
  -ServiceName "Frontend" `
  -FilePath $nodeCmd `
  -ArgumentList @($npmCliPath, "run", "dev", "--", "--host", "127.0.0.1", "--port", "$frontendPort") `
  -WorkingDirectory $frontendDir `
  -Environment @{
    DEV_BACKEND_URL = $backendUrl
    DEV_BACKEND_WS_URL = "ws://127.0.0.1:$backendPort"
  }
Register-ProcessLogPump -ServiceName "Frontend" -Process $frontendProcess
Wait-HttpReady -Name "Frontend" -Url $frontendUrl -Port $frontendPort -LaunchCommand "$nodeCmd $npmCliPath run dev"

Write-ServiceLog -ServiceName "Launcher" -Message "Desktop shell launcher: $desktopLauncherExe"
Write-ServiceLog -ServiceName "Launcher" -Message "GPU Desktop Shell: launching direct runtime process"
Start-DesktopShellProcess -LaunchSpec @{
  Workdir = $desktopShellDir
  LauncherPath = $desktopLauncherExe
  ServerUrl = $frontendUrl
  BackendUrl = $backendUrl
  AgentUrl = $agentUrl
}

Write-ServiceLog -ServiceName "Launcher" -Message "Agent URL: $agentUrl"
Write-ServiceLog -ServiceName "Launcher" -Message "Backend URL: $backendUrl"
Write-ServiceLog -ServiceName "Launcher" -Message "Frontend URL: $frontendUrl"
Write-ServiceLog -ServiceName "Launcher" -Message "Desktop mode: Electron dev shell connected to $frontendUrl"

while ($true) {
  Start-Sleep -Seconds 1
}

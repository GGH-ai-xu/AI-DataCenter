param()

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\dev-launch-helpers.ps1"
. "$PSScriptRoot\dev-managed-service-state.ps1"
. "$PSScriptRoot\runtime-master-key.ps1"
Initialize-ConsoleEncoding

$root = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $root ".venv\Scripts\python.exe"
$frontendNodeModules = Join-Path $root "frontend\node_modules"
$agentDir = Join-Path $root "server-agent"
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"

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

$nodeCmd = Resolve-CommandPath "node"
if (-not $nodeCmd) {
  throw "node not found. Please install Node.js first."
}

$pythonExe = (Resolve-Path $pythonExe).Path
$npmCliPath = Resolve-NpmCliPath -NodePath $nodeCmd
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
$runtimeMasterKey = Ensure-RepoRuntimeMasterKey -RepoRoot $root

Clear-StaleManagedServices -RepoRoot $root
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
Save-ManagedServiceState -ServiceName "Agent" -Process $agentProcess -ExecutablePath $pythonExe -Signature @(".\main.py")
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
    GPU_GOV_MASTER_KEY = $runtimeMasterKey
  }
Save-ManagedServiceState -ServiceName "Backend" -Process $backendProcess -ExecutablePath $pythonExe -Signature @("-m", "uvicorn", "app.main:app")
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
Save-ManagedServiceState -ServiceName "Frontend" -Process $frontendProcess -ExecutablePath $nodeCmd -Signature @($npmCliPath, "run", "dev")
Register-ProcessLogPump -ServiceName "Frontend" -Process $frontendProcess
Wait-HttpReady -Name "Frontend" -Url $frontendUrl -Port $frontendPort -LaunchCommand "$nodeCmd $npmCliPath run dev"

Write-ServiceLog -ServiceName "Launcher" -Message "Agent URL: $agentUrl"
Write-ServiceLog -ServiceName "Launcher" -Message "Backend URL: $backendUrl"
Write-ServiceLog -ServiceName "Launcher" -Message "Frontend URL: $frontendUrl"
Start-Process $frontendUrl | Out-Null

while ($true) {
  Start-Sleep -Seconds 1
}

param()

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\dev-launch-helpers.ps1"
. "$PSScriptRoot\electron-dev-session.ps1"
. "$PSScriptRoot\runtime-master-key.ps1"
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

$desktopBootstrapProcess = $null
$desktopProcess = $null
$desktopSessionFile = $null

$pythonExe = (Resolve-Path $pythonExe).Path
$npmCliPath = Resolve-NpmCliPath -NodePath $nodeCmd
$desktopLauncherExe = Prepare-ElectronDevLauncher -NodePath $nodeCmd -ScriptPath $desktopShellLauncherPrep -ExpectedLauncherName $desktopShellLauncherName
$existingDesktopProcess = Get-RunningDesktopShellRootProcess -LauncherPath $desktopLauncherExe
while ($existingDesktopProcess) {
  Stop-OrphanedDesktopShellSession -DesktopRootProcess $existingDesktopProcess -RepoRoot $root
  $existingDesktopProcess = Get-RunningDesktopShellRootProcess -LauncherPath $desktopLauncherExe
}
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
    GPU_GOV_MASTER_KEY = $runtimeMasterKey
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
$desktopSessionFile = New-DesktopDevSessionFilePath
$desktopBootstrapProcess = Start-DesktopShellProcess -LaunchSpec @{
  Workdir = $desktopShellDir
  LauncherPath = $desktopLauncherExe
  ServerUrl = $frontendUrl
  BackendUrl = $backendUrl
  AgentUrl = $agentUrl
  SessionFile = $desktopSessionFile
  LauncherPid = $PID
}
$desktopSessionInfo = Wait-DesktopDevSessionInfo -SessionFile $desktopSessionFile
if (-not $desktopSessionInfo) {
  $desktopBootstrapProcess.WaitForExit()
  throw "Desktop shell session file was not written. Bootstrap exit code: $($desktopBootstrapProcess.ExitCode)"
}
$desktopRootPid = [int]$desktopSessionInfo.pid
Write-ServiceLog -ServiceName "Launcher" -Message "Desktop shell root process: $desktopRootPid"
$desktopProcess = [System.Diagnostics.Process]::GetProcessById($desktopRootPid)
$null = Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action {
  & taskkill /PID $event.MessageData.DesktopPid /T /F *> $null
  if (Test-Path $event.MessageData.SessionFile) {
    Remove-Item -Path $event.MessageData.SessionFile -Force -ErrorAction SilentlyContinue
  }
} -MessageData @{
  DesktopPid = $desktopRootPid
  SessionFile = $desktopSessionFile
}

Write-ServiceLog -ServiceName "Launcher" -Message "Agent URL: $agentUrl"
Write-ServiceLog -ServiceName "Launcher" -Message "Backend URL: $backendUrl"
Write-ServiceLog -ServiceName "Launcher" -Message "Frontend URL: $frontendUrl"
Write-ServiceLog -ServiceName "Launcher" -Message "Desktop mode: Electron dev shell connected to $frontendUrl"

$desktopExitCode = 0
try {
  $desktopProcess.WaitForExit()
  $desktopExitCode = $desktopProcess.ExitCode
  Write-ServiceLog -ServiceName "Launcher" -Message "Desktop shell exited with code $desktopExitCode"
} finally {
  Stop-ManagedServiceProcesses
  if ($null -ne $desktopProcess) {
    $desktopProcess.Dispose()
  }
  if ($null -ne $desktopBootstrapProcess) {
    $desktopBootstrapProcess.Dispose()
  }
  Remove-DesktopDevSessionFile -SessionFile $desktopSessionFile
}

if ($desktopExitCode -ne 0) {
  exit $desktopExitCode
}

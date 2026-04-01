# Single-Terminal Dev Launch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `start-dev.ps1` 和 `start-electron-dev.ps1` 改为单终端开发入口，在当前终端统一打印 `Agent`、`Backend`、`Frontend` 日志，并按服务加前缀，同时保留动态端口、健康检查和 Electron 直启行为。

**Architecture:** 把进程启动、环境注入、日志转发、健康检查和退出清理抽到共享 PowerShell helper 中，两个入口脚本仅负责组装各自的服务启动参数。日志聚合采用主控制器脚本接管子进程 `stdout/stderr` 的方式，Electron 继续作为独立 GUI 进程启动，不进入多终端模式。

**Tech Stack:** PowerShell 5+, Windows `Start-Process`, Python unittest, Electron dev launcher, FastAPI/Uvicorn, Vite

---

## File Structure

- Create: `scripts/dev-launch-helpers.ps1`
  - 负责共享的 PowerShell 能力：命令解析、动态端口、带环境变量的进程启动、日志前缀输出、健康检查、退出清理。
- Modify: `scripts/start-dev.ps1`
  - 改为单终端控制器，启动 Agent、Backend、Frontend 并汇总日志，保留浏览器自动打开。
- Modify: `scripts/start-electron-dev.ps1`
  - 改为单终端控制器，启动 Agent、Backend、Frontend 并汇总日志，Electron 继续直接启动 launcher EXE。
- Modify: `tests/test_start_dev_scripts.py`
  - 添加结构性回归测试，保证两个脚本不再使用旧的多窗口 PowerShell 宿主模式，并显式依赖共享 helper。

### Task 1: Lock the new launch shape with failing tests

**Files:**
- Modify: `tests/test_start_dev_scripts.py`
- Test: `tests/test_start_dev_scripts.py`

- [ ] **Step 1: Write the failing tests**

Add assertions for the new single-terminal structure:

```python
    def test_start_dev_ps1_uses_shared_single_terminal_helpers(self):
        script = (ROOT / "scripts" / "start-dev.ps1").read_text(encoding="utf-8")

        self.assertIn('. "$PSScriptRoot\\dev-launch-helpers.ps1"', script)
        self.assertIn("Start-ManagedServiceProcess", script)
        self.assertIn("Register-ProcessLogPump", script)
        self.assertIn("Stop-ManagedServiceProcesses", script)
        self.assertNotIn('Start-WindowProcess -Title "GPU Agent"', script)
        self.assertNotIn('Start-WindowProcess -Title "GPU Backend"', script)
        self.assertNotIn('Start-WindowProcess -Title "GPU Frontend"', script)

    def test_start_electron_dev_ps1_uses_shared_single_terminal_helpers(self):
        script = (ROOT / "scripts" / "start-electron-dev.ps1").read_text(encoding="utf-8")

        self.assertIn('. "$PSScriptRoot\\dev-launch-helpers.ps1"', script)
        self.assertIn("Start-ManagedServiceProcess", script)
        self.assertIn("Register-ProcessLogPump", script)
        self.assertIn("Stop-ManagedServiceProcesses", script)
        self.assertNotIn('Start-WindowProcess -Title "GPU Agent"', script)
        self.assertNotIn('Start-WindowProcess -Title "GPU Backend"', script)
        self.assertNotIn('Start-WindowProcess -Title "GPU Frontend"', script)

    def test_dev_launch_helpers_define_log_prefix_and_cleanup_functions(self):
        script = (ROOT / "scripts" / "dev-launch-helpers.ps1").read_text(encoding="utf-8")

        self.assertIn("function Write-ServiceLog", script)
        self.assertIn("function Start-ManagedServiceProcess", script)
        self.assertIn("function Register-ProcessLogPump", script)
        self.assertIn("function Stop-ManagedServiceProcesses", script)
        self.assertIn("[ConsoleCancelEventHandler]", script)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
py -3 -m unittest ^
  tests.test_start_dev_scripts.StartDevScriptTests.test_start_dev_ps1_uses_shared_single_terminal_helpers ^
  tests.test_start_dev_scripts.StartDevScriptTests.test_start_electron_dev_ps1_uses_shared_single_terminal_helpers ^
  tests.test_start_dev_scripts.StartDevScriptTests.test_dev_launch_helpers_define_log_prefix_and_cleanup_functions -v
```

Expected: FAIL because `scripts/dev-launch-helpers.ps1` does not exist yet and the launch scripts still rely on the old multi-window service startup pattern.

- [ ] **Step 3: Commit the red test**

```bash
git add tests/test_start_dev_scripts.py
git commit -m "test: lock single-terminal dev launcher structure"
```

### Task 2: Build the shared PowerShell launcher helpers

**Files:**
- Create: `scripts/dev-launch-helpers.ps1`
- Test: `tests/test_start_dev_scripts.py`

- [ ] **Step 1: Write the helper file with focused responsibilities**

Create `scripts/dev-launch-helpers.ps1` with these functions and constants:

```powershell
Set-StrictMode -Version Latest

$script:ManagedServiceProcesses = @()
$script:ProcessLogPumpRegistrations = @()

function Write-ServiceLog {
  param(
    [string]$ServiceName,
    [string]$Message,
    [string]$Level = "INFO"
  )

  $timestamp = Get-Date -Format "HH:mm:ss"
  Write-Host "$timestamp [$ServiceName][$Level] $Message"
}

function New-ProcessStartInfo {
  param(
    [string]$FilePath,
    [string[]]$ArgumentList,
    [string]$WorkingDirectory,
    [hashtable]$Environment
  )

  $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
  $startInfo.FileName = $FilePath
  foreach ($argument in $ArgumentList) {
    [void]$startInfo.ArgumentList.Add($argument)
  }
  $startInfo.WorkingDirectory = $WorkingDirectory
  $startInfo.UseShellExecute = $false
  $startInfo.RedirectStandardOutput = $true
  $startInfo.RedirectStandardError = $true
  $startInfo.CreateNoWindow = $true

  foreach ($entry in $Environment.GetEnumerator()) {
    $startInfo.Environment[$entry.Key] = [string]$entry.Value
  }

  return $startInfo
}

function Start-ManagedServiceProcess {
  param(
    [string]$ServiceName,
    [string]$FilePath,
    [string[]]$ArgumentList,
    [string]$WorkingDirectory,
    [hashtable]$Environment = @{}
  )

  $startInfo = New-ProcessStartInfo -FilePath $FilePath -ArgumentList $ArgumentList -WorkingDirectory $WorkingDirectory -Environment $Environment
  $process = [System.Diagnostics.Process]::new()
  $process.StartInfo = $startInfo
  $process.EnableRaisingEvents = $true
  [void]$process.Start()
  $script:ManagedServiceProcesses += [PSCustomObject]@{ ServiceName = $ServiceName; Process = $process }
  return $process
}

function Register-ProcessLogPump {
  param(
    [string]$ServiceName,
    [System.Diagnostics.Process]$Process
  )

  $stdoutRegistration = Register-ObjectEvent -InputObject $Process -EventName OutputDataReceived -Action {
    if ($EventArgs.Data) {
      Write-ServiceLog -ServiceName $Event.MessageData.ServiceName -Message $EventArgs.Data
    }
  } -MessageData @{ ServiceName = $ServiceName }

  $stderrRegistration = Register-ObjectEvent -InputObject $Process -EventName ErrorDataReceived -Action {
    if ($EventArgs.Data) {
      Write-ServiceLog -ServiceName $Event.MessageData.ServiceName -Message $EventArgs.Data -Level "ERROR"
    }
  } -MessageData @{ ServiceName = $ServiceName }

  $exitRegistration = Register-ObjectEvent -InputObject $Process -EventName Exited -Action {
    Write-ServiceLog -ServiceName $Event.MessageData.ServiceName -Message "process exited with code $($Sender.ExitCode)" -Level "WARN"
  } -MessageData @{ ServiceName = $ServiceName }

  $Process.BeginOutputReadLine()
  $Process.BeginErrorReadLine()
  $script:ProcessLogPumpRegistrations += @($stdoutRegistration, $stderrRegistration, $exitRegistration)
}
```

- [ ] **Step 2: Add shutdown cleanup helpers**

Append explicit cleanup functions:

```powershell
function Stop-ManagedServiceProcesses {
  foreach ($entry in $script:ManagedServiceProcesses) {
    $process = $entry.Process
    if (-not $process.HasExited) {
      Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
  }

  foreach ($registration in $script:ProcessLogPumpRegistrations) {
    Unregister-Event -SubscriptionId $registration.Id -ErrorAction SilentlyContinue
    Remove-Job -Id $registration.Id -Force -ErrorAction SilentlyContinue
  }
}

function Register-ManagedServiceShutdown {
  $null = Register-EngineEvent PowerShell.Exiting -Action {
    Stop-ManagedServiceProcesses
  }

  $handler = [ConsoleCancelEventHandler]{
    param($sender, $eventArgs)
    $eventArgs.Cancel = $true
    Stop-ManagedServiceProcesses
    exit 0
  }
  [Console]::CancelKeyPress += $handler
}
```

- [ ] **Step 3: Run targeted tests to verify helper structure**

Run:

```bash
py -3 -m unittest tests.test_start_dev_scripts.StartDevScriptTests.test_dev_launch_helpers_define_log_prefix_and_cleanup_functions -v
```

Expected: PASS.

- [ ] **Step 4: Commit the helper layer**

```bash
git add scripts/dev-launch-helpers.ps1 tests/test_start_dev_scripts.py
git commit -m "feat: add shared single-terminal launch helpers"
```

### Task 3: Refactor the browser dev launcher to a single-terminal controller

**Files:**
- Modify: `scripts/start-dev.ps1`
- Modify: `tests/test_start_dev_scripts.py`
- Test: `tests/test_start_dev_scripts.py`

- [ ] **Step 1: Dot-source the helper and remove the old multi-window launcher**

Refactor the top of `scripts/start-dev.ps1`:

```powershell
param()

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\dev-launch-helpers.ps1"

$root = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $root ".venv\Scripts\python.exe"
$frontendNodeModules = Join-Path $root "frontend\node_modules"
$agentDir = Join-Path $root "server-agent"
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"
```

Delete `Start-WindowProcess` entirely from this file.

- [ ] **Step 2: Replace string-based command startup with managed process specs**

Start the three services through helper functions:

```powershell
Register-ManagedServiceShutdown

Write-ServiceLog -ServiceName "Launcher" -Message "Starting Agent on $agentUrl"
$agentProcess = Start-ManagedServiceProcess -ServiceName "Agent" -FilePath $pythonExe -ArgumentList @(".\main.py") -WorkingDirectory $agentDir -Environment @{
  GPU_AGENT_PORT = $agentPort
}
Register-ProcessLogPump -ServiceName "Agent" -Process $agentProcess
Wait-HttpReady -Name "Agent" -Url "$agentUrl/api/health" -Port $agentPort -LaunchCommand "$pythonExe .\main.py"

Write-ServiceLog -ServiceName "Launcher" -Message "Starting Backend on $backendUrl"
$backendProcess = Start-ManagedServiceProcess -ServiceName "Backend" -FilePath $pythonExe -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$backendPort") -WorkingDirectory $backendDir -Environment @{
  PORT = $backendPort
  AGENT_URL = $agentUrl
}
Register-ProcessLogPump -ServiceName "Backend" -Process $backendProcess
Wait-HttpReady -Name "Backend" -Url "$backendUrl/api/health" -Port $backendPort -LaunchCommand "$pythonExe -m uvicorn app.main:app"

Write-ServiceLog -ServiceName "Launcher" -Message "Starting Frontend on $frontendUrl"
$frontendProcess = Start-ManagedServiceProcess -ServiceName "Frontend" -FilePath $npmCmd -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1", "--port", "$frontendPort") -WorkingDirectory $frontendDir -Environment @{
  DEV_BACKEND_URL = $backendUrl
  DEV_BACKEND_WS_URL = "ws://127.0.0.1:$backendPort"
}
Register-ProcessLogPump -ServiceName "Frontend" -Process $frontendProcess
Wait-HttpReady -Name "Frontend" -Url $frontendUrl -Port $frontendPort -LaunchCommand "$npmCmd run dev"
```

- [ ] **Step 3: Keep the script alive and preserve browser open behavior**

At the end of `scripts/start-dev.ps1`, keep browser launch and wait on child processes:

```powershell
Write-ServiceLog -ServiceName "Launcher" -Message "Frontend URL: $frontendUrl"
Start-Process $frontendUrl | Out-Null

while ($true) {
  Start-Sleep -Seconds 1
}
```

Do not add silent fallbacks. If a child process exits early, the registered exit handler should print the exit line and the operator can stop the controller.

- [ ] **Step 4: Run targeted tests**

Run:

```bash
py -3 -m unittest ^
  tests.test_start_dev_scripts.StartDevScriptTests.test_start_dev_ps1_contains_dynamic_port_and_env_injection ^
  tests.test_start_dev_scripts.StartDevScriptTests.test_start_dev_ps1_uses_shared_single_terminal_helpers -v
```

Expected: PASS.

- [ ] **Step 5: Commit the browser launcher refactor**

```bash
git add scripts/start-dev.ps1 tests/test_start_dev_scripts.py
git commit -m "feat: run browser dev services in a single terminal"
```

### Task 4: Refactor the Electron dev launcher to a single-terminal controller

**Files:**
- Modify: `scripts/start-electron-dev.ps1`
- Modify: `tests/test_start_dev_scripts.py`
- Test: `tests/test_start_dev_scripts.py`

- [ ] **Step 1: Dot-source the helper and remove service-specific window startup**

At the top of `scripts/start-electron-dev.ps1`, add:

```powershell
param()

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\dev-launch-helpers.ps1"
```

Remove `Start-WindowProcess` from this file, but keep `Start-DesktopShellProcess` and `Prepare-ElectronDevLauncher`.

- [ ] **Step 2: Start Agent, Backend, Frontend via the shared helper**

Replace the three `Start-WindowProcess` service calls with:

```powershell
Register-ManagedServiceShutdown

Write-ServiceLog -ServiceName "Launcher" -Message "Starting Agent on $agentUrl"
$agentProcess = Start-ManagedServiceProcess -ServiceName "Agent" -FilePath $pythonExe -ArgumentList @(".\main.py") -WorkingDirectory $agentDir -Environment @{
  GPU_AGENT_PORT = $agentPort
}
Register-ProcessLogPump -ServiceName "Agent" -Process $agentProcess
Wait-HttpReady -Name "Agent" -Url "$agentUrl/api/health" -Port $agentPort -LaunchCommand "$pythonExe .\main.py"

Write-ServiceLog -ServiceName "Launcher" -Message "Starting Backend on $backendUrl"
$backendProcess = Start-ManagedServiceProcess -ServiceName "Backend" -FilePath $pythonExe -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$backendPort") -WorkingDirectory $backendDir -Environment @{
  PORT = $backendPort
  AGENT_URL = $agentUrl
}
Register-ProcessLogPump -ServiceName "Backend" -Process $backendProcess
Wait-HttpReady -Name "Backend" -Url "$backendUrl/api/health" -Port $backendPort -LaunchCommand "$pythonExe -m uvicorn app.main:app"

Write-ServiceLog -ServiceName "Launcher" -Message "Starting Frontend on $frontendUrl"
$frontendProcess = Start-ManagedServiceProcess -ServiceName "Frontend" -FilePath $npmCmd -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1", "--port", "$frontendPort") -WorkingDirectory $frontendDir -Environment @{
  DEV_BACKEND_URL = $backendUrl
  DEV_BACKEND_WS_URL = "ws://127.0.0.1:$backendPort"
}
Register-ProcessLogPump -ServiceName "Frontend" -Process $frontendProcess
Wait-HttpReady -Name "Frontend" -Url $frontendUrl -Port $frontendPort -LaunchCommand "$npmCmd run dev"
```

- [ ] **Step 3: Keep Electron direct-launch behavior intact**

Retain:

```powershell
Write-ServiceLog -ServiceName "Launcher" -Message "Desktop shell launcher: $desktopLauncherExe"
Start-DesktopShellProcess -LaunchSpec @{
  Workdir = $desktopShellDir
  LauncherPath = $desktopLauncherExe
  ServerUrl = $frontendUrl
  BackendUrl = $backendUrl
  AgentUrl = $agentUrl
}
```

Then keep the controller alive:

```powershell
while ($true) {
  Start-Sleep -Seconds 1
}
```

- [ ] **Step 4: Run targeted tests**

Run:

```bash
py -3 -m unittest ^
  tests.test_start_dev_scripts.StartDevScriptTests.test_start_electron_dev_ps1_contains_dynamic_port_and_env_injection ^
  tests.test_start_dev_scripts.StartDevScriptTests.test_start_electron_dev_ps1_launches_desktop_shell_without_powershell_host ^
  tests.test_start_dev_scripts.StartDevScriptTests.test_start_electron_dev_ps1_uses_shared_single_terminal_helpers -v
```

Expected: PASS.

- [ ] **Step 5: Commit the Electron launcher refactor**

```bash
git add scripts/start-electron-dev.ps1 tests/test_start_dev_scripts.py
git commit -m "feat: run electron dev services in a single terminal"
```

### Task 5: Final verification on Windows

**Files:**
- Modify: `scripts/start-dev.ps1`
- Modify: `scripts/start-electron-dev.ps1`
- Modify: `scripts/dev-launch-helpers.ps1`
- Modify: `tests/test_start_dev_scripts.py`
- Test: `tests/test_start_dev_scripts.py`

- [ ] **Step 1: Run the full script test suite**

Run:

```bash
py -3 -m unittest tests.test_start_dev_scripts -v
```

Expected: all tests PASS.

- [ ] **Step 2: Parse both PowerShell launchers for syntax errors**

Run:

```powershell
$parseErrors = $null
[void][System.Management.Automation.Language.Parser]::ParseFile("E:\Code\AI-DataCenter\scripts\start-dev.ps1", [ref]$null, [ref]$parseErrors)
[void][System.Management.Automation.Language.Parser]::ParseFile("E:\Code\AI-DataCenter\scripts\start-electron-dev.ps1", [ref]$null, [ref]$parseErrors)
if ($parseErrors.Count -gt 0) { $parseErrors | ForEach-Object { throw $_.Message } }
```

Expected: no output, exit success.

- [ ] **Step 3: Manual behavior check in Windows terminal**

Run:

```bash
start-dev.bat
```

Expected:

- Only one controller terminal remains open.
- Logs from Agent, Backend, Frontend appear in that terminal.
- Each line carries a service prefix.
- Browser opens to the dynamically selected frontend URL.

Then run:

```bash
start-electron-dev.bat
```

Expected:

- Only one controller terminal remains open.
- Agent, Backend, Frontend logs appear in that terminal.
- Electron opens as a separate GUI window without creating an extra log terminal.

- [ ] **Step 4: Commit the verified result**

```bash
git add scripts/dev-launch-helpers.ps1 scripts/start-dev.ps1 scripts/start-electron-dev.ps1 tests/test_start_dev_scripts.py
git commit -m "feat: consolidate dev service logs into one terminal"
```

## Self-Review

- Spec coverage:
  - 单终端控制器：Task 2, Task 3, Task 4
  - 服务前缀日志：Task 2
  - 退出清理：Task 2
  - Electron 直启保留：Task 4
  - Windows 验证：Task 5
- Placeholder scan:
  - No `TODO`, `TBD`, or deferred implementation markers remain.
- Type consistency:
  - Shared helper names used consistently across tests and both launcher scripts: `Write-ServiceLog`, `Start-ManagedServiceProcess`, `Register-ProcessLogPump`, `Stop-ManagedServiceProcesses`, `Register-ManagedServiceShutdown`.

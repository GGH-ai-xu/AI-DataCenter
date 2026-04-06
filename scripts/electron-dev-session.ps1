function Start-DesktopShellProcess {
  param([hashtable]$LaunchSpec)

  return Start-ManagedServiceProcess `
    -ServiceName "DesktopBootstrap" `
    -FilePath $LaunchSpec.LauncherPath `
    -ArgumentList @(".") `
    -WorkingDirectory $LaunchSpec.Workdir `
    -Environment @{
      DESKTOP_DEV_SERVER_URL = $LaunchSpec.ServerUrl
      DESKTOP_DEV_BACKEND_URL = $LaunchSpec.BackendUrl
      DESKTOP_DEV_AGENT_URL = $LaunchSpec.AgentUrl
      DESKTOP_DEV_SESSION_FILE = $LaunchSpec.SessionFile
      DESKTOP_DEV_LAUNCHER_PID = $LaunchSpec.LauncherPid
    }
}

function Prepare-ElectronDevLauncher {
  param(
    [string]$NodePath,
    [string]$ScriptPath,
    [string]$ExpectedLauncherName
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

  if ((Split-Path -Leaf $resolved) -ne $ExpectedLauncherName) {
    throw "Unexpected Electron dev launcher name: $resolved"
  }

  return $resolved
}

function Test-DesktopShellRootCommandLine {
  param(
    [string]$CommandLine,
    [string]$LauncherPath
  )

  if (-not $CommandLine -or $CommandLine -match '--type=') {
    return $false
  }

  $normalized = $CommandLine -replace '"', ''
  $launcherName = Split-Path -Leaf $LauncherPath
  return $normalized -like "*$launcherName*"
}

function Get-DesktopShellProcessSnapshot {
  param([string]$LauncherPath)

  $launcherName = Split-Path -Leaf $LauncherPath
  return Get-CimInstance Win32_Process -Filter ("Name = '{0}'" -f $launcherName) -ErrorAction SilentlyContinue |
    Where-Object {
      Test-DesktopShellRootCommandLine -CommandLine ([string]$_.CommandLine) -LauncherPath $LauncherPath
    }
}

function Get-RunningDesktopShellRootProcess {
  param([string]$LauncherPath)

  return Get-DesktopShellProcessSnapshot -LauncherPath $LauncherPath | Select-Object -First 1
}

function Stop-OrphanedDesktopShellSession {
  param(
    $DesktopRootProcess,
    [string]$RepoRoot
  )

  $sessionPid = [int]$DesktopRootProcess.ParentProcessId
  $targets = @($DesktopRootProcess.ProcessId)
  $targets += Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.ParentProcessId -eq $sessionPid -and $_.ProcessId -ne $DesktopRootProcess.ProcessId } |
    Where-Object { $_.Name -in @("python.exe", "node.exe") -and [string]$_.CommandLine -like "*$RepoRoot*" } |
    Select-Object -ExpandProperty ProcessId
  Write-ServiceLog -ServiceName "Launcher" -Message "Found existing Electron dev session rooted at PID $($DesktopRootProcess.ProcessId); replacing desktop/backend/frontend/agent processes."
  foreach ($targetPid in ($targets | Sort-Object -Unique)) {
    & taskkill /PID $targetPid /T /F *> $null
  }
  Start-Sleep -Milliseconds 600
  $remainingTargets = @($targets | Where-Object { $null -ne (Get-Process -Id $_ -ErrorAction SilentlyContinue) })
  if ($remainingTargets.Count -gt 0) {
    throw "Failed to replace existing Electron dev session: $($remainingTargets -join ', ')"
  }
}

function New-DesktopDevSessionFilePath {
  $sessionRoot = Get-DesktopDevSessionRoot
  New-Item -ItemType Directory -Path $sessionRoot -Force | Out-Null
  return Join-Path $sessionRoot ("session-{0}.json" -f [guid]::NewGuid().ToString("N"))
}

function Get-DesktopDevSessionRoot {
  return Join-Path ([System.IO.Path]::GetTempPath()) "ai-datacenter-electron-dev"
}

function Test-DesktopDevSessionPid {
  param([int]$DesktopPid)

  if ($DesktopPid -le 0) {
    return $false
  }

  $sessionRoot = Get-DesktopDevSessionRoot
  if (-not (Test-Path $sessionRoot)) {
    return $false
  }

  foreach ($sessionFile in (Get-ChildItem -Path $sessionRoot -Filter "session-*.json" -File -ErrorAction SilentlyContinue)) {
    try {
      $session = Get-Content -Path $sessionFile.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
      if ([int]$session.pid -eq $DesktopPid -and [int]$session.launcherPid -gt 0) {
        return $true
      }
    } catch {
    }
  }

  return $false
}

function Wait-DesktopDevSessionInfo {
  param(
    [string]$SessionFile,
    [int]$TimeoutSeconds = 12
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    if (Test-Path $SessionFile) {
      try {
        $session = Get-Content -Path $SessionFile -Raw -Encoding UTF8 | ConvertFrom-Json
        $desktopPid = [int]$session.pid
        if ($desktopPid -gt 0) {
          $desktopProcess = Get-Process -Id $desktopPid -ErrorAction SilentlyContinue
          if ($null -ne $desktopProcess) {
            return $session
          }
        }
      } catch {
      }
    }
    Start-Sleep -Milliseconds 200
  }

  return $null
}

function Remove-DesktopDevSessionFile {
  param([string]$SessionFile)

  if ($SessionFile -and (Test-Path $SessionFile)) {
    Remove-Item -Path $SessionFile -Force -ErrorAction SilentlyContinue
  }
}

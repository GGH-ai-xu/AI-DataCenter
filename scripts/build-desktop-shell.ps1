param(
  [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$frontendDir = Join-Path $root "frontend"
$desktopShellDir = Join-Path $root "desktop-shell"
$windowsPackageDir = Join-Path $root "dist\windows-package"
$windowsAppDir = Join-Path $windowsPackageDir "app"
$distPyInstallerDir = Join-Path $root "dist\pyinstaller"
$buildSpecDir = Join-Path $root "build\pyinstaller"
$backendSpec = Join-Path $buildSpecDir "GPUGovernanceBackend.spec"
$agentSpec = Join-Path $buildSpecDir "GPUServerAgent.spec"
$launcherSpec = Join-Path $buildSpecDir "GPUGovernanceWorkbench.spec"
$defaultElectronMirror = "https://npmmirror.com/mirrors/electron/"
$venvPython = Join-Path $root ".venv\Scripts\python.exe"

if (-not $PythonExe) {
  if (Test-Path $venvPython) {
    $PythonExe = (Resolve-Path $venvPython).Path
  } else {
    $PythonExe = "python"
  }
}

function Run-Step {
  param(
    [string]$Title,
    [string]$Workdir,
    [string[]]$CommandArgs
  )

  Write-Host "==> $Title"
  Push-Location $Workdir
  try {
    $command = $CommandArgs[0]
    $arguments = @()
    if ($CommandArgs.Length -gt 1) {
      $arguments = $CommandArgs[1..($CommandArgs.Length - 1)]
    }
    & $command @arguments
    if ($LASTEXITCODE -ne 0) {
      throw "Command failed: $($CommandArgs -join ' ')"
    }
  } finally {
    Pop-Location
  }
}

function Ensure-Command {
  param([string]$Name)
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "$Name not found."
  }
}

function Sync-Directory {
  param(
    [string]$Source,
    [string]$Target
  )

  if (-not (Test-Path $Source)) {
    throw "Missing source directory: $Source"
  }

  if (Test-Path $Target) {
    Remove-Item -Recurse -Force $Target
  }

  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Target) | Out-Null
  Copy-Item -Recurse -Force $Source $Target
}

Ensure-Command "npm"
Ensure-Command $PythonExe

if (-not $env:ELECTRON_MIRROR) {
  $env:ELECTRON_MIRROR = $defaultElectronMirror
}

Write-Host "Using Python interpreter: $PythonExe"
Write-Host "Electron binary mirror: $($env:ELECTRON_MIRROR)"

Run-Step -Title "Build frontend" -Workdir $frontendDir -CommandArgs @("npm", "run", "build")

Run-Step -Title "Build backend runtime" -Workdir $root -CommandArgs @(
  $PythonExe, "-m", "PyInstaller", "--noconfirm", $backendSpec
)
Run-Step -Title "Build agent runtime" -Workdir $root -CommandArgs @(
  $PythonExe, "-m", "PyInstaller", "--noconfirm", $agentSpec
)
Run-Step -Title "Build launcher runtime" -Workdir $root -CommandArgs @(
  $PythonExe, "-m", "PyInstaller", "--noconfirm", $launcherSpec
)

New-Item -ItemType Directory -Force -Path $windowsAppDir | Out-Null
Sync-Directory -Source (Join-Path $distPyInstallerDir "GPUGovernanceBackend") -Target (Join-Path $windowsAppDir "backend")
Sync-Directory -Source (Join-Path $distPyInstallerDir "GPUServerAgent") -Target (Join-Path $windowsAppDir "agent")
Sync-Directory -Source (Join-Path $distPyInstallerDir "GPUGovernanceWorkbench") -Target (Join-Path $windowsAppDir "launcher")
Write-Host "Windows package runtime ready: $windowsPackageDir"

Run-Step -Title "Install desktop shell dependencies" -Workdir $desktopShellDir -CommandArgs @("npm", "ci", "--include=dev")
Run-Step -Title "Build desktop installer" -Workdir $desktopShellDir -CommandArgs @("npm", "run", "dist")

Write-Host "Desktop installer ready under dist/electron"

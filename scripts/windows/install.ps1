param(
  [string]$InstallDir = (Join-Path $env:LOCALAPPDATA 'GPU-Governance-Workbench')
)

$ErrorActionPreference = 'Stop'

$packageRoot = $PSScriptRoot
$appSource = Join-Path $packageRoot 'app'
$desktopShortcut = Join-Path ([Environment]::GetFolderPath('Desktop')) 'GPU 共享治理平台.lnk'
$startMenuDir = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\GPU 共享治理平台'
$startMenuShortcut = Join-Path $startMenuDir 'GPU 共享治理平台.lnk'
$launcherPath = Join-Path $InstallDir 'launcher\GPUGovernanceWorkbench.exe'
$uninstallPath = Join-Path $InstallDir 'uninstall.ps1'
$uninstallBatPath = Join-Path $InstallDir 'uninstall.bat'

if (-not (Test-Path $appSource)) {
  throw "未找到安装包目录：$appSource"
}

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Copy-Item -Path (Join-Path $appSource '*') -Destination $InstallDir -Recurse -Force
Copy-Item -Path (Join-Path $packageRoot 'uninstall.ps1') -Destination $uninstallPath -Force

@"
@echo off
powershell -ExecutionPolicy Bypass -File "%~dp0uninstall.ps1"
"@ | Set-Content -Path $uninstallBatPath -Encoding ASCII

New-Item -ItemType Directory -Force -Path $startMenuDir | Out-Null
$shell = New-Object -ComObject WScript.Shell

$desktop = $shell.CreateShortcut($desktopShortcut)
$desktop.TargetPath = $launcherPath
$desktop.WorkingDirectory = Split-Path -Parent $launcherPath
$desktop.Save()

$menu = $shell.CreateShortcut($startMenuShortcut)
$menu.TargetPath = $launcherPath
$menu.WorkingDirectory = Split-Path -Parent $launcherPath
$menu.Save()

Write-Host "Install complete: $InstallDir"
Write-Host "Desktop shortcut created."

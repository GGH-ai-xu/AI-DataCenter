param(
  [string]$PythonExe = "python",
  [switch]$NoClean
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$pyiDist = Join-Path $root "dist\pyinstaller"
$pyiWork = Join-Path $root "build\pyinstaller"
$packageRoot = Join-Path $root "dist\windows-package"
$frontendDir = Join-Path $root "frontend"

function Run-Step {
  param(
    [string]$Workdir,
    [string[]]$CommandArgs
  )

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

if (-not $NoClean) {
  Remove-Item $pyiDist -Recurse -Force -ErrorAction SilentlyContinue
  Remove-Item $pyiWork -Recurse -Force -ErrorAction SilentlyContinue
  Remove-Item $packageRoot -Recurse -Force -ErrorAction SilentlyContinue
}

Run-Step $root @($PythonExe, "-m", "pip", "install", "pyinstaller")
Run-Step $frontendDir @("npm", "run", "build")

$backendArgs = @(
  $PythonExe, "-m", "PyInstaller",
  "--noconfirm",
  "--clean",
  "--onedir",
  "--name", "GPUGovernanceBackend",
  "--distpath", $pyiDist,
  "--workpath", $pyiWork,
  "--specpath", $pyiWork,
  "--paths", (Join-Path $root "backend"),
  "--add-data", ((Join-Path $root "frontend\dist") + ";frontend\dist"),
  "--collect-all", "uvicorn",
  "--collect-all", "websockets",
  "--collect-all", "numpy",
  (Join-Path $root "desktop\backend_entry.py")
)

$agentArgs = @(
  $PythonExe, "-m", "PyInstaller",
  "--noconfirm",
  "--clean",
  "--onedir",
  "--name", "GPUServerAgent",
  "--distpath", $pyiDist,
  "--workpath", $pyiWork,
  "--specpath", $pyiWork,
  "--paths", (Join-Path $root "server-agent"),
  (Join-Path $root "server-agent\main.py")
)

$launcherArgs = @(
  $PythonExe, "-m", "PyInstaller",
  "--noconfirm",
  "--clean",
  "--onedir",
  "--windowed",
  "--name", "GPUGovernanceWorkbench",
  "--distpath", $pyiDist,
  "--workpath", $pyiWork,
  "--specpath", $pyiWork,
  (Join-Path $root "desktop\launcher.py")
)

Run-Step $root $backendArgs
Run-Step $root $agentArgs
Run-Step $root $launcherArgs

New-Item -ItemType Directory -Force -Path (Join-Path $packageRoot "app\backend") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $packageRoot "app\agent") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $packageRoot "app\launcher") | Out-Null

Copy-Item -Path (Join-Path $pyiDist "GPUGovernanceBackend\*") -Destination (Join-Path $packageRoot "app\backend") -Recurse -Force
Copy-Item -Path (Join-Path $pyiDist "GPUServerAgent\*") -Destination (Join-Path $packageRoot "app\agent") -Recurse -Force
Copy-Item -Path (Join-Path $pyiDist "GPUGovernanceWorkbench\*") -Destination (Join-Path $packageRoot "app\launcher") -Recurse -Force
Copy-Item -Path (Join-Path $root "backend\.env.example") -Destination (Join-Path $packageRoot "app\backend\.env.example") -Force

Copy-Item -Path (Join-Path $root "scripts\windows\install.ps1") -Destination (Join-Path $packageRoot "install.ps1") -Force
Copy-Item -Path (Join-Path $root "scripts\windows\install.bat") -Destination (Join-Path $packageRoot "install.bat") -Force
Copy-Item -Path (Join-Path $root "scripts\windows\uninstall.ps1") -Destination (Join-Path $packageRoot "uninstall.ps1") -Force
Copy-Item -Path (Join-Path $root "README.md") -Destination (Join-Path $packageRoot "README.md") -Force

Write-Host "Windows package ready: $packageRoot"
Write-Host "Run install.bat inside that folder to install."

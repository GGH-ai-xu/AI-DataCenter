param(
  [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$desktopShellDir = Join-Path $root "desktop-shell"

Write-Host "Step 1/2: build backend and agent runtime..."
powershell -ExecutionPolicy Bypass -File (Join-Path $root "scripts\build-windows.ps1") -PythonExe $PythonExe
if ($LASTEXITCODE -ne 0) {
  throw "Runtime build failed."
}

Write-Host "Step 2/2: build Electron desktop installer..."
Push-Location $desktopShellDir
try {
  npm install
  if ($LASTEXITCODE -ne 0) {
    throw "npm install failed."
  }

  npm run dist
  if ($LASTEXITCODE -ne 0) {
    throw "Electron dist failed."
  }
} finally {
  Pop-Location
}

Write-Host "Desktop installer ready under dist/electron"

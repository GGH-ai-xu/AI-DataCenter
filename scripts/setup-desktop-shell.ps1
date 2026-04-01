param()

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$desktopShellDir = Join-Path $root "desktop-shell"
$defaultElectronMirror = "https://npmmirror.com/mirrors/electron/"

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

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  throw "npm not found. Please install Node.js first."
}

if (-not $env:ELECTRON_MIRROR) {
  $env:ELECTRON_MIRROR = $defaultElectronMirror
}

Write-Host "Electron binary mirror: $($env:ELECTRON_MIRROR)"
Run-Step $desktopShellDir @("npm", "ci", "--include=dev")
Write-Host "Desktop shell dependencies installed."

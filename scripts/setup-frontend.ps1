param()

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
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

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  throw "npm not found. Please install Node.js first."
}

Run-Step $frontendDir @("npm", "ci")
Write-Host "Frontend dependencies installed."

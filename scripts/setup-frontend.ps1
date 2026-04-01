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

function Get-RolldownBindingPackage {
  $runtime = [System.Runtime.InteropServices.RuntimeInformation]
  $arch = $runtime::ProcessArchitecture.ToString().ToLowerInvariant()

  if ($runtime::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::Windows) -and $arch -eq "x64") {
    return "@rolldown/binding-win32-x64-msvc@1.0.0-rc.11"
  }
  if ($runtime::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::Linux) -and $arch -eq "x64") {
    return "@rolldown/binding-linux-x64-gnu@1.0.0-rc.11"
  }

  return $null
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  throw "npm not found. Please install Node.js first."
}

Run-Step $frontendDir @("npm", "ci", "--include=optional")
$rolldownBinding = Get-RolldownBindingPackage
if ($rolldownBinding) {
  Run-Step $frontendDir @("npm", "install", "--no-save", $rolldownBinding)
}
Write-Host "Frontend dependencies installed."

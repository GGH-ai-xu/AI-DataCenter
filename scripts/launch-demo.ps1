param()

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$entry = Join-Path $scriptDir "start-dev.ps1"

if (-not (Test-Path $entry)) {
  throw "start-dev.ps1 not found: $entry"
}

Write-Host "Legacy launch-demo entry detected. Redirecting to scripts/start-dev.ps1..."
& $entry

param(
  [string]$PythonVersion = "3.10",
  [switch]$Recreate
)

$ErrorActionPreference = "Stop"

. "$PSScriptRoot\repo-python-process-cleanup.ps1"

$root = Split-Path -Parent $PSScriptRoot
$venvDir = Join-Path $root ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"

function Assert-VenvUnlocked {
  param(
    [string]$RepoRoot,
    [string]$RepoVenvDir
  )

  $lockingProcesses = @(Get-RepoPythonProcesses -RepoRoot $RepoRoot -RepoVenvDir $RepoVenvDir)
  if ($lockingProcesses.Count -eq 0) {
    return
  }

  $details = $lockingProcesses | ForEach-Object {
    "PID $($_.ProcessId): $($_.ExecutablePath) | $($_.CommandLine)"
  }
  throw "Repository virtual environment is in use by running Python processes. Stop start-dev.bat, backend, agent, tests, and any shell using .venv, then rerun install-deps.bat.`n$($details -join "`n")"
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  throw "uv not found. Please install uv first."
}

Stop-RepoVenvPythonProcesses -RepoRoot $root -RepoVenvDir $venvDir | Out-Null
Assert-VenvUnlocked -RepoRoot $root -RepoVenvDir $venvDir

if ($Recreate -and (Test-Path $venvDir)) {
  Remove-Item $venvDir -Recurse -Force
}

if (-not (Test-Path $venvPython)) {
  uv venv $venvDir --python $PythonVersion
  if ($LASTEXITCODE -ne 0) {
    throw "uv venv failed."
  }
}

uv pip install --python $venvPython `
  -r (Join-Path $root "backend\requirements.txt") `
  -r (Join-Path $root "server-agent\requirements.txt")
if ($LASTEXITCODE -ne 0) {
  throw "uv pip install failed."
}

Write-Host "uv virtual environment ready: $venvPython"
& $venvPython --version

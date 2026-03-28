param(
  [string]$PythonVersion = "3.10",
  [switch]$Recreate
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$venvDir = Join-Path $root ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  throw "uv not found. Please install uv first."
}

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
  -r (Join-Path $root "server-agent\requirements.txt") `
  pyinstaller
if ($LASTEXITCODE -ne 0) {
  throw "uv pip install failed."
}

Write-Host "uv virtual environment ready: $venvPython"
& $venvPython --version

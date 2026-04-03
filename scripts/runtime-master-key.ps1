Set-StrictMode -Version Latest

function Get-RepoRuntimeMasterKeyPath {
  param([string]$RepoRoot)

  return Join-Path $RepoRoot "runtime\.gpu-gov-master-key"
}

function New-RuntimeMasterKey {
  $bytes = New-Object byte[] 32
  $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
  try {
    $generator.GetBytes($bytes)
  } finally {
    $generator.Dispose()
  }
  return [Convert]::ToBase64String($bytes)
}

function Ensure-RepoRuntimeMasterKey {
  param([string]$RepoRoot)

  $existingKey = [string]$env:GPU_GOV_MASTER_KEY
  if (-not [string]::IsNullOrWhiteSpace($existingKey)) {
    return $existingKey.Trim()
  }

  $keyPath = Get-RepoRuntimeMasterKeyPath -RepoRoot $RepoRoot
  $runtimeDir = Split-Path -Parent $keyPath
  New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null

  if (Test-Path $keyPath) {
    $storedKey = (Get-Content -Path $keyPath -Raw -Encoding UTF8).Trim()
    if (-not [string]::IsNullOrWhiteSpace($storedKey)) {
      return $storedKey
    }
  }

  $generatedKey = New-RuntimeMasterKey
  Set-Content -Path $keyPath -Value $generatedKey -Encoding UTF8 -NoNewline
  return $generatedKey
}

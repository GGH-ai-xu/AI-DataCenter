$script:ManagedServiceStatePath = $null

function Get-ManagedServiceStatePath {
  param([string]$RepoRoot)

  return Join-Path $RepoRoot "runtime\start-dev-managed-services.json"
}

function Initialize-ManagedServiceState {
  param([string]$RepoRoot)

  $script:ManagedServiceStatePath = Get-ManagedServiceStatePath -RepoRoot $RepoRoot
}

function Read-ManagedServiceState {
  param([string]$StatePath = $script:ManagedServiceStatePath)

  if ([string]::IsNullOrWhiteSpace($StatePath) -or -not (Test-Path $StatePath)) {
    return @()
  }

  $content = Get-Content -Path $StatePath -Raw -Encoding UTF8
  if ([string]::IsNullOrWhiteSpace($content)) {
    return @()
  }

  $state = $content | ConvertFrom-Json
  if ($state -is [System.Array]) {
    return @($state)
  }

  return @($state)
}

function Write-ManagedServiceState {
  param(
    [object[]]$Entries,
    [string]$StatePath = $script:ManagedServiceStatePath
  )

  $runtimeDir = Split-Path -Parent $StatePath
  if (-not (Test-Path $runtimeDir)) {
    New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
  }

  $json = @($Entries) | ConvertTo-Json -Depth 4
  Set-Content -Path $StatePath -Value $json -Encoding UTF8
}

function Remove-ManagedServiceStateFile {
  param([string]$StatePath = $script:ManagedServiceStatePath)

  if (-not [string]::IsNullOrWhiteSpace($StatePath) -and (Test-Path $StatePath)) {
    Remove-Item -Path $StatePath -Force
  }
}

function New-ManagedServiceStateEntry {
  param(
    [string]$ServiceName,
    [System.Diagnostics.Process]$Process,
    [string]$ExecutablePath,
    [string[]]$Signature
  )

  return [PSCustomObject]@{
    ServiceName = $ServiceName
    ProcessId = $Process.Id
    StartTime = $Process.StartTime.ToUniversalTime().ToString("o")
    ExecutablePath = $ExecutablePath
    Signature = @($Signature)
  }
}

function Save-ManagedServiceState {
  param(
    [string]$ServiceName,
    [System.Diagnostics.Process]$Process,
    [string]$ExecutablePath,
    [string[]]$Signature,
    [string]$StatePath = $script:ManagedServiceStatePath
  )

  $entries = @(Read-ManagedServiceState -StatePath $StatePath | Where-Object {
      $_.ServiceName -ne $ServiceName
    })
  $entries += New-ManagedServiceStateEntry `
    -ServiceName $ServiceName `
    -Process $Process `
    -ExecutablePath $ExecutablePath `
    -Signature $Signature

  Write-ManagedServiceState -Entries $entries -StatePath $StatePath
}

function Convert-ManagedServiceCimCreationDateToIsoString {
  param([string]$CreationDate)

  if ([string]::IsNullOrWhiteSpace($CreationDate)) {
    return $null
  }

  try {
    return [System.Management.ManagementDateTimeConverter]::ToDateTime($CreationDate).ToUniversalTime().ToString("o")
  } catch {
    return $null
  }
}

function Get-ManagedServiceStartTimeIsoString {
  param(
    $RuntimeProcess,
    $CimProcess
  )

  if ($null -ne $RuntimeProcess) {
    try {
      $runtimeStartTime = $RuntimeProcess.StartTime
      if ($null -ne $runtimeStartTime) {
        return $runtimeStartTime.ToUniversalTime().ToString("o")
      }
    } catch {
    }
  }

  if ($null -ne $CimProcess) {
    return Convert-ManagedServiceCimCreationDateToIsoString -CreationDate ([string]$CimProcess.CreationDate)
  }

  return $null
}

function Get-ManagedServiceProcessSnapshot {
  param([int]$ProcessId)

  $cimProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId"
  if ($null -eq $cimProcess) {
    return $null
  }

  $runtimeProcess = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
  return [PSCustomObject]@{
    CimProcess = $cimProcess
    RuntimeProcess = $runtimeProcess
  }
}

function Get-LiveManagedServiceDefinitions {
  param([string]$RepoRoot)

  $pythonExecutable = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot ".venv\Scripts\python.exe"))
  return @(
    [PSCustomObject]@{
      ServiceName = "Agent"
      ExecutablePath = $pythonExecutable
      Signature = @(".\main.py")
    },
    [PSCustomObject]@{
      ServiceName = "Backend"
      ExecutablePath = $pythonExecutable
      Signature = @("-m", "uvicorn", "app.main:app")
    }
  )
}

function Test-LiveManagedServiceMatch {
  param(
    [pscustomobject]$Definition,
    [pscustomobject]$Process
  )

  $actualPath = [string]$Process.ExecutablePath
  if ($actualPath -ine [string]$Definition.ExecutablePath) {
    return $false
  }

  $commandLine = [string]$Process.CommandLine
  foreach ($token in @($Definition.Signature)) {
    if ($commandLine.IndexOf([string]$token, [System.StringComparison]::OrdinalIgnoreCase) -lt 0) {
      return $false
    }
  }

  return $true
}

function New-LiveManagedServiceEntry {
  param(
    [pscustomobject]$Definition,
    [pscustomobject]$Process
  )

  $startTime = Get-ManagedServiceStartTimeIsoString -RuntimeProcess $null -CimProcess $Process
  if ([string]::IsNullOrWhiteSpace($startTime)) {
    return $null
  }

  return [PSCustomObject]@{
    ServiceName = $Definition.ServiceName
    ProcessId = [int]$Process.ProcessId
    StartTime = $startTime
    ExecutablePath = $Definition.ExecutablePath
    Signature = @($Definition.Signature)
  }
}

function Get-LiveManagedServiceEntries {
  param([string]$RepoRoot)

  $definitions = @(Get-LiveManagedServiceDefinitions -RepoRoot $RepoRoot)
  $processes = @(Get-CimInstance Win32_Process -Filter "Name = 'python.exe'")
  $entries = @()

  foreach ($definition in $definitions) {
    foreach ($process in $processes) {
      if (-not (Test-LiveManagedServiceMatch -Definition $definition -Process $process)) {
        continue
      }
      $entry = New-LiveManagedServiceEntry -Definition $definition -Process $process
      if ($null -ne $entry) {
        $entries += $entry
      }
    }
  }

  return $entries
}

function Merge-ManagedServiceEntries {
  param(
    [object[]]$SavedEntries,
    [object[]]$LiveEntries
  )

  $entriesByProcessId = @{}
  foreach ($entry in @($SavedEntries) + @($LiveEntries)) {
    $entriesByProcessId["$($entry.ProcessId)"] = $entry
  }

  return @($entriesByProcessId.Values)
}

function Test-RepositoryManagedStartDevProcess {
  param(
    [pscustomobject]$Entry,
    [pscustomobject]$Snapshot
  )

  if ($null -eq $Entry -or $null -eq $Snapshot) {
    return $false
  }

  if ($null -eq $Snapshot.CimProcess) {
    return $false
  }

  $actualStartTime = Get-ManagedServiceStartTimeIsoString `
    -RuntimeProcess $Snapshot.RuntimeProcess `
    -CimProcess $Snapshot.CimProcess
  if ([string]::IsNullOrWhiteSpace($actualStartTime)) {
    return $false
  }

  if ($actualStartTime -ne [string]$Entry.StartTime) {
    return $false
  }

  $expectedPath = [string]$Entry.ExecutablePath
  $actualPath = [string]$Snapshot.CimProcess.ExecutablePath
  if ($actualPath -ine $expectedPath) {
    return $false
  }

  $commandLine = [string]$Snapshot.CimProcess.CommandLine
  foreach ($token in @($Entry.Signature)) {
    if ([string]::IsNullOrWhiteSpace([string]$token)) {
      continue
    }
    if ($commandLine.IndexOf([string]$token, [System.StringComparison]::OrdinalIgnoreCase) -lt 0) {
      return $false
    }
  }

  return $true
}

function Stop-StaleManagedService {
  param([pscustomobject]$Entry)

  $ProcessId = [int]$Entry.ProcessId
  Write-ServiceLog -ServiceName "Launcher" -Message "Stopping stale Repository-managed start-dev process: $($Entry.ServiceName) (PID $ProcessId)"
  & taskkill /PID $ProcessId /T /F *> $null
}

function Clear-StaleManagedServices {
  param([string]$RepoRoot)

  Initialize-ManagedServiceState -RepoRoot $RepoRoot
  $entries = @(Merge-ManagedServiceEntries `
    -SavedEntries @(Read-ManagedServiceState) `
    -LiveEntries @(Get-LiveManagedServiceEntries -RepoRoot $RepoRoot))
  if ($entries.Count -eq 0) {
    return
  }

  foreach ($entry in $entries) {
    $snapshot = Get-ManagedServiceProcessSnapshot -ProcessId ([int]$entry.ProcessId)
    if (-not (Test-RepositoryManagedStartDevProcess -Entry $entry -Snapshot $snapshot)) {
      continue
    }
    Stop-StaleManagedService -Entry $entry
  }

  Remove-ManagedServiceStateFile
}

function Contains-IgnoreCase {
  param(
    [string]$Text,
    [string]$Needle
  )

  if ([string]::IsNullOrWhiteSpace($Text)) {
    return $false
  }

  return $Text.IndexOf($Needle, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
}

function Get-RepoPythonProcesses {
  param(
    [string]$RepoRoot,
    [string]$RepoVenvDir
  )

  $normalizedRoot = [System.IO.Path]::GetFullPath($RepoRoot)
  $normalizedVenv = [System.IO.Path]::GetFullPath($RepoVenvDir)
  $processes = Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'"
  $matches = @()

  foreach ($process in $processes) {
    $executablePath = [string]$process.ExecutablePath
    $commandLine = [string]$process.CommandLine
    $usesRepoVenv = Contains-IgnoreCase $executablePath $normalizedVenv
    $mentionsRepo = Contains-IgnoreCase $commandLine $normalizedRoot

    if (-not ($usesRepoVenv -or $mentionsRepo)) {
      continue
    }

    $matches += [PSCustomObject]@{
      ProcessId = [int]$process.ProcessId
      ExecutablePath = $executablePath
      CommandLine = $commandLine
    }
  }

  return $matches
}

function Get-RepoPythonProcessDefinitions {
  return @(
    [PSCustomObject]@{
      Category = "agent"
      Signature = @(".\main.py")
    },
    [PSCustomObject]@{
      Category = "backend"
      Signature = @("-m", "uvicorn", "app.main:app")
    },
    [PSCustomObject]@{
      Category = "unittest"
      Signature = @("-m unittest")
    },
    [PSCustomObject]@{
      Category = "pytest"
      Signature = @("-m pytest")
    }
  )
}

function Test-RepoPythonProcessDefinition {
  param(
    [pscustomobject]$Definition,
    [pscustomobject]$Process,
    [string]$RepoVenvDir
  )

  $normalizedVenv = [System.IO.Path]::GetFullPath($RepoVenvDir)
  if (-not (Contains-IgnoreCase ([string]$Process.ExecutablePath) $normalizedVenv)) {
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

function Get-RepoManagedAndTestProcesses {
  param(
    [string]$RepoRoot,
    [string]$RepoVenvDir
  )

  $processes = @(Get-RepoPythonProcesses -RepoRoot $RepoRoot -RepoVenvDir $RepoVenvDir)
  $definitions = @(Get-RepoPythonProcessDefinitions)
  $matches = @()

  foreach ($process in $processes) {
    foreach ($definition in $definitions) {
      if (-not (Test-RepoPythonProcessDefinition -Definition $definition -Process $process -RepoVenvDir $RepoVenvDir)) {
        continue
      }

      $matches += [PSCustomObject]@{
        ProcessId = $process.ProcessId
        ExecutablePath = $process.ExecutablePath
        CommandLine = $process.CommandLine
        Category = $definition.Category
      }
      break
    }
  }

  return $matches
}

function Stop-RepoVenvPythonProcesses {
  param(
    [string]$RepoRoot,
    [string]$RepoVenvDir
  )

  $matches = @(Get-RepoManagedAndTestProcesses -RepoRoot $RepoRoot -RepoVenvDir $RepoVenvDir)
  foreach ($match in $matches) {
    $ProcessId = [int]$match.ProcessId
    Write-Host "Stopping repository Python process [$($match.Category)] PID $ProcessId"
    & taskkill /PID $ProcessId /T /F *> $null
  }

  if ($matches.Count -gt 0) {
    Start-Sleep -Milliseconds 500
  }

  return $matches.Count
}

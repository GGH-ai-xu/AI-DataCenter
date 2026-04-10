Set-StrictMode -Version Latest

function Get-OptionalLocalNeo4jBootstrapLines {
  param([string]$Text)

  if ([string]::IsNullOrWhiteSpace($Text)) {
    return @()
  }

  return @(
    $Text -split "\r?\n" | Where-Object {
      -not [string]::IsNullOrWhiteSpace($_)
    }
  )
}

function Invoke-OptionalLocalNeo4jBootstrap {
  param(
    [string]$BootstrapScript,
    [string]$ServiceName = "Neo4j",
    [scriptblock]$WriteLog
  )

  if (-not $WriteLog) {
    throw "Invoke-OptionalLocalNeo4jBootstrap requires a WriteLog script block."
  }

  if (-not (Test-Path $BootstrapScript)) {
    & $WriteLog $ServiceName "Local Neo4j bootstrap script not found: $BootstrapScript"
    return $false
  }

  $powershell = Get-Command "powershell.exe" -ErrorAction SilentlyContinue |
    Select-Object -First 1
  if (-not $powershell) {
    & $WriteLog $ServiceName "powershell.exe not found; graph workspace may remain offline."
    return $false
  }

  $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
  $startInfo.FileName = if ($powershell.Path) { $powershell.Path } else { $powershell.Source }
  $startInfo.Arguments = "-ExecutionPolicy Bypass -File `"$BootstrapScript`""
  $startInfo.UseShellExecute = $false
  $startInfo.RedirectStandardOutput = $true
  $startInfo.RedirectStandardError = $true
  $startInfo.CreateNoWindow = $true
  $startInfo.StandardOutputEncoding = [System.Text.Encoding]::UTF8
  $startInfo.StandardErrorEncoding = [System.Text.Encoding]::UTF8

  $process = [System.Diagnostics.Process]::new()
  $process.StartInfo = $startInfo

  try {
    [void]$process.Start()
    $stdout = $process.StandardOutput.ReadToEnd()
    $stderr = $process.StandardError.ReadToEnd()
    $process.WaitForExit()
    $exitCode = $process.ExitCode
  } catch {
    & $WriteLog $ServiceName ("Local Neo4j bootstrap invocation failed: " + $_.Exception.Message)
    return $false
  } finally {
    $process.Dispose()
  }

  foreach ($line in Get-OptionalLocalNeo4jBootstrapLines -Text $stdout) {
    & $WriteLog $ServiceName $line
  }
  foreach ($line in Get-OptionalLocalNeo4jBootstrapLines -Text $stderr) {
    & $WriteLog $ServiceName $line
  }

  if ($exitCode -eq 0) {
    return $true
  }

  & $WriteLog $ServiceName "Local Neo4j bootstrap failed; graph workspace may remain offline."
  return $false
}

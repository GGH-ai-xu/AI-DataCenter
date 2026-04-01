Set-StrictMode -Version Latest

$script:ManagedServiceProcesses = @()
$script:ProcessLogPumpRegistrations = @()
$script:ShutdownRegistrationComplete = $false
$script:ManagedServiceStopRequested = $false
$script:HttpReadyPollMilliseconds = 500
$script:EventSourcePrefix = "gpu-dev-launch"
$script:ConsoleCancelHandler = $null
$script:AnsiEscapePattern = [string][char]27 + '\[[0-9;?]*[ -/]*[@-~]'

function Resolve-CommandPath {
  param([string]$CommandName)

  $command = Get-Command $CommandName -ErrorAction SilentlyContinue | Select-Object -First 1
  if (-not $command) {
    return $null
  }

  if ($command.Path) {
    return $command.Path
  }

  return $command.Source
}

function Resolve-NpmCliPath {
  param([string]$NodePath)

  $nodeDir = Split-Path -Parent $NodePath
  $npmCliPath = Join-Path $nodeDir "node_modules\npm\bin\npm-cli.js"
  if (-not (Test-Path $npmCliPath)) {
    throw "npm-cli.js not found next to node executable: $npmCliPath"
  }

  return $npmCliPath
}

function Get-FreePort {
  $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
  $listener.Start()
  try {
    return $listener.LocalEndpoint.Port
  } finally {
    $listener.Stop()
  }
}

function Initialize-ConsoleEncoding {
  [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
  $OutputEncoding = [System.Text.Encoding]::UTF8
}

function Write-ServiceLog {
  param(
    [string]$ServiceName,
    [string]$Message
  )

  $timestamp = Get-Date -Format "HH:mm:ss"
  $normalizedMessage = Normalize-ServiceLogMessage -Message $Message
  Write-Host "$timestamp [$ServiceName] $normalizedMessage"
}

function Wait-HttpReady {
  param(
    [string]$Name,
    [string]$Url,
    [int]$Port,
    [string]$LaunchCommand,
    [int]$TimeoutSeconds = 45
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    try {
      Invoke-WebRequest -Uri $Url -TimeoutSec 2 -UseBasicParsing | Out-Null
      return
    } catch {
      Start-Sleep -Milliseconds $script:HttpReadyPollMilliseconds
    }
  }

  throw "$Name failed to become ready on port $Port. Launch command: $LaunchCommand"
}

function Format-ProcessArgument {
  param([string]$Value)

  if ($Value -notmatch '[\s"]') {
    return $Value
  }

  $escaped = $Value -replace '(\\*)"', '$1$1\"'
  $escaped = $escaped -replace '(\\+)$', '$1$1'
  return '"' + $escaped + '"'
}

function ConvertTo-ProcessArgumentString {
  param([string[]]$ArgumentList)

  return ($ArgumentList | ForEach-Object {
    Format-ProcessArgument -Value ([string]$_)
  }) -join " "
}

function Normalize-ServiceLogMessage {
  param([string]$Message)

  if ([string]::IsNullOrEmpty($Message)) {
    return ""
  }

  return [System.Text.RegularExpressions.Regex]::Replace(
    $Message,
    $script:AnsiEscapePattern,
    ''
  )
}

function New-ManagedProcessStartInfo {
  param(
    [string]$FilePath,
    [string[]]$ArgumentList,
    [string]$WorkingDirectory,
    [hashtable]$Environment
  )

  $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
  $startInfo.FileName = $FilePath
  $startInfo.WorkingDirectory = $WorkingDirectory
  $startInfo.UseShellExecute = $false
  $startInfo.RedirectStandardOutput = $true
  $startInfo.RedirectStandardError = $true
  $startInfo.CreateNoWindow = $true
  $startInfo.StandardOutputEncoding = [System.Text.Encoding]::UTF8
  $startInfo.StandardErrorEncoding = [System.Text.Encoding]::UTF8

  if ($ArgumentList.Count -gt 0) {
    $startInfo.Arguments = ConvertTo-ProcessArgumentString -ArgumentList $ArgumentList
  }

  foreach ($entry in $Environment.GetEnumerator()) {
    $startInfo.Environment[$entry.Key] = [string]$entry.Value
  }

  return $startInfo
}

function Start-ManagedServiceProcess {
  param(
    [string]$ServiceName,
    [string]$FilePath,
    [string[]]$ArgumentList,
    [string]$WorkingDirectory,
    [hashtable]$Environment = @{}
  )

  $startInfo = New-ManagedProcessStartInfo `
    -FilePath $FilePath `
    -ArgumentList $ArgumentList `
    -WorkingDirectory $WorkingDirectory `
    -Environment $Environment

  $process = [System.Diagnostics.Process]::new()
  $process.StartInfo = $startInfo
  $process.EnableRaisingEvents = $true
  [void]$process.Start()

  $script:ManagedServiceProcesses += [PSCustomObject]@{
    ServiceName = $ServiceName
    Process = $process
  }

  return $process
}

function New-ProcessEventRegistration {
  param(
    [System.Diagnostics.Process]$Process,
    [string]$ServiceName,
    [string]$EventName,
    [string]$EventSuffix,
    [scriptblock]$Action
  )

  $sourceIdentifier = "{0}.{1}.{2}.{3}" -f `
    $script:EventSourcePrefix, `
    $ServiceName.ToLowerInvariant(), `
    $EventSuffix, `
    [Guid]::NewGuid().ToString("N")

  $job = Register-ObjectEvent `
    -InputObject $Process `
    -EventName $EventName `
    -SourceIdentifier $sourceIdentifier `
    -Action $Action `
    -MessageData @{ ServiceName = $ServiceName }

  return [PSCustomObject]@{
    SourceIdentifier = $sourceIdentifier
    JobId = $job.Id
  }
}

function Register-ProcessLogPump {
  param(
    [string]$ServiceName,
    [System.Diagnostics.Process]$Process
  )

  $stdoutRegistration = New-ProcessEventRegistration `
    -Process $Process `
    -ServiceName $ServiceName `
    -EventName "OutputDataReceived" `
    -EventSuffix "stdout" `
    -Action {
      if ($EventArgs.Data) {
        Write-ServiceLog -ServiceName $Event.MessageData.ServiceName -Message $EventArgs.Data
      }
    }

  $stderrRegistration = New-ProcessEventRegistration `
    -Process $Process `
    -ServiceName $ServiceName `
    -EventName "ErrorDataReceived" `
    -EventSuffix "stderr" `
    -Action {
      if ($EventArgs.Data) {
        Write-ServiceLog -ServiceName $Event.MessageData.ServiceName -Message $EventArgs.Data
      }
    }

  $exitRegistration = New-ProcessEventRegistration `
    -Process $Process `
    -ServiceName $ServiceName `
    -EventName "Exited" `
    -EventSuffix "exit" `
    -Action {
      $exitCode = if ($Sender) { $Sender.ExitCode } else { "unknown" }
      Write-ServiceLog -ServiceName $Event.MessageData.ServiceName -Message "process exited with code $exitCode"
    }

  $script:ProcessLogPumpRegistrations += @(
    $stdoutRegistration,
    $stderrRegistration,
    $exitRegistration
  )

  $Process.BeginOutputReadLine()
  $Process.BeginErrorReadLine()
}

function Stop-ManagedProcessTree {
  param([System.Diagnostics.Process]$Process)

  if ($null -eq $Process -or $Process.HasExited) {
    return
  }

  & taskkill /PID $Process.Id /T /F *> $null
}

function Clear-ProcessLogPumpRegistrations {
  foreach ($registration in $script:ProcessLogPumpRegistrations) {
    Unregister-Event -SourceIdentifier $registration.SourceIdentifier -ErrorAction SilentlyContinue
    Remove-Job -Id $registration.JobId -Force -ErrorAction SilentlyContinue
  }

  $script:ProcessLogPumpRegistrations = @()
}

function Stop-ManagedServiceProcesses {
  if ($script:ManagedServiceStopRequested) {
    return
  }

  $script:ManagedServiceStopRequested = $true
  foreach ($entry in $script:ManagedServiceProcesses) {
    Stop-ManagedProcessTree -Process $entry.Process
    $entry.Process.Dispose()
  }

  Clear-ProcessLogPumpRegistrations
  if ($null -ne $script:ConsoleCancelHandler) {
    [Console].GetEvent("CancelKeyPress").RemoveEventHandler($null, $script:ConsoleCancelHandler)
    $script:ConsoleCancelHandler = $null
  }
  $script:ManagedServiceProcesses = @()
}

function Register-ManagedServiceShutdown {
  if ($script:ShutdownRegistrationComplete) {
    return
  }

  $null = Register-EngineEvent -SourceIdentifier "$($script:EventSourcePrefix).shutdown" -Action {
    Stop-ManagedServiceProcesses
  }

  $handler = [ConsoleCancelEventHandler]{
    param($sender, $eventArgs)

    $eventArgs.Cancel = $true
    Stop-ManagedServiceProcesses
    exit 0
  }

  [Console].GetEvent("CancelKeyPress").AddEventHandler($null, $handler)
  $script:ConsoleCancelHandler = $handler
  $script:ShutdownRegistrationComplete = $true
}

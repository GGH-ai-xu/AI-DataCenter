$script:AnsiEscapePattern = [string][char]27 + '\[[0-9;?]*[ -/]*[@-~]'
$script:ConsoleWriteLock = [System.Object]::new()

function Initialize-ConsoleEncoding {
  $utf8 = [System.Text.UTF8Encoding]::new($false)
  [Console]::InputEncoding = $utf8
  [Console]::OutputEncoding = $utf8
  $OutputEncoding = $utf8
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

function Write-ConsoleLine {
  param([string]$Message)

  [System.Threading.Monitor]::Enter($script:ConsoleWriteLock)
  try {
    [Console]::Out.WriteLine($Message)
    [Console]::Out.Flush()
  } finally {
    [System.Threading.Monitor]::Exit($script:ConsoleWriteLock)
  }
}

function Write-ServiceLog {
  param(
    [string]$ServiceName,
    [string]$Message
  )

  $timestamp = Get-Date -Format "HH:mm:ss"
  $normalizedMessage = Normalize-ServiceLogMessage -Message $Message
  Write-ConsoleLine -Message "$timestamp [$ServiceName] $normalizedMessage"
}

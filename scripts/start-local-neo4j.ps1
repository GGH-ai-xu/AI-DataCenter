$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\local-neo4j-config.ps1"

$config = Get-LocalNeo4jConfig

if ($config.BoltHost -notin @('127.0.0.1', 'localhost', '::1')) {
  Write-Output "Skip local Neo4j bootstrap: NEO4J_URI points to $($config.BoltHost)."
  exit 0
}

if (-not (Test-Path $config.Neo4jHome)) {
  throw "Local Neo4j home not found: $($config.Neo4jHome)"
}

if (-not (Test-Path $config.Neo4jBat)) {
  throw "neo4j.bat not found: $($config.Neo4jBat)"
}

if (-not (Test-Path $config.JavaHome)) {
  throw "Local Java home not found: $($config.JavaHome)"
}

if (Test-LocalNeo4jListening -Port $config.BoltPort) {
  Write-Output "Local Neo4j already listening on $($config.BoltUri)."
  exit 0
}

$argString = "/c set ""JAVA_HOME=$($config.JavaHome)"" && set ""PATH=$($config.JavaHome)\bin;%PATH%"" && ""$($config.Neo4jBat)"" console"
$process = Start-Process -FilePath 'cmd.exe' -ArgumentList $argString -WindowStyle Hidden -PassThru

$deadline = (Get-Date).AddSeconds(45)
while ((Get-Date) -lt $deadline) {
  if (Test-LocalNeo4jListening -Port $config.BoltPort) {
    Write-Output "Local Neo4j ready on $($config.BoltUri) (bootstrap PID $($process.Id))."
    exit 0
  }
  Start-Sleep -Milliseconds 500
}

throw "Local Neo4j failed to become ready on $($config.BoltUri) within 45 seconds."

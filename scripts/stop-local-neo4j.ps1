$ErrorActionPreference = 'SilentlyContinue'
. "$PSScriptRoot\local-neo4j-config.ps1"

$config = Get-LocalNeo4jConfig
$env:JAVA_HOME = $config.JavaHome
$env:Path = "$($config.JavaHome)\bin;$env:Path"

$neo4jProcesses = Get-CimInstance Win32_Process | Where-Object {
  $_.Name -eq 'java.exe' `
    -and $_.CommandLine -like "*$($config.Neo4jHome)*" `
    -and $_.CommandLine -like '*org.neo4j.server.CommunityEntryPoint*'
}

if ($neo4jProcesses) {
  foreach ($process in $neo4jProcesses) {
    Stop-Process -Id $process.ProcessId -Force
  }

  $deadline = (Get-Date).AddSeconds(15)
  while ((Get-Date) -lt $deadline) {
    if (-not (Test-LocalNeo4jListening -Port $config.BoltPort)) {
      Write-Output ('Stopped Neo4j process IDs: ' + (($neo4jProcesses | ForEach-Object { $_.ProcessId }) -join ', '))
      return
    }
    Start-Sleep -Milliseconds 500
  }

  throw "Neo4j process termination was requested, but port $($config.BoltPort) is still listening."
}

& $config.Neo4jBat stop

$deadline = (Get-Date).AddSeconds(15)
while ((Get-Date) -lt $deadline) {
  if (-not (Test-LocalNeo4jListening -Port $config.BoltPort)) {
    Write-Output "Neo4j stop command submitted and port $($config.BoltPort) is closed."
    return
  }
  Start-Sleep -Milliseconds 500
}

throw "Neo4j stop command was submitted, but port $($config.BoltPort) is still listening."

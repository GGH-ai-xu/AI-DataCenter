function Get-RepoRoot {
  return Split-Path -Parent $PSScriptRoot
}

function Get-ConfigFileValue {
  param(
    [string]$Name,
    [string[]]$Paths
  )

  foreach ($path in $Paths) {
    if (-not (Test-Path $path)) {
      continue
    }
    foreach ($line in Get-Content $path) {
      if ($line -match '^\s*#' -or $line -match '^\s*$') {
        continue
      }
      if ($line -match "^\s*${Name}\s*=\s*(.+?)\s*$") {
        return $matches[1].Trim()
      }
    }
  }

  return ""
}

function Get-LocalNeo4jConfig {
  $repoRoot = Get-RepoRoot
  $configPaths = @(
    (Join-Path $repoRoot 'backend\.env'),
    (Join-Path $repoRoot '.env')
  )

  $boltUri = [Environment]::GetEnvironmentVariable('NEO4J_URI')
  if ([string]::IsNullOrWhiteSpace($boltUri)) {
    $boltUri = Get-ConfigFileValue -Name 'NEO4J_URI' -Paths $configPaths
  }
  if ([string]::IsNullOrWhiteSpace($boltUri)) {
    $boltUri = 'bolt://127.0.0.1:7687'
  }

  $parsedUri = [uri]$boltUri
  $boltHost = ([string]$parsedUri.Host).Trim().ToLowerInvariant()
  $boltPort = if ($parsedUri.Port -gt 0) { $parsedUri.Port } else { 7687 }

  $httpPortText = [Environment]::GetEnvironmentVariable('LOCAL_NEO4J_HTTP_PORT')
  if ([string]::IsNullOrWhiteSpace($httpPortText)) {
    $httpPortText = Get-ConfigFileValue -Name 'LOCAL_NEO4J_HTTP_PORT' -Paths $configPaths
  }
  $httpPort = if ([string]::IsNullOrWhiteSpace($httpPortText)) { 7474 } else { [int]$httpPortText }

  $neo4jHome = [Environment]::GetEnvironmentVariable('LOCAL_NEO4J_HOME')
  if ([string]::IsNullOrWhiteSpace($neo4jHome)) {
    $neo4jHome = Get-ConfigFileValue -Name 'LOCAL_NEO4J_HOME' -Paths $configPaths
  }
  if ([string]::IsNullOrWhiteSpace($neo4jHome)) {
    $neo4jHome = 'C:\gpu-gov-local\neo4j-community-5.26.24'
  }

  $javaHome = [Environment]::GetEnvironmentVariable('LOCAL_NEO4J_JAVA_HOME')
  if ([string]::IsNullOrWhiteSpace($javaHome)) {
    $javaHome = Get-ConfigFileValue -Name 'LOCAL_NEO4J_JAVA_HOME' -Paths $configPaths
  }
  if ([string]::IsNullOrWhiteSpace($javaHome)) {
    $javaHome = 'C:\Program Files\Microsoft\jdk-17.0.18.8-hotspot'
  }

  [PSCustomObject]@{
    RepoRoot = $repoRoot
    BoltUri = $boltUri
    BoltHost = $boltHost
    BoltPort = $boltPort
    HttpPort = $httpPort
    Neo4jHome = $neo4jHome
    Neo4jBat = Join-Path $neo4jHome 'bin\neo4j.bat'
    JavaHome = $javaHome
  }
}

function Test-LocalNeo4jListening {
  param([int]$Port)

  $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -First 1
  return $null -ne $listener
}

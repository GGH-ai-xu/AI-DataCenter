$ErrorActionPreference = 'SilentlyContinue'

$installDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$desktopShortcut = Join-Path ([Environment]::GetFolderPath('Desktop')) 'GPU 共享治理平台.lnk'
$startMenuDir = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\GPU 共享治理平台'
$startMenuShortcut = Join-Path $startMenuDir 'GPU 共享治理平台.lnk'

Get-Process GPUGovernanceWorkbench, GPUGovernanceBackend, GPUServerAgent -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 1

Remove-Item $desktopShortcut -Force -ErrorAction SilentlyContinue
Remove-Item $startMenuShortcut -Force -ErrorAction SilentlyContinue
Remove-Item $startMenuDir -Force -Recurse -ErrorAction SilentlyContinue

Set-Location $env:TEMP
Start-Process -FilePath cmd.exe -ArgumentList "/c ping 127.0.0.1 -n 3 > nul && rmdir /s /q `"$installDir`"" -WindowStyle Hidden

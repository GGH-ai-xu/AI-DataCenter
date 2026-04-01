param(
  [int]$Size = 256
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$sourceSvg = Join-Path $repoRoot 'docs/logo/logo.svg'
$frontendPublic = Join-Path $repoRoot 'frontend/public'
$desktopBuild = Join-Path $repoRoot 'desktop-shell/build'
$pngPath = Join-Path $desktopBuild 'icon.png'
$icoPath = Join-Path $desktopBuild 'icon.ico'
$tempDir = Join-Path $env:TEMP 'ai-datacenter-logo-render'
$renderScript = Join-Path $tempDir 'render-logo.cjs'

New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
Copy-Item $sourceSvg (Join-Path $frontendPublic 'logo.svg') -Force
Copy-Item $sourceSvg (Join-Path $frontendPublic 'favicon.svg') -Force
Copy-Item $sourceSvg (Join-Path $desktopBuild 'logo.svg') -Force

@"
const fs = require('node:fs')
const { Resvg } = require('@resvg/resvg-js')
const toIco = require('to-ico')
async function main() {
  const [source, pngPath, icoPath, sizeArg] = process.argv.slice(2)
  const size = Number(sizeArg) || 256
  const png = new Resvg(fs.readFileSync(source), { fitTo: { mode: 'width', value: size } }).render().asPng()
  fs.writeFileSync(pngPath, png)
  fs.writeFileSync(icoPath, await toIco([png]))
}
main().catch((error) => { console.error(error); process.exit(1) })
"@ | Set-Content -Path $renderScript -Encoding UTF8

& cmd.exe /c "cd /d `"$tempDir`" && if not exist node_modules (npm init -y >nul && npm install --no-save @resvg/resvg-js to-ico >nul) && node render-logo.cjs `"$sourceSvg`" `"$pngPath`" `"$icoPath`" $Size"

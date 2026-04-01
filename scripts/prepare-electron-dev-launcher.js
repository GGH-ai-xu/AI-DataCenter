const fs = require('node:fs')
const path = require('node:path')

const repoRoot = path.resolve(__dirname, '..')
const desktopShellDir = path.join(repoRoot, 'desktop-shell')
const electronDistDir = path.join(
  desktopShellDir,
  'node_modules',
  'electron',
  'dist',
)
const iconPath = path.join(desktopShellDir, 'build', 'icon.ico')
const runtimeDir = path.join(desktopShellDir, 'build', 'dev-runtime')
const launcherName = 'GPUGovernanceWorkbench.exe'
const launcherPath = path.join(runtimeDir, launcherName)
const metaPath = path.join(runtimeDir, '.launcher-meta.json')

function readJson(filePath) {
  if (!fs.existsSync(filePath)) {
    return {}
  }
  return JSON.parse(fs.readFileSync(filePath, 'utf8'))
}

function writeJson(filePath, value) {
  fs.writeFileSync(filePath, JSON.stringify(value, null, 2))
}

function requireModule(modulePath) {
  return require(modulePath)
}

function ensurePaths() {
  for (const filePath of [electronDistDir, iconPath]) {
    if (!fs.existsSync(filePath)) {
      throw new Error(`Missing required path: ${filePath}`)
    }
  }
  fs.mkdirSync(runtimeDir, { recursive: true })
}

function electronRuntimeVersion() {
  const pkgPath = path.join(
    desktopShellDir,
    'node_modules',
    'electron',
    'package.json',
  )
  return JSON.parse(fs.readFileSync(pkgPath, 'utf8')).version
}

function shouldSyncRuntime(meta) {
  if (!fs.existsSync(path.join(runtimeDir, 'electron.exe'))) {
    return true
  }
  return meta.electronVersion !== electronRuntimeVersion()
}

function syncRuntime() {
  fs.cpSync(electronDistDir, runtimeDir, { recursive: true, force: true })
}

function launcherNeedsRefresh(meta) {
  if (!fs.existsSync(launcherPath)) {
    return true
  }
  const iconStat = fs.statSync(iconPath)
  return meta.iconMtimeMs !== iconStat.mtimeMs
}

function replaceLauncherIcon() {
  const ResEdit = requireModule(
    path.join(desktopShellDir, 'node_modules', 'resedit'),
  )
  const exeBuffer = fs.readFileSync(launcherPath)
  const exe = ResEdit.NtExecutable.from(exeBuffer, { ignoreCert: true })
  const res = ResEdit.NtExecutableResource.from(exe)
  const groups = ResEdit.Resource.IconGroupEntry.fromEntries(res.entries)
  const groupId = groups[0]?.id || 1
  const lang = groups[0]?.lang || 1033
  const iconFile = ResEdit.Data.IconFile.from(fs.readFileSync(iconPath))

  ResEdit.Resource.IconGroupEntry.replaceIconsForResource(
    res.entries,
    groupId,
    lang,
    iconFile.icons.map((item) => item.data),
  )

  res.outputResource(exe)
  fs.writeFileSync(launcherPath, Buffer.from(exe.generate()))
}

function ensureLauncher(meta) {
  if (shouldSyncRuntime(meta)) {
    syncRuntime()
  }
  if (launcherNeedsRefresh(meta) || shouldSyncRuntime(meta)) {
    fs.copyFileSync(path.join(runtimeDir, 'electron.exe'), launcherPath)
    replaceLauncherIcon()
  }
}

function nextMeta() {
  return {
    electronVersion: electronRuntimeVersion(),
    iconMtimeMs: fs.statSync(iconPath).mtimeMs,
    launcherName,
  }
}

function main() {
  ensurePaths()
  const currentMeta = readJson(metaPath)
  ensureLauncher(currentMeta)
  const updatedMeta = nextMeta()
  writeJson(metaPath, updatedMeta)
  process.stdout.write(`${launcherPath}\n`)
}

main()

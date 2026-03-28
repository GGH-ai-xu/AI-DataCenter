const { app, BrowserWindow, clipboard, dialog, ipcMain, Menu, Tray, nativeImage, screen, shell } = require('electron')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const http = require('node:http')
const net = require('node:net')
const { spawn } = require('node:child_process')
const DESKTOP_PACKAGE = require('./package.json')

const APP_ID = 'com.gpu.governance.workbench'
const APP_TITLE = 'GPU 共享治理平台'
const APP_SLUG = 'GPU-Governance-Workbench'
const LOCAL_HOST = '127.0.0.1'
const DEFAULT_BACKEND_PORT = 8000
const DEFAULT_AGENT_PORT = 8001
const PORT_SCAN_LIMIT = 40
const AUTO_RESTART_LIMIT = 3
const AUTO_RESTART_DELAY_MS = 1500
const MAIN_WINDOW_SHOW_FALLBACK_MS = 2600
const WINDOW_TOPMOST_BOUNCE_MS = 220
const RELEASE_EXE_PATTERN = /^GPUGovernanceWorkbench-Setup-.*\.exe$/i
const AGENT_EXPORT_DIRNAME = 'GPU-Server-Agent'
const AGENT_START_SCRIPT_NAME = 'Start-Agent.bat'
const AGENT_README_NAME = 'README-REMOTE.txt'

let mainWindow = null
let splashWindow = null
let backendProcess = null
let agentProcess = null
let ownsBackend = false
let ownsAgent = false
let isQuitting = false
let allowWindowClose = false
let tray = null
let closeDialogOpen = false
let backendPort = DEFAULT_BACKEND_PORT
let agentPort = DEFAULT_AGENT_PORT
const managedServices = {
  backend: {
    key: 'backend',
    label: '治理后端',
    status: 'idle',
    detail: '等待启动',
    port: DEFAULT_BACKEND_PORT,
    managed: false,
    owned: false,
    restartAttempts: 0,
    launchSpec: null,
    recoveryPending: false,
    updatedAt: Date.now(),
  },
  agent: {
    key: 'agent',
    label: '本机采集代理',
    status: 'idle',
    detail: '等待启动',
    port: DEFAULT_AGENT_PORT,
    managed: false,
    owned: false,
    restartAttempts: 0,
    launchSpec: null,
    recoveryPending: false,
    updatedAt: Date.now(),
  },
}

function managedServicePort(key) {
  return key === 'backend' ? backendPort : agentPort
}

function managedServiceProcess(key) {
  return key === 'backend' ? backendProcess : agentProcess
}

function setManagedServiceProcess(key, child) {
  if (key === 'backend') {
    backendProcess = child
    return
  }
  agentProcess = child
}

function setManagedServiceOwned(key, owned) {
  if (key === 'backend') {
    ownsBackend = owned
  } else {
    ownsAgent = owned
  }
  managedServices[key].owned = owned
}

function managedServiceSnapshot(key) {
  const state = managedServices[key]
  return {
    key: state.key,
    label: state.label,
    status: state.status,
    detail: state.detail,
    port: state.port,
    managed: state.managed,
    owned: state.owned,
    restartAttempts: state.restartAttempts,
    updatedAt: state.updatedAt,
  }
}

function allManagedServiceSnapshots() {
  return {
    backend: managedServiceSnapshot('backend'),
    agent: managedServiceSnapshot('agent'),
  }
}

function emitManagedServiceState() {
  if (!mainWindow || mainWindow.isDestroyed()) {
    return
  }

  try {
    mainWindow.webContents.send('desktop-shell:service-state', {
      services: allManagedServiceSnapshots(),
    })
  } catch {}
}

function updateManagedServiceState(key, patch = {}) {
  const state = managedServices[key]
  Object.assign(state, patch, {
    port: patch.port ?? managedServicePort(key),
    updatedAt: Date.now(),
  })
  emitManagedServiceState()
}

function markManagedServiceExternal(key, label, detail) {
  updateManagedServiceState(key, {
    label,
    status: 'running',
    detail,
    managed: false,
    owned: false,
    restartAttempts: 0,
    launchSpec: null,
    recoveryPending: false,
  })
}

function managedServiceFailureDetail(label, code, signal) {
  return [
    `${label} 已停止。`,
    `退出码: ${code ?? '未知'}`,
    `信号: ${signal ?? '无'}`,
    `日志目录: ${logsRoot()}`,
  ].join('\n')
}

function parseGitHubRepository(rawUrl) {
  const normalized = String(rawUrl || '')
    .trim()
    .replace(/^git\+/, '')
    .replace(/\.git$/i, '')

  const httpsMatch = normalized.match(/^https?:\/\/github\.com\/([^/]+)\/([^/]+)$/i)
  if (httpsMatch) {
    return { owner: httpsMatch[1], repo: httpsMatch[2] }
  }

  const sshMatch = normalized.match(/^git@github\.com:([^/]+)\/([^/]+)$/i)
  if (sshMatch) {
    return { owner: sshMatch[1], repo: sshMatch[2] }
  }

  return null
}

const releaseRepository = parseGitHubRepository(DESKTOP_PACKAGE.repository?.url)
const releasesPageUrl = releaseRepository
  ? `https://github.com/${releaseRepository.owner}/${releaseRepository.repo}/releases`
  : ''

function currentAppVersion() {
  return app.getVersion() || DESKTOP_PACKAGE.version || '0.0.0'
}

function normalizeVersionTag(value) {
  return String(value || '')
    .trim()
    .replace(/^v/i, '')
    .split('-')[0]
}

function compareVersions(left, right) {
  const leftParts = normalizeVersionTag(left).split('.').map((item) => Number.parseInt(item, 10) || 0)
  const rightParts = normalizeVersionTag(right).split('.').map((item) => Number.parseInt(item, 10) || 0)
  const size = Math.max(leftParts.length, rightParts.length)

  for (let index = 0; index < size; index += 1) {
    const a = leftParts[index] || 0
    const b = rightParts[index] || 0
    if (a > b) return 1
    if (a < b) return -1
  }

  return 0
}

function releaseNotesPreview(body) {
  return String(body || '')
    .replace(/\r\n/g, '\n')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .slice(0, 4)
    .join(' ')
    .slice(0, 240)
}

async function fetchLatestRelease() {
  if (!releaseRepository) {
    throw new Error('未配置 GitHub Releases 发布源')
  }

  const response = await fetch(
    `https://api.github.com/repos/${releaseRepository.owner}/${releaseRepository.repo}/releases/latest`,
    {
      headers: {
        Accept: 'application/vnd.github+json',
        'User-Agent': `${APP_SLUG}/${currentAppVersion()}`,
      },
    },
  )

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error('GitHub Releases 还没有发布正式版本，请先在仓库创建一个 Release')
    }
    throw new Error(`GitHub Releases 请求失败 (${response.status})`)
  }

  const payload = await response.json()
  if (!payload || !payload.tag_name || !payload.html_url) {
    throw new Error('GitHub Releases 返回格式无效')
  }

  const currentVersion = normalizeVersionTag(currentAppVersion())
  const latestVersion = normalizeVersionTag(payload.tag_name)
  const assets = Array.isArray(payload.assets) ? payload.assets : []
  const preferredAsset = assets.find((asset) => RELEASE_EXE_PATTERN.test(asset.name || ''))
  const fallbackAsset = assets.find((asset) => /\.exe$/i.test(asset.name || ''))

  return {
    currentVersion,
    latestVersion,
    available: compareVersions(latestVersion, currentVersion) > 0,
    releaseName: payload.name || payload.tag_name,
    releaseUrl: payload.html_url,
    downloadUrl: preferredAsset?.browser_download_url || fallbackAsset?.browser_download_url || payload.html_url,
    publishedAt: payload.published_at || null,
    notes: releaseNotesPreview(payload.body),
  }
}

function installRoot() {
  if (app.isPackaged) {
    return process.resourcesPath
  }
  return path.resolve(__dirname, '..', 'dist', 'windows-package', 'app')
}

function shellAssetPath(...segments) {
  const base = app.isPackaged ? app.getAppPath() : __dirname
  return path.join(base, ...segments)
}

function runtimeRoot() {
  const configured = (process.env.GPU_GOV_HOME || '').trim()
  const root = configured
    ? configured
    : path.join(process.env.LOCALAPPDATA || path.join(os.homedir(), 'AppData', 'Local'), APP_SLUG)

  for (const name of ['logs', 'runtime', 'data']) {
    fs.mkdirSync(path.join(root, name), { recursive: true })
  }
  process.env.GPU_GOV_HOME = root
  return root
}

function logsRoot() {
  return path.join(runtimeRoot(), 'logs')
}

function connectionConfigPath() {
  return path.join(runtimeRoot(), 'runtime', 'connection.json')
}

function runtimeInfoSnapshot() {
  return {
    runtimeRoot: runtimeRoot(),
    logsRoot: logsRoot(),
    backendBaseUrl: backendBaseUrl(),
    agentBaseUrl: agentBaseUrl(),
    connectionMode: readConnectionMode(),
  }
}

function readConnectionMode() {
  try {
    const payload = JSON.parse(fs.readFileSync(connectionConfigPath(), 'utf-8'))
    return payload.mode === 'remote' ? 'remote' : 'local'
  } catch {
    return 'local'
  }
}

function resourcesPath(name, executable) {
  return path.join(installRoot(), name, executable)
}

function agentPackageSourcePath() {
  return path.join(installRoot(), 'agent')
}

function backendBaseUrl(port = backendPort) {
  return `http://${LOCAL_HOST}:${port}`
}

function backendHealthUrl(port = backendPort) {
  return `${backendBaseUrl(port)}/api/health`
}

function agentHealthUrl() {
  return `http://${LOCAL_HOST}:${agentPort}/api/health`
}

function agentBaseUrl(port = agentPort) {
  return `http://${LOCAL_HOST}:${port}`
}

function buildExportedAgentStartScript() {
  return [
    '@echo off',
    'setlocal',
    'cd /d "%~dp0"',
    `set "GPU_AGENT_HOST=0.0.0.0"`,
    `set "GPU_AGENT_PORT=${DEFAULT_AGENT_PORT}"`,
    'echo Starting GPU Server Agent...',
    `netsh advfirewall firewall add rule name="GPU Server Agent ${DEFAULT_AGENT_PORT}" dir=in action=allow protocol=TCP localport=${DEFAULT_AGENT_PORT} >nul 2>nul`,
    'start "" "%~dp0GPUServerAgent.exe"',
    'echo.',
    `echo Health check: http://127.0.0.1:${DEFAULT_AGENT_PORT}/api/health`,
    `echo If remote access still fails, allow TCP ${DEFAULT_AGENT_PORT} in Windows Firewall.`,
    'pause',
    '',
  ].join('\r\n')
}

function buildExportedAgentReadme() {
  return [
    'GPU Remote Agent Quick Start',
    '',
    `1. Double-click ${AGENT_START_SCRIPT_NAME}`,
    `2. On the remote host, open http://127.0.0.1:${DEFAULT_AGENT_PORT}/api/health`,
    `3. In GPU Governance Workbench, fill in http://<server-ip>:${DEFAULT_AGENT_PORT}`,
    '4. Click Test Connection, then Save and Switch',
    '',
    'Notes:',
    `- The agent listens on port ${DEFAULT_AGENT_PORT}`,
    '- If the health URL opens only on the remote host itself, check Windows Firewall',
    '- Keep the whole folder together when copying to the remote host',
    '',
  ].join('\r\n')
}

function timestampLabel() {
  const now = new Date()
  const pad = (value) => String(value).padStart(2, '0')
  return [
    now.getFullYear(),
    pad(now.getMonth() + 1),
    pad(now.getDate()),
    '-',
    pad(now.getHours()),
    pad(now.getMinutes()),
    pad(now.getSeconds()),
  ].join('')
}

async function canWriteDirectory(targetDir) {
  try {
    await fs.promises.mkdir(targetDir, { recursive: true })
    const probe = path.join(targetDir, `.write-test-${process.pid}-${Date.now()}.tmp`)
    await fs.promises.writeFile(probe, 'ok')
    await fs.promises.unlink(probe)
    return true
  } catch {
    return false
  }
}

async function resolveAgentExportTarget() {
  const candidates = [
    { label: 'desktop', baseDir: app.getPath('desktop') },
    { label: 'downloads', baseDir: app.getPath('downloads') },
    { label: 'runtime', baseDir: path.join(runtimeRoot(), 'exports') },
  ]

  for (const candidate of candidates) {
    if (!candidate.baseDir) {
      continue
    }
    const writable = await canWriteDirectory(candidate.baseDir)
    if (!writable) {
      continue
    }

    const preferred = path.join(candidate.baseDir, AGENT_EXPORT_DIRNAME)
    if (!fs.existsSync(preferred)) {
      return {
        destinationLabel: candidate.label,
        targetDir: preferred,
      }
    }

    return {
      destinationLabel: candidate.label,
      targetDir: path.join(candidate.baseDir, `${AGENT_EXPORT_DIRNAME}-${timestampLabel()}`),
    }
  }

  throw new Error('桌面、下载目录和运行目录都不可写，无法导出远端 Agent 包')
}

async function exportAgentPackage() {
  const sourceDir = agentPackageSourcePath()
  if (!fs.existsSync(sourceDir)) {
    throw new Error(`Missing agent runtime: ${sourceDir}`)
  }

  const { targetDir, destinationLabel } = await resolveAgentExportTarget()
  await fs.promises.cp(sourceDir, targetDir, { recursive: true, force: true })
  await fs.promises.writeFile(
    path.join(targetDir, AGENT_START_SCRIPT_NAME),
    buildExportedAgentStartScript(),
    'utf8',
  )
  await fs.promises.writeFile(
    path.join(targetDir, AGENT_README_NAME),
    buildExportedAgentReadme(),
    'utf8',
  )

  return {
    ok: true,
    targetDir,
    scriptName: AGENT_START_SCRIPT_NAME,
    readmeName: AGENT_README_NAME,
    healthUrl: `http://127.0.0.1:${DEFAULT_AGENT_PORT}/api/health`,
    destinationLabel,
  }
}

function buildWorkbenchUrl() {
  const url = new URL('/', backendBaseUrl())
  url.searchParams.set('desktopVersion', currentAppVersion())
  url.searchParams.set('boot', String(Date.now()))
  return url.toString()
}

function isPortFree(port, host = LOCAL_HOST) {
  return new Promise((resolve) => {
    const server = net.createServer()
    server.unref()
    server.once('error', () => resolve(false))
    server.listen(port, host, () => {
      server.close(() => resolve(true))
    })
  })
}

async function findAvailablePort(startPort, {
  host = LOCAL_HOST,
  attempts = PORT_SCAN_LIMIT,
  excluded = new Set(),
} = {}) {
  for (let offset = 0; offset < attempts; offset += 1) {
    const candidate = startPort + offset
    if (excluded.has(candidate)) {
      continue
    }

    if (await isPortFree(candidate, host)) {
      return candidate
    }
  }

  throw new Error(`未找到可用端口，起始端口 ${startPort}`)
}

function resolveWindowIcon() {
  const iconPath = shellAssetPath('build', 'icon.ico')
  if (!fs.existsSync(iconPath)) {
    return undefined
  }

  const image = nativeImage.createFromPath(iconPath)
  return image.isEmpty() ? undefined : image
}

function rectsIntersect(left, right) {
  return (
    left.x < right.x + right.width &&
    left.x + left.width > right.x &&
    left.y < right.y + right.height &&
    left.y + left.height > right.y
  )
}

function centerBoundsWithinArea(bounds, area) {
  const width = area.width < 980 ? area.width : Math.max(980, Math.min(bounds.width || 1520, area.width))
  const height = area.height < 700 ? area.height : Math.max(700, Math.min(bounds.height || 940, area.height))
  return {
    width,
    height,
    x: Math.round(area.x + (area.width - width) / 2),
    y: Math.round(area.y + (area.height - height) / 2),
  }
}

function clampBoundsToArea(bounds, area) {
  const width = Math.min(bounds.width || 1520, area.width)
  const height = Math.min(bounds.height || 940, area.height)
  return {
    width,
    height,
    x: Math.min(Math.max(bounds.x, area.x), area.x + area.width - width),
    y: Math.min(Math.max(bounds.y, area.y), area.y + area.height - height),
  }
}

function ensureWindowVisible(targetWindow, { forceCenter = false } = {}) {
  if (!targetWindow || targetWindow.isDestroyed()) {
    return
  }

  const displays = screen.getAllDisplays()
  if (!displays.length) {
    return
  }

  const bounds = targetWindow.getBounds()
  const visibleDisplay = displays.find((display) => rectsIntersect(bounds, display.workArea))
  const primaryArea = screen.getPrimaryDisplay().workArea
  const targetArea = (visibleDisplay || screen.getDisplayMatching(bounds) || screen.getPrimaryDisplay()).workArea || primaryArea
  const normalizedBounds = forceCenter || !visibleDisplay
    ? centerBoundsWithinArea(bounds, targetArea)
    : clampBoundsToArea(bounds, targetArea)

  const changed = ['x', 'y', 'width', 'height'].some((key) => normalizedBounds[key] !== bounds[key])
  if (changed) {
    targetWindow.setBounds(normalizedBounds)
  }
}

function presentWindow(targetWindow, { forceCenter = false } = {}) {
  if (!targetWindow || targetWindow.isDestroyed()) {
    return
  }

  if (targetWindow.isMinimized()) {
    targetWindow.restore()
  }

  ensureWindowVisible(targetWindow, { forceCenter })
  targetWindow.show()
  targetWindow.moveTop()
  targetWindow.focus()

  if (process.platform === 'win32') {
    targetWindow.setAlwaysOnTop(true, 'screen-saver')
    const timer = setTimeout(() => {
      if (targetWindow && !targetWindow.isDestroyed()) {
        targetWindow.setAlwaysOnTop(false)
      }
    }, WINDOW_TOPMOST_BOUNCE_MS)
    timer.unref?.()
  }
}

function showMainWindow() {
  if (!mainWindow || mainWindow.isDestroyed()) {
    return
  }

  presentWindow(mainWindow)
}

function ensureTray() {
  if (tray && !tray.isDestroyed()) {
    return tray
  }

  const icon = resolveWindowIcon()
  if (!icon) {
    return null
  }

  tray = new Tray(icon)
  tray.setToolTip(APP_TITLE)
  tray.setContextMenu(Menu.buildFromTemplate([
    {
      label: '显示主界面',
      click: () => showMainWindow(),
    },
    {
      label: '打开日志目录',
      click: () => {
        shell.openPath(logsRoot()).catch(() => {})
      },
    },
    { type: 'separator' },
    {
      label: '退出并关闭服务',
      click: () => {
        void requestAppShutdown()
      },
    },
  ]))

  tray.on('double-click', () => {
    showMainWindow()
  })

  tray.on('click', () => {
    showMainWindow()
  })

  return tray
}

function minimizeToTray() {
  if (!mainWindow || mainWindow.isDestroyed()) {
    return
  }

  ensureTray()
  mainWindow.hide()
}

function requestCloseConfirmation() {
  if (!mainWindow || mainWindow.isDestroyed()) {
    return false
  }

  if (mainWindow.webContents.isLoadingMainFrame()) {
    return false
  }

  try {
    showMainWindow()
    mainWindow.webContents.send('desktop-shell:close-requested', {
      title: '关闭桌面平台',
      message: '你想退出并关闭服务，还是最小化到后台继续运行？',
      detail: '最小化到后台会保留桌面程序与已托管的本机服务。退出并关闭服务会结束桌面程序以及它拉起的本机后端和 Agent。',
    })
    return true
  } catch {
    return false
  }
}

function handleMainWindowClose(event) {
  if (isQuitting || allowWindowClose) {
    return
  }

  event.preventDefault()

  if (closeDialogOpen) {
    showMainWindow()
    return
  }

  closeDialogOpen = true
  if (!requestCloseConfirmation()) {
    closeDialogOpen = false
    minimizeToTray()
  }
}

async function requestAppShutdown() {
  if (isQuitting) {
    return
  }

  isQuitting = true
  closeDialogOpen = false

  try {
    await stopManagedProcesses()
  } finally {
    allowWindowClose = true
    app.quit()
  }
}

ipcMain.handle('desktop-shell:get-app-info', async () => ({
  name: APP_TITLE,
  version: currentAppVersion(),
  updateSupported: Boolean(releaseRepository),
  releasesUrl: releasesPageUrl,
}))

ipcMain.handle('desktop-shell:get-service-state', async () => ({
  services: allManagedServiceSnapshots(),
}))

ipcMain.handle('desktop-shell:get-runtime-info', async () => runtimeInfoSnapshot())

ipcMain.handle('desktop-shell:check-for-updates', async () => {
  try {
    return {
      ok: true,
      ...await fetchLatestRelease(),
      updateSupported: Boolean(releaseRepository),
      releasesUrl: releasesPageUrl,
    }
  } catch (error) {
    return {
      ok: false,
      error: error instanceof Error ? error.message : String(error),
      currentVersion: currentAppVersion(),
      updateSupported: Boolean(releaseRepository),
      releasesUrl: releasesPageUrl,
    }
  }
})

ipcMain.handle('desktop-shell:open-external', async (_event, url) => {
  const target = String(url || '').trim()
  if (!/^https?:\/\//i.test(target)) {
    throw new Error('仅支持打开 http 或 https 链接')
  }
  await shell.openExternal(target)
  return { ok: true }
})

ipcMain.handle('desktop-shell:copy-text', async (_event, value) => {
  clipboard.writeText(String(value || ''))
  return { ok: true }
})

ipcMain.handle('desktop-shell:open-path', async (_event, value) => {
  const target = String(value || '').trim()
  if (!target) {
    throw new Error('路径不能为空')
  }
  if (!fs.existsSync(target)) {
    throw new Error(`路径不存在: ${target}`)
  }
  const errorMessage = await shell.openPath(target)
  if (errorMessage) {
    throw new Error(errorMessage)
  }
  return { ok: true }
})

ipcMain.handle('desktop-shell:export-agent-package', async () => {
  return exportAgentPackage()
})

ipcMain.handle('desktop-shell:resolve-close-request', async (_event, rawAction) => {
  const action = String(rawAction || 'cancel').trim()
  closeDialogOpen = false

  if (action === 'minimize') {
    minimizeToTray()
    return { ok: true, action }
  }

  if (action === 'quit') {
    void requestAppShutdown()
    return { ok: true, action }
  }

  showMainWindow()
  return { ok: true, action: 'cancel' }
})

ipcMain.handle('desktop-shell:restart-managed-services', async () => {
  if (isQuitting) {
    return {
      ok: false,
      error: '应用正在退出，无法重启本机服务',
      services: allManagedServiceSnapshots(),
      runtime: runtimeInfoSnapshot(),
    }
  }

  try {
    await stopManagedProcesses()
    backendPort = DEFAULT_BACKEND_PORT
    agentPort = DEFAULT_AGENT_PORT
    await ensureServices()

    if (mainWindow && !mainWindow.isDestroyed()) {
      await mainWindow.loadURL(buildWorkbenchUrl())
    }

    return {
      ok: true,
      services: allManagedServiceSnapshots(),
      runtime: runtimeInfoSnapshot(),
    }
  } catch (error) {
    return {
      ok: false,
      error: error instanceof Error ? error.message : String(error),
      services: allManagedServiceSnapshots(),
      runtime: runtimeInfoSnapshot(),
    }
  }
})

function emitBootStatus(message, progress) {
  if (!splashWindow || splashWindow.isDestroyed()) {
    return
  }
  splashWindow.webContents.send('boot-status', { message, progress })
}

function healthCheck(url) {
  return new Promise((resolve) => {
    const request = http.get(url, { timeout: 2500 }, (response) => {
      const ok = response.statusCode && response.statusCode >= 200 && response.statusCode < 300
      response.resume()
      resolve(Boolean(ok))
    })
    request.on('timeout', () => {
      request.destroy()
      resolve(false)
    })
    request.on('error', () => resolve(false))
  })
}

async function waitForHealth(url, timeoutMs) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    if (await healthCheck(url)) {
      return true
    }
    await new Promise((resolve) => setTimeout(resolve, 800))
  }
  return false
}

function showManagedServiceFailure(label, detail) {
  if (mainWindow && !mainWindow.isDestroyed()) {
    dialog.showMessageBox(mainWindow, {
      type: 'warning',
      title: APP_TITLE,
      buttons: ['打开日志目录', '继续使用'],
      defaultId: 1,
      cancelId: 1,
      message: `${label} 已停止`,
      detail,
    }).then((result) => {
      if (result.response === 0) {
        shell.openPath(logsRoot()).catch(() => {})
      }
    }).catch(() => {})
    return
  }

  emitBootStatus(`${label} 已停止，请检查日志`, 100)
}

function spawnManagedProcess(spec) {
  const {
    key,
    executable,
    logName,
    label,
    extraEnv = {},
  } = spec
  const logPath = path.join(logsRoot(), logName)
  const logStream = fs.createWriteStream(logPath, { flags: 'a' })
  const env = {
    ...process.env,
    GPU_GOV_HOME: runtimeRoot(),
    ...extraEnv,
  }

  const writeLog = (prefix, content) => {
    logStream.write(`[${new Date().toISOString()}] ${prefix}${content}\n`)
  }

  const child = spawn(executable, [], {
    cwd: path.dirname(executable),
    env,
    windowsHide: true,
    detached: false,
    stdio: ['ignore', 'pipe', 'pipe'],
  })

  writeLog('spawn ', `${executable} env=${JSON.stringify(extraEnv)}`)
  child.stdout?.pipe(logStream, { end: false })
  child.stderr?.pipe(logStream, { end: false })
  setManagedServiceProcess(key, child)

  child.once('error', (error) => {
    writeLog('error ', error instanceof Error ? error.stack || error.message : String(error))
    logStream.end()
    updateManagedServiceState(key, {
      status: 'error',
      detail: `${label} 启动失败，请检查日志目录`,
    })
  })

  child.once('exit', (code, signal) => {
    writeLog('exit ', `code=${code ?? 'null'} signal=${signal ?? 'null'}`)
    logStream.end()
    setManagedServiceProcess(key, null)

    if (isQuitting) {
      updateManagedServiceState(key, {
        status: 'idle',
        detail: '应用正在退出',
        managed: false,
        owned: false,
        restartAttempts: 0,
        launchSpec: null,
        recoveryPending: false,
      })
      return
    }

    const state = managedServices[key]
    const detail = managedServiceFailureDetail(label, code, signal)

    if (state.recoveryPending) {
      return
    }

    if (state.managed && state.owned && state.launchSpec && ['starting', 'restarting'].includes(state.status)) {
      return
    }

    if (state.managed && state.owned && state.launchSpec && state.status === 'running') {
      void restartManagedService(key, detail)
      return
    }

    updateManagedServiceState(key, {
      status: 'error',
      detail: `${label} 已停止，请检查日志目录`,
      managed: false,
      owned: false,
      launchSpec: null,
      recoveryPending: false,
    })
    showManagedServiceFailure(label, detail)
  })

  return child
}

async function startManagedService(spec, options = {}) {
  const {
    key,
    label,
    healthUrl,
    healthTimeoutMs,
  } = spec
  const { restart = false, restartAttempts = 0 } = options

  updateManagedServiceState(key, {
    label,
    status: restart ? 'restarting' : 'starting',
    detail: restart
      ? `${label} 正在自动恢复`
      : `${label} 正在启动`,
    port: managedServicePort(key),
    managed: true,
    owned: true,
    restartAttempts,
    launchSpec: { ...spec },
  })
  setManagedServiceOwned(key, true)

  const child = spawnManagedProcess(spec)
  const started = await waitForHealth(healthUrl, healthTimeoutMs)
  if (!started) {
    await killProcessTree(child)
    throw new Error(`${label} 启动超时，请检查日志目录 ${logsRoot()}`)
  }

  updateManagedServiceState(key, {
    label,
    status: 'running',
    detail: restart ? `${label} 已自动恢复` : `${label} 已运行`,
    port: managedServicePort(key),
    restartAttempts: 0,
    managed: true,
    owned: true,
    launchSpec: { ...spec },
    recoveryPending: false,
  })
  return child
}

async function restartManagedService(key, failureDetail) {
  const state = managedServices[key]
  if (!state.launchSpec || isQuitting) {
    return
  }

  const nextAttempt = state.restartAttempts + 1
  if (nextAttempt > AUTO_RESTART_LIMIT) {
    updateManagedServiceState(key, {
      status: 'error',
      detail: `${state.label} 已连续异常退出，自动恢复停止`,
      restartAttempts: state.restartAttempts,
      recoveryPending: false,
    })
    showManagedServiceFailure(state.label, failureDetail)
    return
  }

  state.recoveryPending = true
  updateManagedServiceState(key, {
    status: 'restarting',
    detail: `${state.label} 异常退出，正在自动重启（${nextAttempt}/${AUTO_RESTART_LIMIT}）`,
    restartAttempts: nextAttempt,
    managed: true,
    owned: true,
  })

  await new Promise((resolve) => setTimeout(resolve, AUTO_RESTART_DELAY_MS))

  try {
    await startManagedService(state.launchSpec, { restart: true, restartAttempts: nextAttempt })
    updateManagedServiceState(key, {
      status: 'running',
      detail: `${state.label} 已自动恢复`,
      restartAttempts: 0,
      recoveryPending: false,
    })
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    state.recoveryPending = false

    if (nextAttempt >= AUTO_RESTART_LIMIT) {
      updateManagedServiceState(key, {
        status: 'error',
        detail: `${state.label} 自动恢复失败，请检查日志目录`,
        restartAttempts: nextAttempt,
      })
      showManagedServiceFailure(state.label, `${failureDetail}\n\n自动恢复失败: ${message}`)
      return
    }

    updateManagedServiceState(key, {
      status: 'restarting',
      detail: `${state.label} 自动恢复失败，准备重试（${nextAttempt}/${AUTO_RESTART_LIMIT}）`,
      restartAttempts: nextAttempt,
      managed: true,
      owned: true,
    })
    await restartManagedService(key, `${failureDetail}\n\n自动恢复失败: ${message}`)
  } finally {
    state.recoveryPending = false
  }
}

async function ensureServices(onStatus = () => {}) {
  updateManagedServiceState('backend', {
    status: 'starting',
    detail: '正在检查治理后端状态',
    port: DEFAULT_BACKEND_PORT,
    managed: false,
    owned: false,
    restartAttempts: 0,
    launchSpec: null,
    recoveryPending: false,
  })
  onStatus('正在检查治理后端状态', 12)
  const backendReady = await healthCheck(backendHealthUrl(DEFAULT_BACKEND_PORT))

  if (!backendReady) {
    backendPort = await findAvailablePort(DEFAULT_BACKEND_PORT, {
      excluded: new Set([DEFAULT_AGENT_PORT]),
    })

    if (backendPort !== DEFAULT_BACKEND_PORT) {
      onStatus(`默认端口 ${DEFAULT_BACKEND_PORT} 已占用，改用 ${backendPort}`, 20)
    }

    const mode = readConnectionMode()

    if (mode === 'local') {
      updateManagedServiceState('agent', {
        status: 'starting',
        detail: '正在检查本机采集代理',
        port: DEFAULT_AGENT_PORT,
        managed: false,
        owned: false,
        restartAttempts: 0,
        launchSpec: null,
        recoveryPending: false,
      })
      onStatus('正在检查本机采集代理', 28)
      const defaultAgentReady = await healthCheck(`http://${LOCAL_HOST}:${DEFAULT_AGENT_PORT}/api/health`)

      if (defaultAgentReady) {
        agentPort = DEFAULT_AGENT_PORT
      } else {
        agentPort = await findAvailablePort(DEFAULT_AGENT_PORT, {
          excluded: new Set([backendPort]),
        })

        if (agentPort !== DEFAULT_AGENT_PORT) {
          onStatus(`默认 Agent 端口 ${DEFAULT_AGENT_PORT} 已占用，改用 ${agentPort}`, 34)
        }
      }

      const agentReady = await healthCheck(agentHealthUrl())

      if (!agentReady) {
        const agentExe = resourcesPath('agent', 'GPUServerAgent.exe')
        if (!fs.existsSync(agentExe)) {
          throw new Error(`Missing agent executable: ${agentExe}`)
        }

        onStatus('正在启动本机采集代理', 42)
        await startManagedService({
          key: 'agent',
          executable: agentExe,
          logName: 'agent-shell.log',
          label: '本机采集代理',
          extraEnv: {
            HOST: LOCAL_HOST,
            PORT: String(agentPort),
            GPU_AGENT_HOST: LOCAL_HOST,
            GPU_AGENT_PORT: String(agentPort),
          },
          healthUrl: agentHealthUrl(),
          healthTimeoutMs: 12000,
        })
      } else {
        onStatus('本机采集代理已在线', 42)
        markManagedServiceExternal('agent', '本机采集代理', '检测到已存在的本机采集代理实例')
      }
    } else {
      onStatus('远程服务器模式已启用，跳过本机代理启动', 42)
      updateManagedServiceState('agent', {
        label: '本机采集代理',
        status: 'external',
        detail: '当前为远程服务器模式，桌面端不会启动本机采集代理',
        port: agentPort,
        managed: false,
        owned: false,
        restartAttempts: 0,
        launchSpec: null,
        recoveryPending: false,
      })
    }

    const backendExe = resourcesPath('backend', 'GPUGovernanceBackend.exe')
    if (!fs.existsSync(backendExe)) {
      throw new Error(`Missing backend executable: ${backendExe}`)
    }

    onStatus('正在启动治理后端', 64)
    await startManagedService({
      key: 'backend',
      executable: backendExe,
      logName: 'backend-shell.log',
      label: '治理后端',
      extraEnv: {
        HOST: LOCAL_HOST,
        PORT: String(backendPort),
        AGENT_URL: agentBaseUrl(),
      },
      healthUrl: backendHealthUrl(),
      healthTimeoutMs: 18000,
    })
  } else {
    backendPort = DEFAULT_BACKEND_PORT
    agentPort = DEFAULT_AGENT_PORT
    onStatus('治理后端已在线，正在同步工作台', 64)
    markManagedServiceExternal('backend', '治理后端', '检测到已存在的治理后端实例')
    if (readConnectionMode() === 'local') {
      const localAgentReady = await healthCheck(`http://${LOCAL_HOST}:${DEFAULT_AGENT_PORT}/api/health`)
      if (localAgentReady) {
        markManagedServiceExternal('agent', '本机采集代理', '检测到已存在的本机采集代理实例')
      } else {
        updateManagedServiceState('agent', {
          label: '本机采集代理',
          status: 'idle',
          detail: '当前会话未托管本机采集代理',
          port: agentPort,
          managed: false,
          owned: false,
          restartAttempts: 0,
          launchSpec: null,
          recoveryPending: false,
        })
      }
    } else {
      updateManagedServiceState('agent', {
        label: '本机采集代理',
        status: 'external',
        detail: '当前为远程服务器模式，桌面端不会启动本机采集代理',
        port: agentPort,
        managed: false,
        owned: false,
        restartAttempts: 0,
        launchSpec: null,
        recoveryPending: false,
      })
    }
  }

  onStatus('正在等待工作台服务就绪', 82)
  const ok = await waitForHealth(backendHealthUrl(), 18000)
  if (!ok) {
    throw new Error(`Backend start timeout on port ${backendPort}. Check logs under ${logsRoot()}`)
  }

  onStatus('正在载入桌面工作台', 94)
}

function killProcessTree(child) {
  return new Promise((resolve) => {
    if (!child || !child.pid || child.killed || child.exitCode !== null) {
      resolve()
      return
    }

    const killer = spawn('taskkill', ['/PID', String(child.pid), '/T', '/F'], { windowsHide: true })
    killer.on('close', () => resolve())
    killer.on('error', () => resolve())
  })
}

async function stopManagedProcesses() {
  const tasks = []
  if (ownsBackend && backendProcess) tasks.push(killProcessTree(backendProcess))
  if (ownsAgent && agentProcess) tasks.push(killProcessTree(agentProcess))
  await Promise.all(tasks)
  setManagedServiceProcess('backend', null)
  setManagedServiceProcess('agent', null)
  setManagedServiceOwned('backend', false)
  setManagedServiceOwned('agent', false)
  updateManagedServiceState('backend', {
    status: 'idle',
    detail: '本机治理后端已停止',
    managed: false,
    owned: false,
    restartAttempts: 0,
    launchSpec: null,
    recoveryPending: false,
  })
  updateManagedServiceState('agent', {
    status: 'idle',
    detail: '本机采集代理已停止',
    managed: false,
    owned: false,
    restartAttempts: 0,
    launchSpec: null,
    recoveryPending: false,
  })
}

async function createSplashWindow() {
  if (splashWindow && !splashWindow.isDestroyed()) {
    return splashWindow
  }

  splashWindow = new BrowserWindow({
    width: 760,
    height: 460,
    show: false,
    resizable: false,
    minimizable: false,
    maximizable: false,
    fullscreenable: false,
    frame: false,
    backgroundColor: '#f8f5f0',
    icon: resolveWindowIcon(),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  })

  splashWindow.removeMenu()
  splashWindow.on('closed', () => {
    splashWindow = null
  })

  await splashWindow.loadFile(shellAssetPath('splash.html'))
  splashWindow.once('ready-to-show', () => {
    splashWindow.show()
  })

  return splashWindow
}

function closeSplashWindow() {
  if (!splashWindow || splashWindow.isDestroyed()) {
    return
  }
  splashWindow.close()
  splashWindow = null
}

async function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1520,
    height: 940,
    minWidth: 1180,
    minHeight: 760,
    show: false,
    center: true,
    title: APP_TITLE,
    autoHideMenuBar: true,
    backgroundColor: '#f8f5f0',
    icon: resolveWindowIcon(),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  })

  mainWindow.removeMenu()
  ensureTray()
  mainWindow.on('close', handleMainWindowClose)
  mainWindow.on('closed', () => {
    mainWindow = null
  })

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })

  mainWindow.webContents.on('did-fail-load', (_event, errorCode, errorDescription, validatedURL, isMainFrame) => {
    if (!isMainFrame || errorCode === -3 || isQuitting) {
      return
    }

    dialog.showMessageBox(mainWindow, {
      type: 'error',
      title: APP_TITLE,
      buttons: ['重新加载', '打开日志目录', '关闭应用'],
      defaultId: 0,
      cancelId: 2,
      message: '工作台页面加载失败',
      detail: [
        `页面地址: ${validatedURL}`,
        `错误码: ${errorCode}`,
        `错误原因: ${errorDescription}`,
        `日志目录: ${logsRoot()}`,
      ].join('\n'),
    }).then((result) => {
      if (result.response === 0) {
        mainWindow?.reload()
        return
      }
      if (result.response === 1) {
        shell.openPath(logsRoot()).catch(() => {})
        return
      }
      void requestAppShutdown()
    }).catch(() => {})
  })

  mainWindow.webContents.once('did-finish-load', () => {
    emitBootStatus('桌面工作台已就绪', 100)
    emitManagedServiceState()
    const revealTimer = setTimeout(() => {
      presentWindow(mainWindow)
    }, 120)
    revealTimer.unref?.()
  })

  mainWindow.once('ready-to-show', () => {
    closeSplashWindow()
    presentWindow(mainWindow, { forceCenter: true })
  })

  emitBootStatus('正在渲染桌面界面', 97)
  await mainWindow.webContents.session.clearCache().catch(() => {})
  await mainWindow.webContents.session.clearStorageData({ storages: ['serviceworkers'] }).catch(() => {})
  await mainWindow.loadURL(buildWorkbenchUrl())

  const showFallbackTimer = setTimeout(() => {
    if (mainWindow && !mainWindow.isDestroyed() && !mainWindow.isVisible()) {
      closeSplashWindow()
      presentWindow(mainWindow, { forceCenter: true })
    }
  }, MAIN_WINDOW_SHOW_FALLBACK_MS)
  showFallbackTimer.unref?.()
}

async function launchWorkbench() {
  await createSplashWindow()
  emitBootStatus('正在准备桌面环境', 8)
  await ensureServices(emitBootStatus)
  await createMainWindow()
}

async function showStartupError(error) {
  const detail = [
    error instanceof Error ? error.message : String(error),
    `日志目录: ${logsRoot()}`,
  ].join('\n\n')

  const result = await dialog.showMessageBox({
    type: 'error',
    title: APP_TITLE,
    buttons: ['打开日志目录', '退出'],
    defaultId: 0,
    cancelId: 1,
    message: '桌面应用启动失败',
    detail,
  })

  if (result.response === 0) {
    await shell.openPath(logsRoot())
  }
}

async function launchWorkbenchWithRecovery() {
  try {
    await launchWorkbench()
  } catch (error) {
    emitBootStatus('启动失败，请检查日志目录', 100)
    await showStartupError(error)
    isQuitting = true
    await stopManagedProcesses()
    allowWindowClose = true
    closeSplashWindow()
    app.quit()
  }
}

async function bootstrap() {
  app.setAppUserModelId(APP_ID)
  app.setName(APP_TITLE)

  const lock = app.requestSingleInstanceLock()
  if (!lock) {
    app.quit()
    return
  }

  app.on('second-instance', () => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      showMainWindow()
      return
    }

    if (splashWindow && !splashWindow.isDestroyed()) {
      presentWindow(splashWindow, { forceCenter: true })
    }
  })

  app.on('before-quit', async (event) => {
    if (allowWindowClose) {
      return
    }

    event.preventDefault()
    void requestAppShutdown()
  })

  app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
      void requestAppShutdown()
    }
  })

  app.on('activate', async () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      await launchWorkbenchWithRecovery()
      return
    }
    showMainWindow()
  })

  await app.whenReady()
  await launchWorkbenchWithRecovery()
}

bootstrap()

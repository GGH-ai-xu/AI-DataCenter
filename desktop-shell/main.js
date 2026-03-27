const { app, BrowserWindow, dialog, ipcMain, nativeImage, shell } = require('electron')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const http = require('node:http')
const { spawn } = require('node:child_process')
const DESKTOP_PACKAGE = require('./package.json')

const APP_ID = 'com.gpu.governance.workbench'
const APP_TITLE = 'GPU 共享治理平台'
const APP_SLUG = 'GPU-Governance-Workbench'
const UI_URL = 'http://127.0.0.1:8000/'
const BACKEND_HEALTH_URL = 'http://127.0.0.1:8000/api/health'
const AGENT_HEALTH_URL = 'http://127.0.0.1:8001/api/health'
const RELEASE_EXE_PATTERN = /^GPUGovernanceWorkbench-Setup-.*\.exe$/i

let mainWindow = null
let splashWindow = null
let backendProcess = null
let agentProcess = null
let ownsBackend = false
let ownsAgent = false
let isQuitting = false

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

function resolveWindowIcon() {
  const iconPath = shellAssetPath('build', 'icon.ico')
  if (!fs.existsSync(iconPath)) {
    return undefined
  }

  const image = nativeImage.createFromPath(iconPath)
  return image.isEmpty() ? undefined : image
}

ipcMain.handle('desktop-shell:get-app-info', async () => ({
  name: APP_TITLE,
  version: currentAppVersion(),
  updateSupported: Boolean(releaseRepository),
  releasesUrl: releasesPageUrl,
}))

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

function spawnManagedProcess(executable, logName, label) {
  const logPath = path.join(logsRoot(), logName)
  const logStream = fs.createWriteStream(logPath, { flags: 'a' })
  const env = {
    ...process.env,
    GPU_GOV_HOME: runtimeRoot(),
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

  writeLog('spawn ', executable)
  child.stdout?.pipe(logStream, { end: false })
  child.stderr?.pipe(logStream, { end: false })

  child.once('error', (error) => {
    writeLog('error ', error instanceof Error ? error.stack || error.message : String(error))
    logStream.end()
  })

  child.once('exit', (code, signal) => {
    writeLog('exit ', `code=${code ?? 'null'} signal=${signal ?? 'null'}`)
    logStream.end()

    if (isQuitting) {
      return
    }

    const detail = [
      `${label} 已停止。`,
      `退出码: ${code ?? '未知'}`,
      `信号: ${signal ?? '无'}`,
      `日志目录: ${logsRoot()}`,
    ].join('\n')

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
  })

  return child
}

async function ensureServices(onStatus = () => {}) {
  onStatus('正在检查治理后端状态', 12)
  const backendReady = await healthCheck(BACKEND_HEALTH_URL)

  if (!backendReady) {
    const mode = readConnectionMode()

    if (mode === 'local') {
      onStatus('正在检查本机采集代理', 28)
      const agentReady = await healthCheck(AGENT_HEALTH_URL)

      if (!agentReady) {
        const agentExe = resourcesPath('agent', 'GPUServerAgent.exe')
        if (!fs.existsSync(agentExe)) {
          throw new Error(`Missing agent executable: ${agentExe}`)
        }

        onStatus('正在启动本机采集代理', 42)
        agentProcess = spawnManagedProcess(agentExe, 'agent-shell.log', '本机采集代理')
        ownsAgent = true

        const agentStarted = await waitForHealth(AGENT_HEALTH_URL, 12000)
        if (!agentStarted) {
          throw new Error(`Agent start timeout. Check logs under ${logsRoot()}`)
        }
      } else {
        onStatus('本机采集代理已在线', 42)
      }
    } else {
      onStatus('远程服务器模式已启用，跳过本机代理启动', 42)
    }

    const backendExe = resourcesPath('backend', 'GPUGovernanceBackend.exe')
    if (!fs.existsSync(backendExe)) {
      throw new Error(`Missing backend executable: ${backendExe}`)
    }

    onStatus('正在启动治理后端', 64)
    backendProcess = spawnManagedProcess(backendExe, 'backend-shell.log', '治理后端')
    ownsBackend = true
  } else {
    onStatus('治理后端已在线，正在同步工作台', 64)
  }

  onStatus('正在等待工作台服务就绪', 82)
  const ok = await waitForHealth(BACKEND_HEALTH_URL, 18000)
  if (!ok) {
    throw new Error(`Backend start timeout. Check logs under ${logsRoot()}`)
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
  backendProcess = null
  agentProcess = null
  ownsBackend = false
  ownsAgent = false
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
      app.quit()
    }).catch(() => {})
  })

  mainWindow.webContents.once('did-finish-load', () => {
    emitBootStatus('桌面工作台已就绪', 100)
  })

  mainWindow.once('ready-to-show', () => {
    closeSplashWindow()
    mainWindow.show()
    mainWindow.focus()
  })

  emitBootStatus('正在渲染桌面界面', 97)
  await mainWindow.loadURL(UI_URL)
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
    const activeWindow = mainWindow && !mainWindow.isDestroyed() ? mainWindow : splashWindow
    if (!activeWindow) {
      return
    }
    if (activeWindow.isMinimized()) {
      activeWindow.restore()
    }
    activeWindow.focus()
  })

  app.on('before-quit', async (event) => {
    if (isQuitting) {
      return
    }
    event.preventDefault()
    isQuitting = true
    await stopManagedProcesses()
    app.quit()
  })

  app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
      app.quit()
    }
  })

  app.on('activate', async () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      await launchWorkbenchWithRecovery()
    }
  })

  await app.whenReady()
  await launchWorkbenchWithRecovery()
}

bootstrap()

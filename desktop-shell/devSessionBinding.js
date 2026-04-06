const fs = require('node:fs')
const path = require('node:path')

let launcherWatchTimer = null

function desktopDevSessionFile() {
  const target = String(process.env.DESKTOP_DEV_SESSION_FILE || '').trim()
  if (!target) {
    throw new Error('缺少 DESKTOP_DEV_SESSION_FILE，无法建立 Electron 开发会话绑定')
  }
  return target
}

function desktopDevLauncherPid() {
  const value = Number.parseInt(process.env.DESKTOP_DEV_LAUNCHER_PID || '', 10)
  if (!Number.isInteger(value) || value <= 0) {
    throw new Error('缺少 DESKTOP_DEV_LAUNCHER_PID，无法建立 Electron 开发会话绑定')
  }
  return value
}

function writeDesktopDevSession() {
  const sessionFile = desktopDevSessionFile()
  fs.mkdirSync(path.dirname(sessionFile), { recursive: true })
  fs.writeFileSync(sessionFile, JSON.stringify({
    pid: process.pid,
    launcherPid: desktopDevLauncherPid(),
    startedAt: new Date().toISOString(),
  }), 'utf8')
}

function clearDesktopDevSession() {
  const sessionFile = String(process.env.DESKTOP_DEV_SESSION_FILE || '').trim()
  if (!sessionFile) {
    return
  }
  fs.rmSync(sessionFile, { force: true })
}

function stopDesktopDevLauncherWatch() {
  if (!launcherWatchTimer) {
    return
  }
  clearInterval(launcherWatchTimer)
  launcherWatchTimer = null
}

function startDesktopDevLauncherWatch(onLauncherExit) {
  const launcherPid = desktopDevLauncherPid()
  stopDesktopDevLauncherWatch()
  launcherWatchTimer = setInterval(() => {
    try {
      process.kill(launcherPid, 0)
    } catch {
      stopDesktopDevLauncherWatch()
      onLauncherExit(launcherPid)
    }
  }, 1000)
  launcherWatchTimer.unref?.()
}

module.exports = {
  clearDesktopDevSession,
  startDesktopDevLauncherWatch,
  stopDesktopDevLauncherWatch,
  writeDesktopDevSession,
}

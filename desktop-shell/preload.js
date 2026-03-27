const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('desktopShell', {
  platform: process.platform,
  isDesktop: true,
  getAppInfo() {
    return ipcRenderer.invoke('desktop-shell:get-app-info')
  },
  checkForUpdates() {
    return ipcRenderer.invoke('desktop-shell:check-for-updates')
  },
  openExternal(url) {
    return ipcRenderer.invoke('desktop-shell:open-external', url)
  },
  resolveCloseRequest(action) {
    return ipcRenderer.invoke('desktop-shell:resolve-close-request', action)
  },
  onBootStatus(callback) {
    if (typeof callback !== 'function') {
      return () => {}
    }

    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('boot-status', listener)
    return () => ipcRenderer.removeListener('boot-status', listener)
  },
  onCloseRequest(callback) {
    if (typeof callback !== 'function') {
      return () => {}
    }

    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('desktop-shell:close-requested', listener)
    return () => ipcRenderer.removeListener('desktop-shell:close-requested', listener)
  },
})

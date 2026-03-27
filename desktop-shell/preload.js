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
  onBootStatus(callback) {
    if (typeof callback !== 'function') {
      return () => {}
    }

    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('boot-status', listener)
    return () => ipcRenderer.removeListener('boot-status', listener)
  },
})

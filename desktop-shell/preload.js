const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('desktopShell', {
  platform: process.platform,
  isDesktop: true,
  getAppInfo() {
    return ipcRenderer.invoke('desktop-shell:get-app-info')
  },
  getServiceState() {
    return ipcRenderer.invoke('desktop-shell:get-service-state')
  },
  getRuntimeInfo() {
    return ipcRenderer.invoke('desktop-shell:get-runtime-info')
  },
  checkForUpdates() {
    return ipcRenderer.invoke('desktop-shell:check-for-updates')
  },
  openExternal(url) {
    return ipcRenderer.invoke('desktop-shell:open-external', url)
  },
  copyText(value) {
    return ipcRenderer.invoke('desktop-shell:copy-text', value)
  },
  openPath(value) {
    return ipcRenderer.invoke('desktop-shell:open-path', value)
  },
  exportAgentPackage() {
    return ipcRenderer.invoke('desktop-shell:export-agent-package')
  },
  restartManagedServices() {
    return ipcRenderer.invoke('desktop-shell:restart-managed-services')
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
  onServiceState(callback) {
    if (typeof callback !== 'function') {
      return () => {}
    }

    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('desktop-shell:service-state', listener)
    return () => ipcRenderer.removeListener('desktop-shell:service-state', listener)
  },
})

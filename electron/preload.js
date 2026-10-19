const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  minimize: () => ipcRenderer.send('window-minimize'),
  maximize: () => ipcRenderer.send('window-maximize'),
  close: () => ipcRenderer.send('window-close'),
  openPath: (fullPath) => ipcRenderer.invoke('open-path', fullPath),
  openExternal: (url) => ipcRenderer.invoke('open-external', url),
  platform: process.platform,

  // Window state
  onMaximizedChange: (callback) => ipcRenderer.on('window-maximized-change', (event, isMaximized) => callback(isMaximized)),
  isMaximized: () => ipcRenderer.invoke('window-is-maximized'),

  // OTA / Auto-update APIs
  checkForUpdates: () => ipcRenderer.send('check-for-updates'),
  restartForUpdate: () => ipcRenderer.send('restart-app-for-update'),
  onUpdateStatus: (callback) => {
    ipcRenderer.on('update-status', (event, data) => callback(data));
  }
});

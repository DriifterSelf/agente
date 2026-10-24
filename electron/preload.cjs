const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  selectFolder: () => ipcRenderer.invoke('select-folder'),
  minimize: () => ipcRenderer.send('window-minimize'),
  maximize: () => ipcRenderer.send('window-maximize'),
  close: () => ipcRenderer.send('window-close'),
  openPath: (fullPath) => ipcRenderer.invoke('open-path', fullPath),
  openExternal: (url) => ipcRenderer.invoke('open-external', url),
  platform: process.platform,
  isElectron: true,

  // DevTools & Debugging
  openDevTools: (mode) => ipcRenderer.send('open-devtools', mode),
  toggleDevTools: () => ipcRenderer.send('toggle-devtools'),
  reloadWindow: () => ipcRenderer.send('window-reload'),

  // Backend diagnostics & logs
  getBackendStatus: () => ipcRenderer.invoke('get-backend-status'),
  getBackendLogs: () => ipcRenderer.invoke('get-backend-logs'),
  restartBackend: () => ipcRenderer.invoke('restart-backend'),
  selectPythonPath: () => ipcRenderer.invoke('select-python-path'),
  installPythonWinGet: () => ipcRenderer.invoke('install-python-winget'),
  downloadPortablePython: () => ipcRenderer.invoke('download-portable-python'),
  onBackendLog: (callback) => {
    const listener = (event, data) => callback(data);
    ipcRenderer.on('backend-log', listener);
    return () => ipcRenderer.removeListener('backend-log', listener);
  },

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


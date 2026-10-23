const { app, BrowserWindow, ipcMain, shell, dialog } = require('electron');
const path = require('path');
const fs = require('fs');
const { autoUpdater } = require('electron-updater');
const BackendManager = require('./backend_manager.cjs');

let mainWindow = null;
let backendManager = null;

// Configure auto-updater
autoUpdater.autoDownload = true;
autoUpdater.autoInstallOnAppQuit = true;

// Clean up old cached installers in %LOCALAPPDATA%\agente-studio-updater\pending
function cleanOldUpdaterCache() {
  try {
    const localAppData = process.env.LOCALAPPDATA || (process.platform === 'win32' && process.env.USERPROFILE ? path.join(process.env.USERPROFILE, 'AppData', 'Local') : null);
    if (!localAppData) return;
    const pendingDir = path.join(localAppData, 'agente-studio-updater', 'pending');
    if (fs.existsSync(pendingDir)) {
      const entries = fs.readdirSync(pendingDir);
      for (const entry of entries) {
        try {
          fs.rmSync(path.join(pendingDir, entry), { recursive: true, force: true });
        } catch (e) {}
      }
    }
  } catch (e) {}
}

function setupAutoUpdater() {
  cleanOldUpdaterCache();
  autoUpdater.on('checking-for-update', () => {
    mainWindow?.webContents.send('update-status', { status: 'checking' });
  });

  autoUpdater.on('update-available', (info) => {
    mainWindow?.webContents.send('update-status', {
      status: 'available',
      version: info.version
    });
  });

  autoUpdater.on('update-not-available', () => {
    mainWindow?.webContents.send('update-status', { status: 'not-available' });
  });

  autoUpdater.on('download-progress', (progressObj) => {
    mainWindow?.webContents.send('update-status', {
      status: 'downloading',
      percent: Math.round(progressObj.percent),
      bytesPerSecond: progressObj.bytesPerSecond
    });
  });

  autoUpdater.on('update-downloaded', (info) => {
    mainWindow?.webContents.send('update-status', {
      status: 'downloaded',
      version: info.version
    });
  });

  autoUpdater.on('error', (err) => {
    mainWindow?.webContents.send('update-status', {
      status: 'error',
      error: err.message
    });
  });

  ipcMain.on('check-for-updates', () => {
    if (app.isPackaged) {
      autoUpdater.checkForUpdates();
    } else {
      mainWindow?.webContents.send('update-status', { status: 'dev-mode' });
    }
  });

  ipcMain.on('restart-app-for-update', () => {
    autoUpdater.quitAndInstall();
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1360,
    height: 860,
    minWidth: 1050,
    minHeight: 650,
    frame: false, // Custom frameless window for sleek Antigravity look
    backgroundColor: '#0B0F17',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      nodeIntegration: false,
      contextIsolation: true
    }
  });
  ipcMain.handle('select-folder', async () => {
    if (!mainWindow) return null;
    const result = await dialog.showOpenDialog(mainWindow, {
      title: 'Seleccionar Repositorio Local',
      properties: ['openDirectory']
    });
    return result.canceled ? null : result.filePaths[0];
  });

  // Window controls
  ipcMain.on('window-minimize', () => {
    if (mainWindow) mainWindow.minimize();
  });

  ipcMain.on('window-maximize', () => {
    if (mainWindow) {
      if (mainWindow.isMaximized()) {
        mainWindow.unmaximize();
      } else {
        mainWindow.maximize();
      }
    }
  });

  ipcMain.on('window-close', () => {
    if (mainWindow) mainWindow.close();
  });

  ipcMain.handle('open-path', async (event, fullPath) => {
    return await shell.openPath(fullPath);
  });

  ipcMain.handle('open-external', async (event, url) => {
    return await shell.openExternal(url);
  });

  ipcMain.handle('window-is-maximized', () => {
    return mainWindow ? mainWindow.isMaximized() : false;
  });

  mainWindow.on('maximize', () => {
    mainWindow?.webContents.send('window-maximized-change', true);
  });

  mainWindow.on('unmaximize', () => {
    mainWindow?.webContents.send('window-maximized-change', false);
  });

  // Load URL or built file
  const distHtml = path.join(__dirname, '..', 'dist', 'index.html');

  if (process.env.VITE_DEV === 'true') {
    mainWindow.loadURL('http://localhost:3000');
  } else if (fs.existsSync(distHtml)) {
    mainWindow.loadFile(distHtml);
  } else {
    mainWindow.loadURL('http://localhost:3000');
  }

  // Crash and load error diagnostics
  mainWindow.webContents.on('did-fail-load', (event, errorCode, errorDescription, validatedURL) => {
    console.error(`[Electron] Page failed to load: ${validatedURL} [${errorCode}: ${errorDescription}]`);
  });

  mainWindow.webContents.on('render-process-gone', (event, details) => {
    console.error('[Electron] Renderer process gone:', details);
  });

  // Allow F12 or Ctrl+Shift+I to open DevTools for troubleshooting if needed
  mainWindow.webContents.on('before-input-event', (event, input) => {
    if (input.key === 'F12' || (input.control && input.shift && input.key.toLowerCase() === 'i')) {
      mainWindow.webContents.toggleDevTools();
      event.preventDefault();
    }
  });

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    if (app.isPackaged) {
      setTimeout(() => {
        autoUpdater.checkForUpdatesAndNotify();
      }, 3000);
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// Disable hardware acceleration on Windows to prevent GPU compositing black screen
if (process.platform === 'win32') {
  app.disableHardwareAcceleration();
}

app.whenReady().then(async () => {
  const basePath = app.isPackaged ? process.resourcesPath : app.getAppPath();
  backendManager = new BackendManager(basePath);

  setupAutoUpdater();

  // Display the UI immediately
  createWindow();

  // Start backend asynchronously without blocking window rendering
  backendManager.start().catch((err) => {
    console.error('Failed to start backend:', err);
  });

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (backendManager) {
    backendManager.stop();
  }
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('will-quit', () => {
  if (backendManager) {
    backendManager.stop();
  }
});

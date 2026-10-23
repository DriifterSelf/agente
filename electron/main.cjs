const { app, BrowserWindow, ipcMain, shell, dialog, Menu } = require('electron');
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

function setupIpcHandlers() {
  ipcMain.handle('select-folder', async () => {
    if (!mainWindow) return null;
    const result = await dialog.showOpenDialog(mainWindow, {
      title: 'Seleccionar Repositorio Local',
      properties: ['openDirectory']
    });
    return result.canceled ? null : result.filePaths[0];
  });

  // Window controls
  ipcMain.on('window-minimize', (event) => {
    const win = BrowserWindow.fromWebContents(event.sender) || mainWindow;
    if (win && !win.isDestroyed()) {
      win.minimize();
    }
  });

  ipcMain.on('window-maximize', (event) => {
    const win = BrowserWindow.fromWebContents(event.sender) || mainWindow;
    if (win && !win.isDestroyed()) {
      if (win.isMaximized()) {
        win.unmaximize();
      } else {
        win.maximize();
      }
    }
  });

  ipcMain.on('window-close', (event) => {
    const win = BrowserWindow.fromWebContents(event.sender) || mainWindow;
    if (win && !win.isDestroyed()) {
      win.close();
    }
  });

  ipcMain.handle('open-path', async (event, fullPath) => {
    return await shell.openPath(fullPath);
  });

  ipcMain.handle('open-external', async (event, url) => {
    return await shell.openExternal(url);
  });

  ipcMain.handle('window-is-maximized', (event) => {
    const win = BrowserWindow.fromWebContents(event.sender) || mainWindow;
    return win && !win.isDestroyed() ? win.isMaximized() : false;
  });

  // DevTools & Debugging IPC
  ipcMain.on('open-devtools', (event, mode) => {
    const win = BrowserWindow.fromWebContents(event.sender) || mainWindow;
    if (win && !win.isDestroyed()) {
      win.webContents.openDevTools({ mode: mode || 'detach' });
    }
  });

  ipcMain.on('toggle-devtools', (event) => {
    const win = BrowserWindow.fromWebContents(event.sender) || mainWindow;
    if (win && !win.isDestroyed()) {
      win.webContents.toggleDevTools();
    }
  });

  ipcMain.on('window-reload', (event) => {
    const win = BrowserWindow.fromWebContents(event.sender) || mainWindow;
    if (win && !win.isDestroyed()) {
      win.webContents.reload();
    }
  });

  // Backend diagnostics IPC
  ipcMain.handle('get-backend-status', () => {
    return backendManager ? backendManager.getStatus() : { status: 'none' };
  });

  ipcMain.handle('get-backend-logs', () => {
    return backendManager ? backendManager.getLogs() : [];
  });

  ipcMain.handle('restart-backend', async () => {
    if (backendManager) {
      backendManager.stop();
      return await backendManager.start();
    }
    return false;
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
      contextIsolation: true,
      devTools: true // Explicitly enable DevTools in all builds
    }
  });

  mainWindow.on('maximize', () => {
    mainWindow?.webContents.send('window-maximized-change', true);
  });

  mainWindow.on('unmaximize', () => {
    mainWindow?.webContents.send('window-maximized-change', false);
  });

  // Context menu for Inspect Element & DevTools
  mainWindow.webContents.on('context-menu', (event, params) => {
    const contextMenu = Menu.buildFromTemplate([
      {
        label: 'Inspeccionar elemento',
        click: () => {
          mainWindow.webContents.inspectElement(params.x, params.y);
          if (!mainWindow.webContents.isDevToolsOpened()) {
            mainWindow.webContents.openDevTools({ mode: 'detach' });
          }
        }
      },
      {
        label: 'Abrir DevTools / Consola (F12)',
        accelerator: 'F12',
        click: () => {
          mainWindow.webContents.openDevTools({ mode: 'detach' });
        }
      },
      { type: 'separator' },
      {
        label: 'Recargar aplicación (Ctrl+R / F5)',
        accelerator: 'CmdOrCtrl+R',
        click: () => {
          mainWindow.webContents.reload();
        }
      },
      { type: 'separator' },
      { role: 'cut', label: 'Cortar' },
      { role: 'copy', label: 'Copiar' },
      { role: 'paste', label: 'Pegar' },
      { role: 'selectAll', label: 'Seleccionar todo' }
    ]);
    contextMenu.popup({ window: mainWindow, x: params.x, y: params.y });
  });

  // Global keyboard shortcuts (F12, Ctrl+Shift+I, F5, Ctrl+R)
  mainWindow.webContents.on('before-input-event', (event, input) => {
    if (input.type !== 'keyDown') return;

    if (
      input.key === 'F12' ||
      ((input.control || input.meta) && input.shift && input.key.toLowerCase() === 'i')
    ) {
      mainWindow.webContents.toggleDevTools();
      event.preventDefault();
    } else if (
      input.key === 'F5' ||
      ((input.control || input.meta) && !input.shift && input.key.toLowerCase() === 'r')
    ) {
      mainWindow.webContents.reload();
      event.preventDefault();
    }
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

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    if (backendManager) {
      backendManager.setMainWindow(mainWindow);
    }
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

  setupIpcHandlers();
  setupAutoUpdater();

  // Display the UI immediately
  createWindow();

  if (backendManager && mainWindow) {
    backendManager.setMainWindow(mainWindow);
  }

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


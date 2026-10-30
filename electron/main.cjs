const { app, BrowserWindow, ipcMain, shell, dialog, Menu } = require('electron');
const path = require('path');
const fs = require('fs');
const os = require('os');
const https = require('https');
const { spawn } = require('child_process');
const { autoUpdater } = require('electron-updater');
const BackendManager = require('./backend_manager.cjs');

let mainWindow = null;
let backendManager = null;
let customDownloadedInstallerPath = null;
let isAutoUpdaterHandlingDownload = false;

const GITHUB_OWNER = 'DriifterSelf';
const GITHUB_REPO = 'agente';

// Configure auto-updater explicitly
autoUpdater.autoDownload = true;
autoUpdater.autoInstallOnAppQuit = true;
autoUpdater.allowPrerelease = true;

try {
  autoUpdater.setFeedURL({
    provider: 'github',
    owner: GITHUB_OWNER,
    repo: GITHUB_REPO
  });
} catch (e) {}

function logOta(text, type = 'system') {
  console.log(`[OTA] ${text}`);
  if (backendManager) {
    backendManager.addLog(type, `[OTA] ${text}`);
  }
}

// Extract clean semver (e.g. "1.2.0", "1.3.0", "2.0.0") from any tag string like "v1.2.0", "1 v1.2.0", "Release v2.0.0"
function extractSemver(raw) {
  if (!raw || typeof raw !== 'string') return null;
  const match = raw.match(/(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?/);
  if (!match) return null;
  return {
    clean: `${match[1]}.${match[2]}.${match[3]}`,
    major: parseInt(match[1], 10),
    minor: parseInt(match[2], 10),
    patch: parseInt(match[3], 10),
    prerelease: match[4] || null,
    raw: raw.trim()
  };
}

// Returns > 0 if verA > verB, < 0 if verA < verB, 0 if equal
function compareSemver(verA, verB) {
  const a = typeof verA === 'string' ? extractSemver(verA) : verA;
  const b = typeof verB === 'string' ? extractSemver(verB) : verB;
  if (!a && !b) return 0;
  if (a && !b) return 1;
  if (!a && b) return -1;
  if (a.major !== b.major) return a.major - b.major;
  if (a.minor !== b.minor) return a.minor - b.minor;
  return a.patch - b.patch;
}

function fetchGitHubJson(apiPath) {
  return new Promise((resolve, reject) => {
    const req = https.get(
      `https://api.github.com${apiPath}`,
      {
        headers: {
          'User-Agent': 'AgenteStudio-OTA/1.0',
          Accept: 'application/vnd.github+json'
        },
        timeout: 8000
      },
      (res) => {
        if (res.statusCode === 301 || res.statusCode === 302) {
          return fetchGitHubJson(res.headers.location.replace('https://api.github.com', '')).then(resolve).catch(reject);
        }
        let body = '';
        res.on('data', (chunk) => (body += chunk));
        res.on('end', () => {
          if (res.statusCode >= 200 && res.statusCode < 300) {
            try {
              resolve(JSON.parse(body));
            } catch (e) {
              reject(e);
            }
          } else {
            reject(new Error(`GitHub API HTTP ${res.statusCode}`));
          }
        });
      }
    );
    req.on('error', reject);
  });
}

function downloadInstallerDirectly(downloadUrl, targetVersion) {
  return new Promise((resolve, reject) => {
    const destPath = path.join(os.tmpdir(), `AgenteStudio-Setup-${targetVersion}.exe`);
    logOta(`Descargando instalador v${targetVersion} desde GitHub Releases...`);
    const file = fs.createWriteStream(destPath);

    const requestUrl = (url) => {
      https
        .get(url, { headers: { 'User-Agent': 'AgenteStudio-OTA/1.0' } }, (res) => {
          if (res.statusCode === 301 || res.statusCode === 302 || res.statusCode === 307) {
            return requestUrl(res.headers.location);
          }
          if (res.statusCode !== 200) {
            file.close();
            return reject(new Error(`HTTP ${res.statusCode}`));
          }

          const totalBytes = parseInt(res.headers['content-length'] || '0', 10);
          let downloadedBytes = 0;

          res.on('data', (chunk) => {
            downloadedBytes += chunk.length;
            if (totalBytes > 0) {
              const percent = Math.min(99, Math.round((downloadedBytes / totalBytes) * 100));
              mainWindow?.webContents.send('update-status', {
                status: 'downloading',
                version: targetVersion,
                percent
              });
            }
          });

          res.pipe(file);
          file.on('finish', () => {
            file.close(() => {
              customDownloadedInstallerPath = destPath;
              logOta(`¡Instalador v${targetVersion} descargado y listo para aplicar! (${destPath})`);
              mainWindow?.webContents.send('update-status', {
                status: 'downloaded',
                version: targetVersion
              });
              resolve(destPath);
            });
          });
        })
        .on('error', (err) => {
          fs.unlink(destPath, () => {});
          reject(err);
        });
    };

    requestUrl(downloadUrl);
  });
}

// Direct inspection of GitHub Releases and Tags so v1.2.0, v1.3.0, v2.0.0 are ALWAYS recognized
async function checkGitHubTagsAndReleases() {
  try {
    const currentVersion = app.getVersion();
    logOta(`Consultando tags y releases en github.com/${GITHUB_OWNER}/${GITHUB_REPO} (Versión actual: v${currentVersion})...`);

    const [releases, tags] = await Promise.all([
      fetchGitHubJson(`/repos/${GITHUB_OWNER}/${GITHUB_REPO}/releases?per_page=30`).catch(() => []),
      fetchGitHubJson(`/repos/${GITHUB_OWNER}/${GITHUB_REPO}/tags?per_page=30`).catch(() => [])
    ]);

    const candidates = [];

    if (Array.isArray(releases)) {
      for (const rel of releases) {
        if (rel.draft) continue;
        const parsed = extractSemver(rel.tag_name) || extractSemver(rel.name);
        if (parsed) {
          const assets = Array.isArray(rel.assets) ? rel.assets : [];
          const exeAsset = assets.find(
            (a) =>
              /\.exe$/i.test(a.name) &&
              !/blockmap/i.test(a.name) &&
              !/uninstall/i.test(a.name)
          );
          candidates.push({
            ...parsed,
            rawTag: rel.tag_name || rel.name,
            exeUrl: exeAsset ? exeAsset.browser_download_url : null,
            htmlUrl: rel.html_url,
            source: 'release'
          });
        }
      }
    }

    if (Array.isArray(tags)) {
      for (const t of tags) {
        const parsed = extractSemver(t.name);
        if (parsed && !candidates.some((c) => c.clean === parsed.clean)) {
          candidates.push({
            ...parsed,
            rawTag: t.name,
            exeUrl: null,
            htmlUrl: `https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}/releases/tag/${encodeURIComponent(t.name)}`,
            source: 'tag'
          });
        }
      }
    }

    if (candidates.length === 0) {
      logOta('No se encontraron tags semver en el repositorio remoto.');
      return null;
    }

    // Sort descending by semver (so v2.0.0 > v1.3.0 > v1.2.0 > v1.0.1)
    candidates.sort((a, b) => compareSemver(b, a));
    const highest = candidates[0];
    const detectedList = candidates.slice(0, 6).map((c) => `v${c.clean} (${c.rawTag})`).join(', ');
    logOta(`Tags detectados en GitHub: [${detectedList}] | Mayor versión: v${highest.clean}`);

    if (compareSemver(highest.clean, currentVersion) > 0) {
      logOta(`¡Nueva versión detectada! v${highest.clean} > v${currentVersion}`);
      mainWindow?.webContents.send('update-status', {
        status: 'available',
        version: highest.clean,
        rawTag: highest.rawTag,
        hasInstaller: Boolean(highest.exeUrl)
      });

      // If there is a .exe asset on the release and electron-updater isn't already downloading it, download directly
      if (highest.exeUrl && !isAutoUpdaterHandlingDownload) {
        await downloadInstallerDirectly(highest.exeUrl, highest.clean);
      } else if (!highest.exeUrl) {
        // Check if any newer release has an .exe asset
        const newestWithExe = candidates.find(
          (c) => compareSemver(c.clean, currentVersion) > 0 && Boolean(c.exeUrl)
        );
        if (newestWithExe && !isAutoUpdaterHandlingDownload) {
          await downloadInstallerDirectly(newestWithExe.exeUrl, newestWithExe.clean);
        } else {
          logOta(
            `El tag ${highest.rawTag} (v${highest.clean}) existe en GitHub pero aún no tiene un archivo .exe compilado en Releases.`
          );
          mainWindow?.webContents.send('update-status', {
            status: 'tag-only',
            version: highest.clean,
            rawTag: highest.rawTag
          });
        }
      }
      return highest;
    } else {
      logOta(`La aplicación está en la versión más reciente (v${currentVersion}).`);
      mainWindow?.webContents.send('update-status', {
        status: 'not-available',
        version: currentVersion
      });
      return null;
    }
  } catch (err) {
    logOta(`Error al verificar tags de GitHub: ${err.message}`, 'stderr');
    return null;
  }
}

// Clean up old cached installers in %LOCALAPPDATA%\agente-studio-updater\pending
function cleanOldUpdaterCache() {
  try {
    const localAppData =
      process.env.LOCALAPPDATA ||
      (process.platform === 'win32' && process.env.USERPROFILE
        ? path.join(process.env.USERPROFILE, 'AppData', 'Local')
        : null);
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

// Ensure ~/AgenteStudio/models and ~/AgenteStudio/projects exist and rescue any .gguf models
// from the Electron installation directory BEFORE an NSIS update can overwrite the install folder.
function rescueUserModelsAndProjects() {
  try {
    const userVault = path.join(os.homedir(), 'AgenteStudio');
    const safeModelsDir = path.join(userVault, 'models');
    const safeProjectsDir = path.join(userVault, 'projects');
    fs.mkdirSync(safeModelsDir, { recursive: true });
    fs.mkdirSync(safeProjectsDir, { recursive: true });

    const candidateInstallDirs = [
      process.resourcesPath ? path.join(process.resourcesPath, 'models') : null,
      process.resourcesPath ? path.join(path.dirname(process.resourcesPath), 'models') : null,
      process.execPath ? path.join(path.dirname(process.execPath), 'models') : null,
      app.getAppPath() ? path.join(app.getAppPath(), 'models') : null
    ].filter(Boolean);

    for (const dir of candidateInstallDirs) {
      if (!fs.existsSync(dir) || path.resolve(dir) === path.resolve(safeModelsDir)) continue;
      const entries = fs.readdirSync(dir, { withFileTypes: true });
      for (const entry of entries) {
        if (entry.isFile() && entry.name.toLowerCase().endsWith('.gguf')) {
          const srcPath = path.join(dir, entry.name);
          const dstPath = path.join(safeModelsDir, entry.name);
          if (!fs.existsSync(dstPath)) {
            try {
              fs.renameSync(srcPath, dstPath);
              logOta(`Modelo GGUF protegido en bóveda persistente: ${dstPath}`);
            } catch (moveErr) {
              try {
                fs.copyFileSync(srcPath, dstPath);
                fs.unlinkSync(srcPath);
                logOta(`Modelo GGUF copiado a bóveda persistente: ${dstPath}`);
              } catch (e) {}
            }
          }
        }
      }
    }
  } catch (e) {
    console.warn('[StorageGuard] Aviso protegiendo modelos:', e.message);
  }
}

function setupAutoUpdater() {
  cleanOldUpdaterCache();

  autoUpdater.on('checking-for-update', () => {
    logOta('Buscando actualizaciones vía electron-updater...');
    mainWindow?.webContents.send('update-status', { status: 'checking' });
  });

  autoUpdater.on('update-available', (info) => {
    isAutoUpdaterHandlingDownload = true;
    logOta(`Actualización disponible en electron-updater: v${info.version}`);
    mainWindow?.webContents.send('update-status', {
      status: 'available',
      version: info.version
    });
  });

  autoUpdater.on('update-not-available', () => {
    // Also verify directly against GitHub API tags/releases in case latest.yml was out of sync
    checkGitHubTagsAndReleases();
  });

  autoUpdater.on('download-progress', (progressObj) => {
    isAutoUpdaterHandlingDownload = true;
    mainWindow?.webContents.send('update-status', {
      status: 'downloading',
      percent: Math.round(progressObj.percent),
      bytesPerSecond: progressObj.bytesPerSecond
    });
  });

  autoUpdater.on('update-downloaded', (info) => {
    logOta(`Actualización v${info.version} descargada por electron-updater.`);
    mainWindow?.webContents.send('update-status', {
      status: 'downloaded',
      version: info.version
    });
  });

  autoUpdater.on('error', (err) => {
    logOta(`Aviso en electron-updater (${err.message}), usando verificador directo de Tags de GitHub...`);
    isAutoUpdaterHandlingDownload = false;
    checkGitHubTagsAndReleases();
  });

  ipcMain.on('check-for-updates', async () => {
    mainWindow?.webContents.send('update-status', { status: 'checking' });
    if (app.isPackaged) {
      try {
        await autoUpdater.checkForUpdates();
      } catch (e) {
        await checkGitHubTagsAndReleases();
      }
    } else {
      await checkGitHubTagsAndReleases();
    }
  });

  ipcMain.on('restart-app-for-update', () => {
    // Stop backend & llama-server first so file locks on .gguf models are released, then rescue any models
    if (backendManager) {
      backendManager.stop();
    }
    rescueUserModelsAndProjects();

    if (customDownloadedInstallerPath && fs.existsSync(customDownloadedInstallerPath)) {
      logOta(`Ejecutando instalador descargado: ${customDownloadedInstallerPath}`);
      try {
        const child = spawn(customDownloadedInstallerPath, [], {
          detached: true,
          stdio: 'ignore'
        });
        child.unref();
        app.quit();
        return;
      } catch (e) {
        shell.openPath(customDownloadedInstallerPath);
        app.quit();
        return;
      }
    }
    autoUpdater.quitAndInstall();
  });
}

function setupIpcHandlers() {
  ipcMain.handle('get-app-version', () => {
    return app.getVersion();
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

  ipcMain.handle('select-python-path', async () => {
    if (!mainWindow) return null;
    const result = await dialog.showOpenDialog(mainWindow, {
      title: 'Seleccionar ejecutable de Python (python.exe o py.exe)',
      filters: [
        { name: 'Ejecutables Python', extensions: ['exe', 'bat', 'cmd'] },
        { name: 'Todos los archivos', extensions: ['*'] }
      ],
      properties: ['openFile']
    });
    if (!result.canceled && result.filePaths[0] && backendManager) {
      return await backendManager.setCustomPython(result.filePaths[0]);
    }
    return null;
  });

  ipcMain.handle('install-python-winget', async () => {
    if (backendManager) {
      return await backendManager.installViaWinGet();
    }
    return { success: false, error: 'Backend manager no disponible' };
  });

  ipcMain.handle('download-portable-python', async () => {
    if (backendManager) {
      return await backendManager.downloadPortablePython();
    }
    return { success: false, error: 'Backend manager no disponible' };
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1360,
    height: 860,
    minWidth: 1050,
    minHeight: 650,
    frame: false,
    backgroundColor: '#0B0F17',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      nodeIntegration: false,
      contextIsolation: true,
      devTools: true
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
    setTimeout(() => {
      if (app.isPackaged) {
        autoUpdater.checkForUpdates().catch(() => {
          checkGitHubTagsAndReleases();
        });
      } else {
        checkGitHubTagsAndReleases();
      }
    }, 3000);
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
  rescueUserModelsAndProjects();
  const basePath = app.isPackaged ? process.resourcesPath : app.getAppPath();
  backendManager = new BackendManager(basePath);

  setupIpcHandlers();
  setupAutoUpdater();

  createWindow();

  if (backendManager && mainWindow) {
    backendManager.setMainWindow(mainWindow);
  }

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
  rescueUserModelsAndProjects();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('will-quit', () => {
  if (backendManager) {
    backendManager.stop();
  }
  rescueUserModelsAndProjects();
});

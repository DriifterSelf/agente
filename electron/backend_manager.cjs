const { spawn, execSync } = require('child_process');
const path = require('path');
const http = require('http');
const fs = require('fs');

class BackendManager {
  constructor(basePath) {
    this.basePath = basePath;
    this.process = null;
    this.logs = [];
    this.status = 'idle'; // idle | starting | running | failed | no_python
    this.errorMessage = null;
    this.mainWindow = null;
    this.resolvedPython = null;

    // Config path for user custom python path
    try {
      const appData = process.env.APPDATA || (process.platform === 'win32' && process.env.USERPROFILE ? path.join(process.env.USERPROFILE, 'AppData', 'Roaming') : null);
      this.configDir = appData ? path.join(appData, 'AgenteStudio') : path.join(this.basePath, '.config');
      this.configFile = path.join(this.configDir, 'python_config.json');
      if (!fs.existsSync(this.configDir)) {
        fs.mkdirSync(this.configDir, { recursive: true });
      }
    } catch (e) {
      this.configFile = null;
    }
  }

  setMainWindow(win) {
    this.mainWindow = win;
  }

  addLog(type, text) {
    const entry = {
      type, // 'stdout' | 'stderr' | 'system'
      text: String(text).trim(),
      time: new Date().toLocaleTimeString()
    };
    if (entry.text) {
      console.log(`[Backend ${entry.type}] ${entry.text}`);
      this.logs.push(entry);
      if (this.logs.length > 600) this.logs.shift();
      if (this.mainWindow && !this.mainWindow.isDestroyed()) {
        try {
          this.mainWindow.webContents.send('backend-log', entry);
        } catch (e) {}
      }
    }
  }

  getLogs() {
    return this.logs;
  }

  getStatus() {
    return {
      status: this.status,
      errorMessage: this.errorMessage,
      hasProcess: Boolean(this.process),
      pythonPath: this.resolvedPython ? this.resolvedPython.cmd : null,
      logCount: this.logs.length
    };
  }

  getSavedCustomPython() {
    try {
      if (this.configFile && fs.existsSync(this.configFile)) {
        const raw = fs.readFileSync(this.configFile, 'utf-8');
        const data = JSON.parse(raw);
        if (data.pythonPath && fs.existsSync(data.pythonPath)) {
          return data.pythonPath;
        }
      }
    } catch (e) {}
    return null;
  }

  saveCustomPython(customPath) {
    try {
      if (this.configFile && customPath) {
        fs.writeFileSync(this.configFile, JSON.stringify({ pythonPath: customPath }, null, 2), 'utf-8');
      }
    } catch (e) {}
  }

  // Detect genuine working Python executable on Windows / Linux / macOS
  findPythonCommand() {
    // 1. Saved custom python from user
    const saved = this.getSavedCustomPython();
    if (saved) {
      this.addLog('system', `Usando Python personalizado guardado: ${saved}`);
      return { cmd: saved, args: [] };
    }

    // 2. Environment variable PYTHON
    if (process.env.PYTHON && fs.existsSync(process.env.PYTHON)) {
      return { cmd: process.env.PYTHON, args: [] };
    }

    // 3. Embedded Python bundled inside the application distribution or user data
    const bundledCandidates = [
      path.join(this.basePath, 'python', 'python.exe'),
      path.join(this.basePath, 'python-embed', 'python.exe'),
      path.join(this.basePath, 'runtime', 'python.exe'),
      path.join(this.basePath, '..', 'python', 'python.exe'),
      path.join(this.basePath, '..', 'runtime', 'python.exe'),
      this.configDir ? path.join(this.configDir, 'python', 'python.exe') : null
    ].filter(Boolean);

    for (const p of bundledCandidates) {
      if (fs.existsSync(p)) {
        this.addLog('system', `Encontrado Python embebido en la aplicación: ${p}`);
        return { cmd: p, args: [] };
      }
    }

    if (process.platform === 'win32') {
      // 4. Try official Python Launcher (py.exe). It is NEVER hijacked by Microsoft Store WindowsApps!
      try {
        const pyVer = execSync('py -3 -c "import sys; print(sys.executable)"', {
          encoding: 'utf-8',
          timeout: 2500,
          stdio: ['ignore', 'pipe', 'ignore']
        }).trim();
        if (pyVer && !pyVer.toLowerCase().includes('windowsapps') && fs.existsSync(pyVer)) {
          this.addLog('system', `Detectado lanzador oficial 'py' enlazado a: ${pyVer}`);
          return { cmd: 'py', args: ['-3'] };
        }
      } catch (e) {}

      // 5. Query PowerShell for any real python that is NOT in WindowsApps
      try {
        const psOut = execSync(
          'powershell -NoProfile -Command "(Get-Command py, python3, python -ErrorAction SilentlyContinue | Where-Object { $_.Source -notmatch \'WindowsApps\' } | Select-Object -First 1).Source"',
          { encoding: 'utf-8', timeout: 3000, stdio: ['ignore', 'pipe', 'ignore'] }
        ).trim();

        if (psOut && !psOut.toLowerCase().includes('windowsapps') && fs.existsSync(psOut)) {
          this.addLog('system', `PowerShell detectó ejecutable real: ${psOut}`);
          return { cmd: psOut, args: [] };
        }
      } catch (e) {}

      // 6. Direct search in common Windows installations
      const userProfile = process.env.USERPROFILE || '';
      const localAppData = process.env.LOCALAPPDATA || path.join(userProfile, 'AppData', 'Local');
      const programFiles = process.env.ProgramFiles || 'C:\\Program Files';
      const programFilesX86 = process.env['ProgramFiles(x86)'] || 'C:\\Program Files (x86)';

      const searchPaths = [
        path.join(localAppData, 'Programs', 'Python', 'Python312', 'python.exe'),
        path.join(localAppData, 'Programs', 'Python', 'Python311', 'python.exe'),
        path.join(localAppData, 'Programs', 'Python', 'Python310', 'python.exe'),
        path.join(localAppData, 'Programs', 'Python', 'Python39', 'python.exe'),
        path.join(programFiles, 'Python312', 'python.exe'),
        path.join(programFiles, 'Python311', 'python.exe'),
        path.join(programFiles, 'Python310', 'python.exe'),
        path.join(programFiles, 'Python39', 'python.exe'),
        path.join(programFilesX86, 'Python311', 'python.exe'),
        path.join(programFilesX86, 'Python310', 'python.exe'),
        path.join(userProfile, 'anaconda3', 'python.exe'),
        path.join(userProfile, 'miniconda3', 'python.exe'),
        'C:\\ProgramData\\anaconda3\\python.exe',
        'C:\\ProgramData\\miniconda3\\python.exe',
        'C:\\Python312\\python.exe',
        'C:\\Python311\\python.exe',
        'C:\\Python310\\python.exe',
        'C:\\Python39\\python.exe'
      ];

      for (const p of searchPaths) {
        if (fs.existsSync(p)) {
          this.addLog('system', `Detectado Python en ruta estándar: ${p}`);
          return { cmd: p, args: [] };
        }
      }

      // 7. Test if 'python' in PATH is usable or if it's the Microsoft Store dummy alias
      try {
        const testOut = execSync('python -c "import sys; print(sys.version_info[0])"', {
          encoding: 'utf-8',
          timeout: 2000,
          stdio: ['ignore', 'pipe', 'pipe']
        }).trim();
        if (testOut === '3') {
          return { cmd: 'python', args: [] };
        }
      } catch (e) {
        // Ignored: it's the 9009 Windows Store fake alias or not found
      }

      // No valid Python found on Windows
      return null;
    }

    // POSIX (Linux / macOS)
    try {
      const out = execSync('which python3 || which python', { encoding: 'utf-8', timeout: 2000 }).trim();
      if (out) return { cmd: out, args: [] };
    } catch (e) {}

    return { cmd: 'python3', args: [] };
  }

  async start() {
    this.status = 'starting';
    this.addLog('system', `Iniciando gestor de backend local (Directorio base: ${this.basePath})...`);

    return new Promise((resolve) => {
      // 1. Check if backend is already running on port 8765
      const req = http.get('http://127.0.0.1:8765/api/health', (res) => {
        if (res.statusCode === 200) {
          this.status = 'running';
          this.addLog('system', 'Backend ya detectado y respondiendo en http://127.0.0.1:8765.');
          resolve(true);
        } else {
          this.spawnBackend(resolve);
        }
      });

      req.on('error', () => {
        this.spawnBackend(resolve);
      });

      req.setTimeout(1500, () => {
        req.destroy();
        this.spawnBackend(resolve);
      });
    });
  }

  spawnBackend(onReady) {
    try {
      const serverScript = path.join(this.basePath, 'backend', 'server.py');
      if (!fs.existsSync(serverScript)) {
        this.status = 'failed';
        this.errorMessage = `Script no encontrado: ${serverScript}`;
        this.addLog('system', `ERROR: No se encontró backend/server.py en: ${serverScript}`);
        onReady(false);
        return;
      }

      const pythonCmd = this.findPythonCommand();

      if (!pythonCmd) {
        this.status = 'no_python';
        this.errorMessage = 'No se encontró un entorno de Python 3 válido en el sistema (el comando "python" fue interceptado por el alias de Windows Store).';
        this.addLog('stderr', 'AVISO: Windows interceptó el comando con el alias de Microsoft Store (código 9009). No hay Python 3 accesible.');
        this.addLog('system', 'Solución: Puedes hacer clic en "Instalar Python con WinGet" o "Seleccionar ruta de python.exe" en la Consola DevTools.');
        onReady(false);
        return;
      }

      this.resolvedPython = pythonCmd;
      const { cmd, args } = pythonCmd;
      const fullCmdString = `${cmd} ${args.concat(serverScript).join(' ')}`;
      this.addLog('system', `Ejecutando: ${fullCmdString}`);

      this.process = spawn(cmd, [...args, serverScript], {
        cwd: this.basePath,
        env: {
          ...process.env,
          PYTHONUNBUFFERED: '1',
          PYTHONIOENCODING: 'utf-8'
        },
        stdio: ['ignore', 'pipe', 'pipe']
      });

      let resolved = false;

      this.process.on('error', (err) => {
        this.status = 'failed';
        this.errorMessage = `Error al ejecutar ${cmd}: ${err.message}`;
        this.addLog('stderr', `Fallo al lanzar Python (${cmd}): ${err.message}`);
        if (!resolved) {
          resolved = true;
          onReady(false);
        }
      });

      this.process.stdout?.on('data', (data) => {
        const str = data.toString();
        this.addLog('stdout', str);
        if (str.includes('Uvicorn running') || str.includes('Application startup complete') || str.includes('127.0.0.1:8765')) {
          this.status = 'running';
          if (!resolved) {
            resolved = true;
            onReady(true);
          }
        }
      });

      this.process.stderr?.on('data', (data) => {
        const str = data.toString();
        this.addLog('stderr', str);
        if (str.includes('Uvicorn running') || str.includes('Application startup complete')) {
          this.status = 'running';
          if (!resolved) {
            resolved = true;
            onReady(true);
          }
        }
      });

      this.process.on('exit', (code, signal) => {
        this.addLog('system', `Proceso backend finalizó (código: ${code}, señal: ${signal})`);
        if (this.status !== 'running') {
          this.status = 'failed';
        }
        if (!resolved) {
          resolved = true;
          onReady(false);
        }
      });

      // Fallback timeout: wait up to 10 seconds for backend to start
      setTimeout(() => {
        if (!resolved) {
          resolved = true;
          http.get('http://127.0.0.1:8765/api/health', (res) => {
            if (res.statusCode === 200) {
              this.status = 'running';
              this.addLog('system', 'Backend respondiendo con éxito.');
              onReady(true);
            } else {
              onReady(false);
            }
          }).on('error', () => {
            this.addLog('system', 'Esperando que el backend FastAPI responda...');
            onReady(false);
          });
        }
      }, 9000);
    } catch (e) {
      this.status = 'failed';
      this.errorMessage = e.message;
      this.addLog('stderr', `Excepción al iniciar backend: ${e.message}`);
      onReady(false);
    }
  }

  // Set and persist a user-selected Python executable
  async setCustomPython(selectedPath) {
    if (!selectedPath || !fs.existsSync(selectedPath)) {
      return { success: false, error: 'La ruta seleccionada no existe.' };
    }

    this.saveCustomPython(selectedPath);
    this.addLog('system', `Nueva ruta de Python asignada: ${selectedPath}`);
    this.stop();
    const ok = await this.start();
    return { success: ok, path: selectedPath };
  }

  // Automatic installer via WinGet on Windows 10/11
  async installViaWinGet() {
    this.addLog('system', 'Iniciando instalación automática de Python 3.11 mediante Windows Package Manager (WinGet)...');
    return new Promise((resolve) => {
      try {
        const winget = spawn('winget', [
          'install',
          '-e',
          '--id',
          'Python.Python.3.11',
          '--accept-package-agreements',
          '--accept-source-agreements'
        ], {
          shell: true,
          stdio: ['ignore', 'pipe', 'pipe']
        });

        winget.stdout?.on('data', (data) => {
          this.addLog('stdout', `[WinGet] ${data.toString()}`);
        });

        winget.stderr?.on('data', (data) => {
          this.addLog('stderr', `[WinGet] ${data.toString()}`);
        });

        winget.on('close', async (code) => {
          if (code === 0) {
            this.addLog('system', '¡Python 3.11 instalado con éxito! Reiniciando backend...');
            // Wait 2 seconds for PATH refresh
            setTimeout(async () => {
              this.stop();
              const restarted = await this.start();
              resolve({ success: restarted });
            }, 2500);
          } else {
            this.addLog('stderr', `WinGet finalizó con código: ${code}`);
            resolve({ success: false, error: `Código de salida: ${code}` });
          }
        });

        winget.on('error', (err) => {
          this.addLog('stderr', `Error al ejecutar winget: ${err.message}`);
          resolve({ success: false, error: err.message });
        });
      } catch (e) {
        this.addLog('stderr', `Excepción al iniciar winget: ${e.message}`);
        resolve({ success: false, error: e.message });
      }
    });
  }

  // Download official portable Python 3.11 embeddable archive directly
  async downloadPortablePython() {
    this.addLog('system', 'Iniciando descarga directa de Python 3.11 Portable Embebido (64-bit)...');
    const targetDir = path.join(this.configDir, 'python');
    if (!fs.existsSync(targetDir)) {
      fs.mkdirSync(targetDir, { recursive: true });
    }
    const zipPath = path.join(this.configDir, 'python-3.11.9-embed-amd64.zip');
    const url = 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip';

    return new Promise((resolve) => {
      const https = require('https');
      const file = fs.createWriteStream(zipPath);

      const doDownload = (downloadUrl) => {
        https.get(downloadUrl, (res) => {
          if (res.statusCode === 301 || res.statusCode === 302) {
            return doDownload(res.headers.location);
          }
          if (res.statusCode !== 200) {
            this.addLog('stderr', `Error en descarga de Python: HTTP ${res.statusCode}`);
            return resolve({ success: false, error: `HTTP ${res.statusCode}` });
          }

          res.pipe(file);
          file.on('finish', () => {
            file.close(async () => {
              this.addLog('system', 'Descarga completada (~10 MB). Extrayendo Python Portable...');
              try {
                try {
                  execSync(`tar -xf "${zipPath}" -C "${targetDir}"`, { timeout: 30000 });
                } catch (e) {
                  execSync(`powershell -NoProfile -Command "Expand-Archive -Path '${zipPath}' -DestinationPath '${targetDir}' -Force"`, { timeout: 30000 });
                }

                try { fs.unlinkSync(zipPath); } catch (e) {}

                // Enable site-packages in python311._pth
                const pth = path.join(targetDir, 'python311._pth');
                if (fs.existsSync(pth)) {
                  let pthContent = fs.readFileSync(pth, 'utf-8');
                  pthContent = pthContent.replace(/#import site/g, 'import site');
                  if (!pthContent.includes('import site')) pthContent += '\nimport site\n';
                  if (!pthContent.includes('Lib\\site-packages')) pthContent += 'Lib\\site-packages\n';
                  fs.writeFileSync(pth, pthContent, 'utf-8');
                }

                const pythonExe = path.join(targetDir, 'python.exe');
                if (fs.existsSync(pythonExe)) {
                  this.addLog('system', `¡Python Portable integrado con éxito en: ${pythonExe}!`);
                  await this.setCustomPython(pythonExe);
                  resolve({ success: true, path: pythonExe });
                } else {
                  resolve({ success: false, error: 'No se encontró python.exe tras descomprimir' });
                }
              } catch (err) {
                this.addLog('stderr', `Error al descomprimir: ${err.message}`);
                resolve({ success: false, error: err.message });
              }
            });
          });
        }).on('error', (err) => {
          this.addLog('stderr', `Fallo al descargar Python: ${err.message}`);
          resolve({ success: false, error: err.message });
        });
      };

      doDownload(url);
    });
  }

  stop() {
    if (this.process) {
      try {
        this.addLog('system', 'Deteniendo backend...');
        this.process.kill();
      } catch (e) {}
      this.process = null;
      this.status = 'idle';
    }
  }
}

module.exports = BackendManager;

const { spawn, execSync } = require('child_process');
const path = require('path');
const http = require('http');
const https = require('https');
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
      const appData =
        process.env.APPDATA ||
        (process.platform === 'win32' && process.env.USERPROFILE
          ? path.join(process.env.USERPROFILE, 'AppData', 'Roaming')
          : null);
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

  downloadFileHelper(url, dest) {
    return new Promise((resolve, reject) => {
      const file = fs.createWriteStream(dest);
      const req = https.get(url, { headers: { 'User-Agent': 'AgenteStudio/1.0' } }, (res) => {
        if (res.statusCode === 301 || res.statusCode === 302 || res.statusCode === 307) {
          file.close();
          return this.downloadFileHelper(res.headers.location, dest).then(resolve).catch(reject);
        }
        if (res.statusCode !== 200) {
          file.close();
          return reject(new Error(`HTTP ${res.statusCode}`));
        }
        res.pipe(file);
        file.on('finish', () => {
          file.close(() => resolve(true));
        });
      });
      req.on('error', (err) => {
        fs.unlink(dest, () => {});
        reject(err);
      });
    });
  }

  // Ensure python311._pth has site-packages and basePath enabled
  configurePthFile(pythonExePath) {
    try {
      const pyDir = path.dirname(pythonExePath);
      const pthFiles = fs.readdirSync(pyDir).filter((f) => f.endsWith('._pth'));
      for (const pthName of pthFiles) {
        const pthPath = path.join(pyDir, pthName);
        let content = fs.readFileSync(pthPath, 'utf-8');
        content = content.replace(/#import site/g, 'import site');
        if (!content.includes('import site')) content += '\nimport site\n';
        if (!content.includes('Lib\\site-packages')) content += 'Lib\\site-packages\n';
        if (!content.includes(this.basePath)) content += `${this.basePath}\n`;
        fs.writeFileSync(pthPath, content, 'utf-8');
      }
      const sitePkg = path.join(pyDir, 'Lib', 'site-packages');
      if (!fs.existsSync(sitePkg)) {
        fs.mkdirSync(sitePkg, { recursive: true });
      }
    } catch (e) {}
  }

  // Automatically verify and install pip + backend/requirements.txt if missing
  async ensurePythonDependencies(pythonCmd) {
    const { cmd, args } = pythonCmd;
    const reqFile = path.join(this.basePath, 'backend', 'requirements.txt');
    if (!fs.existsSync(reqFile)) return true;

    if (fs.existsSync(cmd)) {
      this.configurePthFile(cmd);
    }

    // 1. Check if fastapi and uvicorn are already importable
    try {
      const checkArgs = [...args, '-c', 'import fastapi, uvicorn, pydantic, requests; print("OK")'];
      const out = execSync(`"${cmd}" ${checkArgs.map((a) => `"${a}"`).join(' ')}`, {
        cwd: this.basePath,
        encoding: 'utf-8',
        timeout: 5000,
        stdio: ['ignore', 'pipe', 'pipe']
      }).trim();
      if (out.includes('OK')) {
        return true;
      }
    } catch (e) {
      this.addLog('system', 'Detectadas librerías de backend pendientes de instalar en este entorno Python. Preparando instalación automática...');
    }

    // 2. Check if pip is installed; if not, bootstrap get-pip.py
    let hasPip = false;
    try {
      execSync(`"${cmd}" ${args.join(' ')} -m pip --version`, {
        cwd: this.basePath,
        stdio: ['ignore', 'pipe', 'pipe'],
        timeout: 5000
      });
      hasPip = true;
    } catch (e) {
      hasPip = false;
    }

    if (!hasPip) {
      try {
        this.addLog('system', 'Descargando gestor de paquetes oficial (get-pip.py)...');
        const getPipPath = path.join(this.configDir || this.basePath, 'get-pip.py');
        await this.downloadFileHelper('https://bootstrap.pypa.io/get-pip.py', getPipPath);
        this.addLog('system', 'Activando pip en el entorno Python...');
        await new Promise((resolve) => {
          const proc = spawn(cmd, [...args, getPipPath, '--no-warn-script-location'], {
            cwd: this.basePath,
            stdio: ['ignore', 'pipe', 'pipe']
          });
          proc.stdout?.on('data', (d) => this.addLog('stdout', `[pip-setup] ${d.toString()}`));
          proc.stderr?.on('data', (d) => this.addLog('stderr', `[pip-setup] ${d.toString()}`));
          proc.on('close', () => resolve());
          proc.on('error', () => resolve());
        });
        try {
          fs.unlinkSync(getPipPath);
        } catch (e) {}
      } catch (err) {
        this.addLog('stderr', `Error al inicializar pip: ${err.message}`);
      }
    }

    // 3. Install backend/requirements.txt
    this.addLog('system', 'Instalando paquetes del proyecto (FastAPI, Uvicorn, OpenPyXL, Docx, PPTX, Requests)...');
    return new Promise((resolve) => {
      const pipProc = spawn(cmd, [...args, '-m', 'pip', 'install', '-r', reqFile, '--no-warn-script-location'], {
        cwd: this.basePath,
        stdio: ['ignore', 'pipe', 'pipe']
      });
      pipProc.stdout?.on('data', (d) => this.addLog('stdout', `[pip] ${d.toString()}`));
      pipProc.stderr?.on('data', (d) => this.addLog('stderr', `[pip] ${d.toString()}`));
      pipProc.on('close', (code) => {
        if (code === 0) {
          this.addLog('system', '¡Librerías del backend instaladas correctamente!');
          resolve(true);
        } else {
          this.addLog('stderr', `Instalación de pip finalizó con código ${code}`);
          resolve(false);
        }
      });
      pipProc.on('error', (err) => {
        this.addLog('stderr', `Error ejecutando pip: ${err.message}`);
        resolve(false);
      });
    });
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

    // 3. Tuned Local Inference Runtime & Bundled Portable Python
    const userProfile = process.env.USERPROFILE || '';
    const agenteStudioHome = userProfile ? path.join(userProfile, 'AgenteStudio') : null;

    const tunedCandidates = [
      path.join(this.basePath, 'runtime', 'python.exe'),
      path.join(this.basePath, 'runtime', 'Scripts', 'python.exe'),
      path.join(this.basePath, '..', 'runtime', 'python.exe'),
      path.join(this.basePath, '..', 'runtime', 'Scripts', 'python.exe'),
      path.join(this.basePath, 'venv', 'Scripts', 'python.exe'),
      path.join(this.basePath, '..', 'venv', 'Scripts', 'python.exe'),
      path.join(this.basePath, 'python', 'python.exe'),
      path.join(this.basePath, '..', 'python', 'python.exe'),
      agenteStudioHome ? path.join(agenteStudioHome, 'runtime', 'python.exe') : null,
      agenteStudioHome ? path.join(agenteStudioHome, 'python', 'python.exe') : null,
      this.configDir ? path.join(this.configDir, 'runtime', 'python.exe') : null,
      this.configDir ? path.join(this.configDir, 'python', 'python.exe') : null
    ].filter(Boolean);

    for (const p of tunedCandidates) {
      if (fs.existsSync(p)) {
        this.addLog('system', `[Runtime Integrado] Detectado entorno Python del proyecto en: ${p}`);
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
          return { cmd: pyVer, args: [] };
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
      } catch (e) {}

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

  async spawnBackend(onReady) {
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
        this.errorMessage =
          'No se encontró un entorno de Python 3 válido en el sistema (el comando "python" fue interceptado por el alias de Windows Store).';
        this.addLog(
          'stderr',
          'AVISO: Windows interceptó el comando con el alias de Microsoft Store (código 9009). No hay Python 3 accesible.'
        );
        this.addLog(
          'system',
          'Solución: Haz clic en "Descargar Python 3.11 Portable (Integrado)" en la Consola DevTools para descargar e instalar automáticamente Python + todas las librerías del proyecto.'
        );
        onReady(false);
        return;
      }

      this.resolvedPython = pythonCmd;

      // Ensure pip and backend/requirements.txt are installed in this Python before running server.py!
      await this.ensurePythonDependencies(pythonCmd);

      const { cmd, args } = pythonCmd;
      const fullCmdString = `${cmd} ${args.concat(serverScript).join(' ')}`;
      this.addLog('system', `Ejecutando: ${fullCmdString}`);

      this.process = spawn(cmd, [...args, serverScript], {
        cwd: this.basePath,
        env: {
          ...process.env,
          PYTHONPATH: this.basePath,
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
        if (
          str.includes('Uvicorn running') ||
          str.includes('Application startup complete') ||
          str.includes('127.0.0.1:8765')
        ) {
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

      // Fallback timeout: wait up to 12 seconds for backend to start
      setTimeout(() => {
        if (!resolved) {
          resolved = true;
          http
            .get('http://127.0.0.1:8765/api/health', (res) => {
              if (res.statusCode === 200) {
                this.status = 'running';
                this.addLog('system', 'Backend respondiendo con éxito.');
                onReady(true);
              } else {
                onReady(false);
              }
            })
            .on('error', () => {
              this.addLog('system', 'Esperando que el backend FastAPI responda...');
              onReady(false);
            });
        }
      }, 12000);
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
        const winget = spawn(
          'winget',
          ['install', '-e', '--id', 'Python.Python.3.11', '--accept-package-agreements', '--accept-source-agreements'],
          {
            shell: true,
            stdio: ['ignore', 'pipe', 'pipe']
          }
        );

        winget.stdout?.on('data', (data) => {
          this.addLog('stdout', `[WinGet] ${data.toString()}`);
        });

        winget.stderr?.on('data', (data) => {
          this.addLog('stderr', `[WinGet] ${data.toString()}`);
        });

        winget.on('close', async (code) => {
          if (code === 0) {
            this.addLog('system', '¡Python 3.11 instalado con éxito! Instalando dependencias y reiniciando backend...');
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

  // Download official portable Python 3.11 embeddable archive + pip + requirements.txt
  async downloadPortablePython() {
    this.addLog('system', 'Iniciando descarga de Python 3.11 Portable + Librerías del Proyecto...');
    const targetDir = path.join(this.configDir, 'python');
    if (!fs.existsSync(targetDir)) {
      fs.mkdirSync(targetDir, { recursive: true });
    }
    const zipPath = path.join(this.configDir, 'python-3.11.9-embed-amd64.zip');
    const url = 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip';

    try {
      const pythonExe = path.join(targetDir, 'python.exe');
      if (!fs.existsSync(pythonExe)) {
        await this.downloadFileHelper(url, zipPath);
        this.addLog('system', 'Descarga de Python Portable completada (~10 MB). Extrayendo...');
        try {
          execSync(`tar -xf "${zipPath}" -C "${targetDir}"`, { timeout: 30000 });
        } catch (e) {
          execSync(
            `powershell -NoProfile -Command "Expand-Archive -Path '${zipPath}' -DestinationPath '${targetDir}' -Force"`,
            { timeout: 30000 }
          );
        }
        try {
          fs.unlinkSync(zipPath);
        } catch (e) {}
      }

      if (!fs.existsSync(pythonExe)) {
        return { success: false, error: 'No se encontró python.exe tras descomprimir' };
      }

      // Configure python311._pth and install pip + backend/requirements.txt
      this.configurePthFile(pythonExe);
      this.addLog('system', 'Configurando pip e instalando librerías del backend (FastAPI, Uvicorn, Office)...');
      await this.ensurePythonDependencies({ cmd: pythonExe, args: [] });

      this.addLog('system', `¡Entorno Python Portable + Dependencias listo en: ${pythonExe}!`);
      await this.setCustomPython(pythonExe);
      return { success: true, path: pythonExe };
    } catch (err) {
      this.addLog('stderr', `Error preparando Python Portable: ${err.message}`);
      return { success: false, error: err.message };
    }
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

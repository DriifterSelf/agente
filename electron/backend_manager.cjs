const { spawn } = require('child_process');
const path = require('path');
const http = require('http');
const fs = require('fs');

class BackendManager {
  constructor(basePath) {
    this.basePath = basePath;
    this.process = null;
    this.logs = [];
    this.status = 'idle'; // idle | starting | running | failed
    this.errorMessage = null;
    this.mainWindow = null;
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
      if (this.logs.length > 500) this.logs.shift();
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
      logCount: this.logs.length
    };
  }

  // Detect working Python executable on Windows / Linux / macOS
  findPythonCommand() {
    if (process.env.PYTHON && fs.existsSync(process.env.PYTHON)) {
      return { cmd: process.env.PYTHON, args: [] };
    }

    // Common standard candidates
    const candidates = ['python', 'py', 'python3'];

    if (process.platform === 'win32') {
      const userProfile = process.env.USERPROFILE || '';
      const localAppData = process.env.LOCALAPPDATA || path.join(userProfile, 'AppData', 'Local');
      const programFiles = process.env.ProgramFiles || 'C:\\Program Files';
      
      const winPaths = [
        path.join(localAppData, 'Programs', 'Python', 'Python312', 'python.exe'),
        path.join(localAppData, 'Programs', 'Python', 'Python311', 'python.exe'),
        path.join(localAppData, 'Programs', 'Python', 'Python310', 'python.exe'),
        path.join(localAppData, 'Programs', 'Python', 'Python39', 'python.exe'),
        path.join(programFiles, 'Python312', 'python.exe'),
        path.join(programFiles, 'Python311', 'python.exe'),
        path.join(programFiles, 'Python310', 'python.exe'),
      ];

      for (const p of winPaths) {
        if (fs.existsSync(p)) {
          return { cmd: p, args: [] };
        }
      }
    }

    return { cmd: 'python', args: [] };
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

      const { cmd, args } = this.findPythonCommand();
      this.addLog('system', `Ejecutando: ${cmd} ${args.concat(serverScript).join(' ')}`);

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
        this.addLog('system', 'Sugerencia: Asegúrate de que Python 3.10+ esté instalado y en el PATH de Windows.');
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
          // Test health check one more time
          http.get('http://127.0.0.1:8765/api/health', (res) => {
            if (res.statusCode === 200) {
              this.status = 'running';
              this.addLog('system', 'Backend respondiendo con éxito.');
              onReady(true);
            } else {
              onReady(false);
            }
          }).on('error', () => {
            this.addLog('system', 'Timeout esperando que el backend uvicorn responda.');
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

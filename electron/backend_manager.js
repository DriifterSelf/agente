const { spawn } = require('child_process');
const path = require('path');
const http = require('http');
const fs = require('fs');

class BackendManager {
  constructor(appPath) {
    const hasResBackend = process.resourcesPath && fs.existsSync(path.join(process.resourcesPath, 'backend', 'server.py'));
    this.appPath = hasResBackend ? path.resolve(process.resourcesPath) : path.resolve(appPath);
    this.process = null;
    this.port = 8765;
  }

  start() {
    return new Promise((resolve) => {
      const isWin = process.platform === 'win32';
      const embeddedPy = path.join(this.appPath, 'runtime', 'python', 'python.exe');
      const venvPy = isWin
        ? path.join(this.appPath, 'venv', 'Scripts', 'python.exe')
        : path.join(this.appPath, 'venv', 'bin', 'python');
      const pythonExe = fs.existsSync(embeddedPy) ? embeddedPy : venvPy;

      const serverScript = path.join(this.appPath, 'backend', 'server.py');
      const logFile = path.join(this.appPath, 'backend.log');
      const logStream = fs.createWriteStream(logFile, { flags: 'a' });

      logStream.write(`\n--- [${new Date().toISOString()}] Starting Backend ---\n`);
      logStream.write(`Path: ${this.appPath}\nPython: ${pythonExe}\nScript: ${serverScript}\n`);

      this.process = spawn(pythonExe, [serverScript], {
        cwd: this.appPath,
        windowsHide: true,
        env: {
          ...process.env,
          PYTHONPATH: this.appPath,
          PYTHONUNBUFFERED: '1'
        },
        stdio: ['ignore', 'pipe', 'pipe']
      });

      this.process.stdout.pipe(logStream);
      this.process.stderr.pipe(logStream);

      this.process.on('error', (err) => {
        logStream.write(`[BackendManager] Spawn error: ${err.message}\n`);
      });

      this.process.on('close', (code) => {
        logStream.write(`[BackendManager] Process exited with code ${code}\n`);
      });

      let attempts = 0;
      const maxAttempts = 30;
      const interval = setInterval(() => {
        attempts++;
        const req = http.get(`http://127.0.0.1:${this.port}/api/health`, (res) => {
          if (res.statusCode === 200) {
            clearInterval(interval);
            logStream.write('[BackendManager] Health check OK. Server ready.\n');
            resolve();
          }
        });

        req.on('error', () => {
          if (attempts >= maxAttempts) {
            clearInterval(interval);
            logStream.write('[BackendManager] Warning: Health check timed out.\n');
            resolve();
          }
        });
      }, 500);
    });
  }

  stop() {
    if (this.process) {
      try {
        if (process.platform === 'win32') {
          spawn('taskkill', ['/pid', this.process.pid, '/f', '/t'], { windowsHide: true });
        } else {
          this.process.kill('SIGTERM');
        }
      } catch (err) {
        console.error('[BackendManager] Error killing backend:', err);
      }
      this.process = null;
    }
  }
}

module.exports = BackendManager;
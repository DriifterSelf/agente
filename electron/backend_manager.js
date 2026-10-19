const { spawn } = require('child_process');
const path = require('path');
const http = require('http');

class BackendManager {
  constructor(appPath) {
    this.appPath = appPath;
    this.process = null;
    this.port = 8765;
  }

  start() {
    return new Promise((resolve, reject) => {
      const isWin = process.platform === 'win32';
      const pythonExe = isWin
        ? path.join(this.appPath, 'venv', 'Scripts', 'python.exe')
        : path.join(this.appPath, 'venv', 'bin', 'python');

      const serverScript = path.join(this.appPath, 'backend', 'server.py');

      console.log(`[BackendManager] Starting backend: ${pythonExe} ${serverScript}`);

      // Spawning with windowsHide: true ensures NO black terminal window opens on Windows!
      this.process = spawn(pythonExe, [serverScript], {
        cwd: this.appPath,
        windowsHide: true,
        stdio: ['ignore', 'pipe', 'pipe']
      });

      this.process.stdout.on('data', (data) => {
        const msg = data.toString();
        // console.log(`[Backend stdout] ${msg}`);
      });

      this.process.stderr.on('data', (data) => {
        const msg = data.toString();
        // console.error(`[Backend stderr] ${msg}`);
      });

      this.process.on('close', (code) => {
        console.log(`[BackendManager] Python backend exited with code ${code}`);
      });

      // Poll until server is ready
      let attempts = 0;
      const maxAttempts = 30; // 15 seconds
      const interval = setInterval(() => {
        attempts++;
        const req = http.get(`http://127.0.0.1:${this.port}/api/health`, (res) => {
          if (res.statusCode === 200) {
            clearInterval(interval);
            console.log('[BackendManager] Backend is ready and responding on port', this.port);
            resolve();
          }
        });

        req.on('error', () => {
          if (attempts >= maxAttempts) {
            clearInterval(interval);
            console.warn('[BackendManager] Backend health check timed out. Proceeding anyway.');
            resolve();
          }
        });
      }, 500);
    });
  }

  stop() {
    if (this.process) {
      console.log('[BackendManager] Stopping Python backend process...');
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

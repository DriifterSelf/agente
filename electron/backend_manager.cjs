const { spawn } = require('child_process');
const path = require('path');
const http = require('http');

class BackendManager {
  constructor(basePath) {
    this.basePath = basePath;
    this.process = null;
  }

  async start() {
    return new Promise((resolve) => {
      // Check if backend is already running
      http.get('http://127.0.0.1:8765/api/health', (res) => {
        if (res.statusCode === 200) {
          resolve(true);
        }
      }).on('error', () => {
        this.spawnBackend(resolve);
      });
    });
  }

  spawnBackend(onReady) {
    try {
      const serverScript = path.join(this.basePath, 'backend', 'server.py');
      this.process = spawn('python', [serverScript], {
        cwd: this.basePath,
        stdio: 'pipe'
      });

      this.process.stdout?.on('data', (data) => {
        const str = data.toString();
        if (str.includes('Uvicorn running') || str.includes('Application startup complete')) {
          onReady(true);
        }
      });

      setTimeout(() => onReady(false), 8000);
    } catch (e) {
      onReady(false);
    }
  }

  stop() {
    if (this.process) {
      try {
        this.process.kill();
      } catch (e) {}
      this.process = null;
    }
  }
}

module.exports = BackendManager;

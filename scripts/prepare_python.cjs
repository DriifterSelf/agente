/**
 * Script para descargar y preparar los binarios de Python 3.11 Portable Embebido
 * para empaquetado autónomo en Windows (Electron Builder).
 */
const fs = require('fs');
const path = require('path');
const https = require('https');
const { execSync } = require('child_process');

const ROOT_DIR = path.resolve(__dirname, '..');
const PYTHON_DIR = path.join(ROOT_DIR, 'python');
const PYTHON_ZIP_URL = 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip';
const ZIP_PATH = path.join(ROOT_DIR, 'python-embed.zip');

function downloadFile(url, dest) {
  return new Promise((resolve, reject) => {
    console.log(`[Python Bundler] Descargando Python embeddable desde: ${url}`);
    const file = fs.createWriteStream(dest);
    
    https.get(url, (response) => {
      // Handle redirects
      if (response.statusCode === 301 || response.statusCode === 302) {
        return downloadFile(response.headers.location, dest).then(resolve).catch(reject);
      }
      if (response.statusCode !== 200) {
        return reject(new Error(`Fallo en la descarga HTTP: código ${response.statusCode}`));
      }

      response.pipe(file);
      file.on('finish', () => {
        file.close(() => {
          console.log('[Python Bundler] Descarga completada con éxito.');
          resolve(true);
        });
      });
    }).on('error', (err) => {
      fs.unlink(dest, () => {});
      reject(err);
    });
  });
}

async function preparePython() {
  try {
    if (!fs.existsSync(PYTHON_DIR)) {
      fs.mkdirSync(PYTHON_DIR, { recursive: true });
    }

    const pythonExe = path.join(PYTHON_DIR, 'python.exe');
    if (fs.existsSync(pythonExe)) {
      console.log(`[Python Bundler] Binarios de Python ya presentes en: ${pythonExe}`);
    } else {
      // Check if running on GitHub Actions or Windows with pythonLocation
      if (process.env.pythonLocation && fs.existsSync(path.join(process.env.pythonLocation, 'python.exe'))) {
        console.log(`[Python Bundler] Copiando Python desde el runner de GitHub Actions: ${process.env.pythonLocation}`);
        try {
          execSync(`robocopy "${process.env.pythonLocation}" "${PYTHON_DIR}" /E /XF *.pdb /R:2 /W:2`, { stdio: 'inherit' });
        } catch (e) {
          // Robocopy returns exit code 1-3 on successful copy
        }
      } else {
        // Download official embeddable zip
        await downloadFile(PYTHON_ZIP_URL, ZIP_PATH);
        console.log('[Python Bundler] Extrayendo paquete embebido...');

        // Extract using tar (standard in modern Windows, Linux and macOS)
        try {
          execSync(`tar -xf "${ZIP_PATH}" -C "${PYTHON_DIR}"`, { stdio: 'inherit' });
        } catch (e) {
          execSync(`powershell -NoProfile -Command "Expand-Archive -Path '${ZIP_PATH}' -DestinationPath '${PYTHON_DIR}' -Force"`, { stdio: 'inherit' });
        }

        if (fs.existsSync(ZIP_PATH)) {
          fs.unlinkSync(ZIP_PATH);
        }
      }
    }

    // Configure python311._pth to enable import site and site-packages
    const pthFile = path.join(PYTHON_DIR, 'python311._pth');
    if (fs.existsSync(pthFile)) {
      console.log('[Python Bundler] Habilitando soporte de site-packages en python311._pth...');
      let content = fs.readFileSync(pthFile, 'utf-8');
      content = content.replace(/#import site/g, 'import site');
      if (!content.includes('import site')) {
        content += '\nimport site\n';
      }
      if (!content.includes('Lib\\site-packages')) {
        content = 'python311.zip\n.\nLib\\site-packages\nLib\nimport site\n';
      }
      fs.writeFileSync(pthFile, content, 'utf-8');
    }

    // Ensure Lib/site-packages directory exists
    const sitePackages = path.join(PYTHON_DIR, 'Lib', 'site-packages');
    if (!fs.existsSync(sitePackages)) {
      fs.mkdirSync(sitePackages, { recursive: true });
    }

    // Install backend requirements into Python site-packages if pip is available
    const reqFile = path.join(ROOT_DIR, 'backend', 'requirements.txt');
    if (fs.existsSync(reqFile)) {
      console.log('[Python Bundler] Instalando dependencias del backend en el runtime embebido...');
      try {
        execSync(`pip install -r "${reqFile}" --target "${sitePackages}" --no-warn-script-location`, { stdio: 'inherit' });
      } catch (err) {
        console.log('[Python Bundler] Pip no disponible en este entorno, se usará el entorno del sistema o instalación en vivo.');
      }
    }

    console.log('[Python Bundler] Preparación de Python embebido finalizada correctamente.');
  } catch (err) {
    console.error('[Python Bundler] Error al preparar Python:', err);
    // Keep directory created so electron-builder doesn't fail
    if (!fs.existsSync(PYTHON_DIR)) {
      fs.mkdirSync(PYTHON_DIR, { recursive: true });
    }
  }
}

preparePython();

/**
 * Script para descargar y preparar:
 * 1. Python 3.11 Portable Embebido + pip + todas las dependencias de backend/requirements.txt
 * 2. Motor de inferencia nativo llama.cpp (runtime/llama-server.exe con soporte GPU CUDA/Vulkan)
 * para empaquetado autónomo en Windows (Electron Builder).
 */
const fs = require('fs');
const path = require('path');
const https = require('https');
const { execSync } = require('child_process');

const ROOT_DIR = path.resolve(__dirname, '..');
const PYTHON_DIR = path.join(ROOT_DIR, 'python');
const RUNTIME_DIR = path.join(ROOT_DIR, 'runtime');
const PYTHON_ZIP_URL = 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip';
const GET_PIP_URL = 'https://bootstrap.pypa.io/get-pip.py';
const ZIP_PATH = path.join(ROOT_DIR, 'python-embed.zip');
const GET_PIP_PATH = path.join(PYTHON_DIR, 'get-pip.py');

function downloadFile(url, dest) {
  return new Promise((resolve, reject) => {
    console.log(`[Bundler] Descargando desde: ${url}`);
    const file = fs.createWriteStream(dest);

    const request = https.get(
      url,
      { headers: { 'User-Agent': 'AgenteStudio-Builder/1.0' } },
      (response) => {
        if (response.statusCode === 301 || response.statusCode === 302 || response.statusCode === 307) {
          file.close();
          return downloadFile(response.headers.location, dest).then(resolve).catch(reject);
        }
        if (response.statusCode !== 200) {
          file.close();
          return reject(new Error(`Fallo HTTP ${response.statusCode} al descargar ${url}`));
        }

        response.pipe(file);
        file.on('finish', () => {
          file.close(() => resolve(true));
        });
      }
    );

    request.on('error', (err) => {
      fs.unlink(dest, () => {});
      reject(err);
    });
  });
}

function fetchJson(url) {
  return new Promise((resolve, reject) => {
    https
      .get(url, { headers: { 'User-Agent': 'AgenteStudio-Builder/1.0', Accept: 'application/vnd.github+json' } }, (res) => {
        if (res.statusCode === 301 || res.statusCode === 302) {
          return fetchJson(res.headers.location).then(resolve).catch(reject);
        }
        let body = '';
        res.on('data', (chunk) => (body += chunk));
        res.on('end', () => {
          try {
            resolve(JSON.parse(body));
          } catch (e) {
            reject(e);
          }
        });
      })
      .on('error', reject);
  });
}

function extractZip(zipPath, targetDir) {
  try {
    execSync(`tar -xf "${zipPath}" -C "${targetDir}"`, { stdio: 'inherit' });
  } catch (e) {
    execSync(
      `powershell -NoProfile -Command "Expand-Archive -Path '${zipPath}' -DestinationPath '${targetDir}' -Force"`,
      { stdio: 'inherit' }
    );
  }
}

async function prepareLlamaRuntime() {
  try {
    if (!fs.existsSync(RUNTIME_DIR)) {
      fs.mkdirSync(RUNTIME_DIR, { recursive: true });
    }

    const llamaServerExe = path.join(RUNTIME_DIR, 'llama-server.exe');
    if (fs.existsSync(llamaServerExe)) {
      console.log(`[Runtime Bundler] llama-server.exe ya presente en: ${llamaServerExe}`);
      return;
    }

    console.log('[Runtime Bundler] Consultando última versión oficial de ggml-org/llama.cpp para Windows (GPU)...');
    const release = await fetchJson('https://api.github.com/repos/ggml-org/llama.cpp/releases/latest');
    const assets = Array.isArray(release.assets) ? release.assets : [];

    // Prefer Vulkan x64 binary (supports both NVIDIA RTX 4070 and AMD RX 9070 XT out-of-the-box without 4GB CUDA redist)
    let targetAsset =
      assets.find((a) => /bin-win-vulkan-x64\.zip$/i.test(a.name)) ||
      assets.find((a) => /bin-win-cuda.*-x64\.zip$/i.test(a.name) && !/cudart/i.test(a.name)) ||
      assets.find((a) => /bin-win-avx2-x64\.zip$/i.test(a.name));

    if (!targetAsset || !targetAsset.browser_download_url) {
      console.log('[Runtime Bundler] No se encontró asset precompilado en la consulta; se descargará bajo demanda al iniciar.');
      return;
    }

    const runtimeZip = path.join(ROOT_DIR, 'llama-runtime.zip');
    await downloadFile(targetAsset.browser_download_url, runtimeZip);
    console.log(`[Runtime Bundler] Extrayendo ${targetAsset.name} en ${RUNTIME_DIR}...`);
    extractZip(runtimeZip, RUNTIME_DIR);

    if (fs.existsSync(runtimeZip)) {
      fs.unlinkSync(runtimeZip);
    }

    // Si el zip extrajo una subcarpeta (ej. build/bin/*), mover ejecutables y DLLs a la raíz de runtime/
    if (!fs.existsSync(llamaServerExe)) {
      const findAndFlatten = (dir) => {
        for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
          const fullPath = path.join(dir, entry.name);
          if (entry.isDirectory()) {
            findAndFlatten(fullPath);
          } else if (/\.(exe|dll)$/i.test(entry.name)) {
            const destPath = path.join(RUNTIME_DIR, entry.name);
            if (fullPath !== destPath && !fs.existsSync(destPath)) {
              fs.copyFileSync(fullPath, destPath);
            }
          }
        }
      };
      findAndFlatten(RUNTIME_DIR);
    }

    console.log('[Runtime Bundler] Motor nativo llama-server.exe preparado correctamente.');
  } catch (err) {
    console.warn('[Runtime Bundler] Aviso al preparar llama-server.exe (se descargará bajo demanda en la app):', err.message);
  }
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
      await downloadFile(PYTHON_ZIP_URL, ZIP_PATH);
      console.log('[Python Bundler] Extrayendo paquete Python 3.11 embebido...');
      extractZip(ZIP_PATH, PYTHON_DIR);

      if (fs.existsSync(ZIP_PATH)) {
        fs.unlinkSync(ZIP_PATH);
      }
    }

    // Configurar python311._pth para habilitar site-packages y resolución del proyecto
    const pthFile = path.join(PYTHON_DIR, 'python311._pth');
    const pthContent = [
      'python311.zip',
      '.',
      '..',
      'Lib',
      'Lib\\site-packages',
      'DLLs',
      'import site'
    ].join('\n') + '\n';
    fs.writeFileSync(pthFile, pthContent, 'utf-8');
    console.log('[Python Bundler] Configurado python311._pth con soporte completo de site-packages.');

    const sitePackages = path.join(PYTHON_DIR, 'Lib', 'site-packages');
    if (!fs.existsSync(sitePackages)) {
      fs.mkdirSync(sitePackages, { recursive: true });
    }

    const reqFile = path.join(ROOT_DIR, 'backend', 'requirements.txt');
    if (fs.existsSync(reqFile)) {
      console.log('[Python Bundler] Instalando dependencias de backend/requirements.txt en python/Lib/site-packages...');
      let installedWithEmbedded = false;

      if (process.platform === 'win32' && fs.existsSync(pythonExe)) {
        try {
          await downloadFile(GET_PIP_URL, GET_PIP_PATH);
          execSync(`"${pythonExe}" "${GET_PIP_PATH}" --no-warn-script-location`, { stdio: 'inherit' });
          execSync(`"${pythonExe}" -m pip install -r "${reqFile}" --no-warn-script-location`, { stdio: 'inherit' });
          installedWithEmbedded = true;
          if (fs.existsSync(GET_PIP_PATH)) fs.unlinkSync(GET_PIP_PATH);
        } catch (err) {
          console.warn('[Python Bundler] Aviso al usar pip del ejecutable embebido, usando pip del sistema con --target:', err.message);
        }
      }

      if (!installedWithEmbedded) {
        try {
          execSync(
            `pip install -r "${reqFile}" --target "${sitePackages}" --implementation cp --python-version 3.11 --only-binary=:all: --upgrade --no-warn-script-location`,
            { stdio: 'inherit' }
          );
        } catch (e) {
          try {
            execSync(`pip install -r "${reqFile}" --target "${sitePackages}" --no-warn-script-location`, { stdio: 'inherit' });
          } catch (err) {
            console.warn('[Python Bundler] Pip no disponible en este entorno de compilación.');
          }
        }
      }
    }

    // Preparar también los binarios nativos de inferencia (runtime/llama-server.exe)
    await prepareLlamaRuntime();

    console.log('[Python Bundler] Preparación de Python + Runtime nativo finalizada correctamente.');
  } catch (err) {
    console.error('[Python Bundler] Error al preparar entorno:', err);
    if (!fs.existsSync(PYTHON_DIR)) fs.mkdirSync(PYTHON_DIR, { recursive: true });
    if (!fs.existsSync(RUNTIME_DIR)) fs.mkdirSync(RUNTIME_DIR, { recursive: true });
  }
}

preparePython();

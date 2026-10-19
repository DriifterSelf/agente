# ⚡ Agente Studio

> Aplicación de escritorio nativa para Windows con interfaz estilo Antigravity, motor de ofimática (Word, Excel, PowerPoint), navegación web, automatización del sistema y actualizaciones automáticas (OTA).

---

## 🚀 Arquitectura y Capacidades

- **Sin consola:** Corre silenciosamente con ventana nativa de Electron y tema oscuro.
- **Detección Dinámica de Hardware:**
  - En **AMD Radeon RX 9070 XT**: Aceleración por ROCm / HIP / Vulkan con 16 GB de VRAM.
  - En **Alienware m18 R2 (RTX 4070 Laptop)**: Aceleración por CUDA 12.x con 8 GB de VRAM + 64 GB de RAM offloading.
- **3 Paneles (Estilo Antigravity):**
  - **Izquierda:** Proyectos y explorador de archivos con apertura en Windows.
  - **Centro:** Chat con trazabilidad de acciones en tiempo real (cápsulas de pensamiento y ejecución).
  - **Derecha:** Panel de artefactos con botón directo de *Abrir en Excel / Word / PowerPoint*.
- **Herramientas de Oficina:**
  - 📊 Creación de hojas de cálculo `.xlsx` con formatos financieros, tablas y gráficos.
  - 📄 Creación de documentos `.docx` ejecutivos con portadas, títulos y llamadas.
  - 📑 Creación de presentaciones `.pptx` en formato panorámico 16:9.
  - 🌐 Navegación e investigación web con extracción limpia de contenido.

---

## 🔄 Sistema de Actualizaciones OTA (Over-The-Air)

La aplicación cuenta con dos métodos integrados para mantenerse siempre al día:

### 1. Conectar a tu Repositorio en GitHub
Para subir el código a tu cuenta de GitHub:
```powershell
git remote add origin https://github.com/TU_USUARIO/agente-studio.git
git push -u origin main
```

### 2. Auto-Update OTA de Producción (`electron-updater`)
En `package.json`, cambia `"owner": "USUARIO_GITHUB"` por tu usuario de GitHub.
Cada vez que publiques un release con un nuevo tag:
```powershell
npm run dist
```
Cualquier instalación de la app detectará la actualización automáticamente, la descargará en segundo plano y mostrará el botón de reinicio para aplicar los cambios.

### 3. Sincronización Rápida desde la App
En la barra de título superior, el botón **"Buscar Actualizaciones"** consulta tu repositorio Git en tiempo real, descarga cambios con `git pull` y recompila la interfaz en segundos.

---

## 📦 Generar Instalador `.exe` para Distribuir

Para compilar el instalador ejecutable para Windows:
```powershell
npm run build:win
```
Los archivos `.exe` generados quedarán en la carpeta `release/`:
* `Agente Studio Setup 1.0.0.exe` (Instalador NSIS con acceso directo y menú inicio)
* `Agente Studio 1.0.0.exe` (Versión portable de un solo archivo)

# ==============================================================================
# DESCARGADOR NATIVO DE BINARIOS LLAMA.CPP (GPU VULKAN / CUDA) PARA WINDOWS
# ==============================================================================
# Descarga e instala llama-server.exe + DLLs de GPU en:
#   C:\Users\<TU_USUARIO>\AgenteStudio\runtime\llama-server.exe
# ==============================================================================

$runtimeDir = Join-Path $env:USERPROFILE "AgenteStudio\runtime"
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

Clear-Host
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "   INSTALADOR NATIVO DE LLAMA-SERVER.EXE (GPU WINDOWS x64)" -ForegroundColor Cyan
Write-Host "==========================================================="
Write-Host "Carpeta de destino: $runtimeDir`n"

$zipPath = Join-Path $runtimeDir "llama-runtime.zip"
$extractDir = Join-Path $runtimeDir "_extract_tmp"

Write-Host "[1/3] Consultando ultima version oficial en GitHub (ggml-org/llama.cpp)..." -ForegroundColor Yellow

$downloadUrl = $null
try {
    $jsonRaw = curl.exe --ssl-no-revoke -s -L "https://api.github.com/repos/ggml-org/llama.cpp/releases/latest"
    $release = $jsonRaw | ConvertFrom-Json
    foreach ($asset in $release.assets) {
        if ($asset.name -match "bin-win-vulkan-x64\.zip$") {
            $downloadUrl = $asset.browser_download_url
            Write-Host "      Encontrada version GPU Vulkan/NVIDIA: $($asset.name)" -ForegroundColor Green
            break
        }
    }
    if (-not $downloadUrl) {
        foreach ($asset in $release.assets) {
            if ($asset.name -match "bin-win-avx2-x64\.zip$") {
                $downloadUrl = $asset.browser_download_url
                Write-Host "      Encontrada version AVX2 x64: $($asset.name)" -ForegroundColor Green
                break
            }
        }
    }
} catch {
    Write-Host "      Aviso al consultar API, usando enlace directo de respaldo..." -ForegroundColor DarkYellow
}

if (-not $downloadUrl) {
    $downloadUrl = "https://github.com/ggml-org/llama.cpp/releases/download/b5092/llama-b5092-bin-win-vulkan-x64.zip"
}

Write-Host "`n[2/3] Descargando paquete de binarios (~22 MB)..." -ForegroundColor Yellow
curl.exe --ssl-no-revoke -L --fail --retry 5 --retry-delay 3 "$downloadUrl" -o "$zipPath"

if (-not (Test-Path $zipPath)) {
    Write-Host "`n[ERROR] No se pudo descargar el archivo ZIP." -ForegroundColor Red
    exit 1
}

Write-Host "`n[3/3] Extrayendo llama-server.exe y librerias DLL..." -ForegroundColor Yellow
if (Test-Path $extractDir) { Remove-Item -Recurse -Force $extractDir }
Expand-Archive -Path $zipPath -DestinationPath $extractDir -Force

Get-ChildItem -Path $extractDir -Recurse -File | Where-Object {
    $_.Extension -in ".exe", ".dll"
} | ForEach-Object {
    Copy-Item -Path $_.FullName -Destination (Join-Path $runtimeDir $_.Name) -Force
}

Remove-Item -Force $zipPath -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force $extractDir -ErrorAction SilentlyContinue

$serverExe = Join-Path $runtimeDir "llama-server.exe"
if (Test-Path $serverExe) {
    $sizeMb = [math]::Round((Get-Item $serverExe).Length / 1MB, 2)
    Write-Host "`n===========================================================" -ForegroundColor Cyan
    Write-Host " [OK] BINARIO INSTALADO: $serverExe ($sizeMb MB)" -ForegroundColor Green
    Write-Host " [OK] DLLs DE ACELERACION GPU EXTRAIDAS CORRECTAMENTE" -ForegroundColor Green
    Write-Host "===========================================================" -ForegroundColor Cyan
    Write-Host "`nYa puedes volver a Agente Studio o pulsar 'Reconectar Python' / cambiar modelo." -ForegroundColor White
} else {
    Write-Host "`n[FAIL] No se encontro llama-server.exe tras extraer el paquete." -ForegroundColor Red
}

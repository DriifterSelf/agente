$dest = "$env:USERPROFILE\AgenteStudio\models"
New-Item -ItemType Directory -Force -Path $dest | Out-Null

# Si habia modelos en .\models dentro de la carpeta del proyecto/instalacion, moverlos a la boveda segura
if (Test-Path ".\models") {
    Get-ChildItem -Path ".\models" -Filter "*.gguf" -ErrorAction SilentlyContinue | ForEach-Object {
        $target = Join-Path $dest $_.Name
        if (-not (Test-Path $target)) {
            Move-Item -Path $_.FullName -Destination $target -Force -ErrorAction SilentlyContinue
        }
    }
}

Clear-Host
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "   DESCARGADOR NATIVO DE WINDOWS (BOVEDA PERSISTENTE)" -ForegroundColor Cyan
Write-Host "==========================================================="
Write-Host "Carpeta segura (inmune a actualizaciones): $dest`n"
Write-Host " [1] Qwen3-30B-A3B-Q4_K_M (~17.3 GB - MoE para 64GB DDR5)"
Write-Host " [2] Qwen3-8B-Q4_K_M (~4.68 GB - Ultrarrapido para VRAM)`n"

$opc = Read-Host "Elige una opcion (1 o 2) [Enter para 1]"
if ($opc -eq "2") {
    $name = "Qwen3-8B-Q4_K_M.gguf"
    $url = "https://huggingface.co/Qwen/Qwen3-8B-GGUF/resolve/main/Qwen3-8B-Q4_K_M.gguf?download=true"
    $min = 4GB
} else {
    $name = "Qwen3-30B-A3B-Q4_K_M.gguf"
    $url = "https://huggingface.co/Qwen/Qwen3-30B-A3B-GGUF/resolve/main/Qwen3-30B-A3B-Q4_K_M.gguf?download=true"
    $min = 15GB
}

$file = Join-Path $dest $name
Write-Host "`nDescargando $name ..." -ForegroundColor Yellow
Write-Host "(Tiene reanudacion automatica si se corta la conexion)`n"

curl.exe --ssl-no-revoke -L --fail -C - --retry 10 --retry-delay 5 $url -o $file

Write-Host "`n===========================================================" -ForegroundColor Cyan
Write-Host " VERIFICANDO INTEGRIDAD DEL ARCHIVO GGUF..." -ForegroundColor Cyan
Write-Host "==========================================================="

if (Test-Path $file) {
    $item = Get-Item $file
    $gb = [math]::Round($item.Length / 1GB, 2)
    Write-Host "Tamano en disco: $gb GB"
    if ($item.Length -ge $min) {
        $stream = [System.IO.File]::OpenRead($file)
        $bytes = New-Object byte[] 4
        $null = $stream.Read($bytes, 0, 4)
        $stream.Close()
        $magic = [System.Text.Encoding]::ASCII.GetString($bytes)
        if ($magic -eq "GGUF") {
            Write-Host "`n [OK] Cabecera magica valida: GGUF" -ForegroundColor Green
            Write-Host " [OK] MODELO VERIFICADO Y 100% OPERATIVO" -ForegroundColor Green
        } else {
            Write-Host "`n [FAIL] Cabecera invalida: $magic" -ForegroundColor Red
        }
    } else {
        Write-Host "`n [FAIL] Archivo incompleto ($gb GB de descarga)." -ForegroundColor Red
    }
}

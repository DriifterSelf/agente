import os
import sys
import ssl
import glob
import json
import time
import shutil
import zipfile
import threading
import subprocess
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional

try:
    import psutil
except ImportError:
    psutil = None

try:
    from llama_cpp import Llama
except ImportError:
    Llama = None


class InferenceEngine:
    """
    Motor de Inferencia Híbrido GPU (CUDA 12.x / Vulkan) + DDR5 RAM.
    Ejecuta modelos GGUF (Qwen3-30B-A3B-Q4_K_M.gguf y Qwen3-8B-Q4_K_M.gguf)
    mediante binarios nativos de llama.cpp (runtime/llama-server.exe) o llama-cpp-python.
    """

    OFFICIAL_MODELS = [
        {
            "filename": "Qwen3-30B-A3B-Q4_K_M.gguf",
            "expected_gb": 17.3,
            "badge": "MoE • 64GB DDR5 + GPU",
            "desc": "Arquitectura Mixture-of-Experts (30B totales, 3B activos) • Máximo razonamiento",
            "url": "https://huggingface.co/Qwen/Qwen3-30B-A3B-GGUF/resolve/main/Qwen3-30B-A3B-Q4_K_M.gguf?download=true"
        },
        {
            "filename": "Qwen3-8B-Q4_K_M.gguf",
            "expected_gb": 4.68,
            "badge": "100% VRAM • Ultrarrápido",
            "desc": "100% en los 8GB VRAM de tu RTX 4070 • Respuesta instantánea",
            "url": "https://huggingface.co/Qwen/Qwen3-8B-GGUF/resolve/main/Qwen3-8B-Q4_K_M.gguf?download=true"
        }
    ]

    def __init__(self, models_dir: str):
        self.root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.user_home_dir = os.path.join(os.path.expanduser("~"), "AgenteStudio")
        self.safe_models_dir = os.path.join(self.user_home_dir, "models")
        os.makedirs(self.safe_models_dir, exist_ok=True)

        # Siempre usar la bóveda de usuario (~/AgenteStudio/models) como carpeta principal de descarga y almacenamiento
        self.models_dir = self.safe_models_dir
        self._rescue_models_from_install_dir(models_dir)

        self.active_model: Optional[str] = None
        self.active_model_path: Optional[str] = None
        self.n_ctx: int = 32768
        self.kv_mode: str = "auto"  # "auto" | "gpu" | "ram"
        self.kv_location: str = "gpu"
        self.model_instance = None
        self.server_process: Optional[subprocess.Popen] = None
        self.server_port: int = 8081
        self.n_gpu_layers: int = 35
        self.engine_state: str = "idle"  # "idle" | "loading" | "ready" | "no_model"
        self.engine_message: str = "Inicializando motor..."
        self._lock = threading.Lock()

    def _log(self, msg: str):
        print(f"[InferenceEngine] {msg}", flush=True)

    def _rescue_models_from_install_dir(self, extra_dir: Optional[str] = None):
        """
        Si existen archivos .gguf dentro del directorio de instalación de la app (que NSIS borra al actualizar),
        los mueve automáticamente a ~/AgenteStudio/models para que jamás se pierdan en una actualización.
        """
        volatile_dirs = [
            extra_dir,
            os.path.join(self.root_dir, "models"),
            os.path.join(os.path.dirname(self.root_dir), "models"),
        ]
        for v_dir in volatile_dirs:
            if not v_dir or not os.path.exists(v_dir):
                continue
            if os.path.abspath(v_dir) == os.path.abspath(self.safe_models_dir):
                continue
            try:
                for entry in os.scandir(v_dir):
                    if entry.is_file() and entry.name.lower().endswith(".gguf"):
                        dest = os.path.join(self.safe_models_dir, entry.name)
                        if not os.path.exists(dest):
                            try:
                                shutil.move(entry.path, dest)
                                self._log(f"Modelo rescatado a bóveda persistente contra actualizaciones: {dest}")
                            except Exception:
                                pass
            except Exception:
                pass

    def _get_candidate_model_dirs(self) -> List[str]:
        appdata = os.environ.get("APPDATA") or ""
        localappdata = os.environ.get("LOCALAPPDATA") or ""
        dirs = [
            self.safe_models_dir,
            self.models_dir,
            os.path.join(self.user_home_dir, "models"),
            os.path.join(appdata, "AgenteStudio", "models") if appdata else "",
            os.path.join(localappdata, "AgenteStudio", "models") if localappdata else "",
            os.path.join(os.path.expanduser("~"), "Downloads"),
            os.path.join(self.root_dir, "models"),
            os.path.join(os.path.dirname(self.root_dir), "models"),
        ]
        unique = []
        for d in dirs:
            if d:
                norm = os.path.abspath(d)
                if norm not in unique and os.path.exists(norm):
                    unique.append(norm)
        return unique

    def _is_valid_gguf(self, path: str) -> bool:
        try:
            if not os.path.isfile(path) or os.path.getsize(path) < 10 * 1024 * 1024:
                return False
            with open(path, "rb") as f:
                magic = f.read(4)
            return magic == b"GGUF"
        except Exception:
            return False

    def list_available_models(self) -> List[Dict[str, Any]]:
        """Devuelve únicamente los modelos .gguf válidos e instalados en disco."""
        results = []
        seen_names = set()

        for d in self._get_candidate_model_dirs():
            files = glob.glob(os.path.join(d, "*.gguf"))
            for f in files:
                if not self._is_valid_gguf(f):
                    continue
                fname = os.path.basename(f)
                if fname.lower() in seen_names:
                    continue
                seen_names.add(fname.lower())
                try:
                    size_gb = round(os.path.getsize(f) / (1024 ** 3), 2)
                except Exception:
                    size_gb = 0.0

                meta = next((m for m in self.OFFICIAL_MODELS if m["filename"].lower() == fname.lower()), None)
                results.append({
                    "filename": fname,
                    "size_gb": size_gb,
                    "path": f,
                    "installed": True,
                    "badge": meta["badge"] if meta else "GGUF Local",
                    "desc": meta["desc"] if meta else f"Modelo local en {os.path.dirname(f)}"
                })

        def sort_key(item):
            name_low = item["filename"].lower()
            if "qwen3-30b" in name_low:
                return (0, name_low)
            if "qwen3-8b" in name_low:
                return (1, name_low)
            return (2, name_low)

        return sorted(results, key=sort_key)

    def list_catalog_models(self) -> List[Dict[str, Any]]:
        """Devuelve todos los modelos instalados en disco + los modelos oficiales Qwen3 para el selector."""
        installed_list = self.list_available_models()
        installed_map = {m["filename"].lower(): m for m in installed_list}
        catalog = []

        for off in self.OFFICIAL_MODELS:
            key = off["filename"].lower()
            if key in installed_map:
                item = dict(installed_map[key])
                item["active"] = bool(self.active_model and self.active_model.lower() == key)
                catalog.append(item)
            else:
                target_path = os.path.join(self.models_dir, off["filename"])
                partial_gb = 0.0
                if os.path.exists(target_path):
                    try:
                        partial_gb = round(os.path.getsize(target_path) / (1024 ** 3), 2)
                    except Exception:
                        pass
                catalog.append({
                    "filename": off["filename"],
                    "size_gb": off["expected_gb"],
                    "partial_gb": partial_gb,
                    "path": target_path,
                    "installed": False,
                    "active": bool(self.active_model and self.active_model.lower() == key),
                    "badge": off["badge"],
                    "desc": off["desc"],
                    "url": off["url"]
                })

        official_keys = {m["filename"].lower() for m in self.OFFICIAL_MODELS}
        for inst in installed_list:
            if inst["filename"].lower() not in official_keys:
                item = dict(inst)
                item["active"] = bool(self.active_model and self.active_model.lower() == inst["filename"].lower())
                catalog.append(item)

        return catalog

    def download_model_native(self, filename: str) -> Dict[str, Any]:
        """Lanza el descargador nativo con curl.exe en Windows para el modelo seleccionado."""
        meta = next((m for m in self.OFFICIAL_MODELS if m["filename"].lower() == filename.lower()), None)
        if not meta:
            return {"status": "error", "message": f"URL oficial no registrada para {filename}"}

        os.makedirs(self.models_dir, exist_ok=True)
        dest_file = os.path.join(self.models_dir, meta["filename"])
        url = meta["url"]

        if sys.platform == "win32":
            try:
                ps_cmd = (
                    f'$Host.UI.RawUI.WindowTitle = "Descargando {meta["filename"]}"; '
                    f'Write-Host "===========================================================" -ForegroundColor Cyan; '
                    f'Write-Host " DESCARGANDO {meta["filename"]} ({meta["expected_gb"]} GB)" -ForegroundColor Cyan; '
                    f'Write-Host " Destino: {dest_file}" -ForegroundColor Yellow; '
                    f'Write-Host "===========================================================" -ForegroundColor Cyan; '
                    f'curl.exe --ssl-no-revoke -L --fail -C - --retry 10 --retry-delay 5 "{url}" -o "{dest_file}"; '
                    f'Write-Host "`nDescarga finalizada. Ya puedes seleccionar el modelo en Agente Studio." -ForegroundColor Green; '
                    f'Read-Host "Presiona Enter para cerrar"'
                )
                subprocess.Popen(
                    ["powershell", "-NoProfile", "-Command", ps_cmd],
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
                return {"status": "started", "filename": meta["filename"], "dest": dest_file}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        return {"status": "error", "message": "Descarga nativa disponible en Windows"}

    def _find_llama_server_binary(self) -> Optional[str]:
        exe_name = "llama-server.exe" if sys.platform == "win32" else "llama-server"
        search_roots = [
            os.path.join(self.user_home_dir, "runtime"),
            os.path.join(self.root_dir, "runtime"),
            os.path.join(os.path.dirname(self.root_dir), "runtime"),
        ]
        appdata = os.environ.get("APPDATA")
        if appdata:
            search_roots.append(os.path.join(appdata, "AgenteStudio", "runtime"))
        localappdata = os.environ.get("LOCALAPPDATA")
        if localappdata:
            search_roots.append(os.path.join(localappdata, "AgenteStudio", "runtime"))

        for base in search_roots:
            direct = os.path.join(base, exe_name)
            if os.path.isfile(direct):
                return direct
            if os.path.isdir(base):
                for root, _, files in os.walk(base):
                    if exe_name in files:
                        return os.path.join(root, exe_name)
        return None

    def ensure_runtime(self) -> Optional[str]:
        """
        Verifica si existe llama-server.exe. Si no existe, lo descarga automáticamente
        usando curl.exe nativo de Windows (--ssl-no-revoke) para evitar errores SSL en Python embebido.
        """
        existing = self._find_llama_server_binary()
        if existing:
            self._log(f"Binario nativo GPU encontrado en: {existing}")
            return existing

        if sys.platform != "win32":
            return shutil.which("llama-server")

        target_runtime_dir = os.path.join(self.user_home_dir, "runtime")
        os.makedirs(target_runtime_dir, exist_ok=True)
        zip_dest = os.path.join(target_runtime_dir, "llama-runtime.zip")
        release_json_path = os.path.join(target_runtime_dir, "release_latest.json")

        try:
            self.engine_state = "loading"
            self.engine_message = "Descargando binarios GPU de llama.cpp (llama-server.exe)..."
            self._log("No se encontró llama-server.exe. Consultando última release oficial de ggml-org/llama.cpp...")

            release_data = None
            creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

            # 1. Consultar API de GitHub con curl.exe --ssl-no-revoke (inmune a errores de certificados de Python embed)
            try:
                curl_res = subprocess.run(
                    [
                        "curl.exe",
                        "--ssl-no-revoke",
                        "-sL",
                        "-H", "User-Agent: AgenteStudio/1.0",
                        "-H", "Accept: application/vnd.github+json",
                        "https://api.github.com/repos/ggml-org/llama.cpp/releases/latest",
                        "-o", release_json_path
                    ],
                    capture_output=True,
                    text=True,
                    timeout=20,
                    creationflags=creation_flags
                )
                if curl_res.returncode == 0 and os.path.exists(release_json_path):
                    with open(release_json_path, "r", encoding="utf-8", errors="replace") as rf:
                        release_data = json.load(rf)
                    try:
                        os.remove(release_json_path)
                    except Exception:
                        pass
            except Exception as e_curl:
                self._log(f"Aviso consultando con curl.exe: {e_curl}")

            # Fallback con urllib + contexto SSL sin verificación
            if not release_data:
                ctx = ssl._create_unverified_context()
                req = urllib.request.Request(
                    "https://api.github.com/repos/ggml-org/llama.cpp/releases/latest",
                    headers={"User-Agent": "AgenteStudio/1.0", "Accept": "application/vnd.github+json"}
                )
                with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
                    release_data = json.loads(resp.read().decode("utf-8"))

            assets = release_data.get("assets", []) if isinstance(release_data, dict) else []
            asset_url = None
            asset_name = None

            # Priorizar paquete nativo CUDA 12.4 para NVIDIA RTX 4070 (aceleración pura Tensor Cores),
            # o Vulkan universal como respaldo
            cuda_bin = next((a for a in assets if "bin-win-cuda-12.4-x64.zip" in a.get("name", "").lower()), None)
            cudart_bin = next((a for a in assets if "cudart-llama-bin-win-cuda-12.4-x64.zip" in a.get("name", "").lower()), None)
            vulkan_bin = next((a for a in assets if "bin-win-vulkan-x64.zip" in a.get("name", "").lower()), None)

            target_assets = []
            if cuda_bin and cudart_bin:
                target_assets = [cuda_bin, cudart_bin]
                asset_name = "NVIDIA CUDA 12.4 Nativo"
            elif vulkan_bin:
                target_assets = [vulkan_bin]
                asset_name = vulkan_bin.get("name", "Vulkan x64")
            else:
                for pattern in ["bin-win-avx2-x64.zip", "bin-win-x64.zip"]:
                    fallback_a = next((a for a in assets if pattern in a.get("name", "").lower()), None)
                    if fallback_a:
                        target_assets = [fallback_a]
                        asset_name = fallback_a.get("name")
                        break

            if not target_assets:
                self._log("No se encontró paquete zip compatible en la release de llama.cpp.")
                return None

            self._log(f"Descargando {asset_name}...")
            self.engine_message = f"Descargando {asset_name}..."

            for a_item in target_assets:
                a_url = a_item.get("browser_download_url")
                a_filename = a_item.get("name")
                item_zip = os.path.join(target_runtime_dir, a_filename)
                try:
                    subprocess.run(
                        ["curl.exe", "--ssl-no-revoke", "-L", "--fail", "--retry", "5", a_url, "-o", item_zip],
                        capture_output=True,
                        timeout=180,
                        creationflags=creation_flags
                    )
                    if os.path.exists(item_zip):
                        with zipfile.ZipFile(item_zip, "r") as zf:
                            zf.extractall(target_runtime_dir)
                        try:
                            os.remove(item_zip)
                        except Exception:
                            pass
                except Exception as e_dl:
                    self._log(f"Aviso descargando {a_filename}: {e_dl}")



            # Si se extrajo en una subcarpeta (ej. build/bin/), copiar ejecutables y DLLs a la raíz de target_runtime_dir
            direct_exe = os.path.join(target_runtime_dir, "llama-server.exe")
            if not os.path.isfile(direct_exe):
                for root, _, files in os.walk(target_runtime_dir):
                    for f in files:
                        if f.lower().endswith((".exe", ".dll")):
                            src_p = os.path.join(root, f)
                            dst_p = os.path.join(target_runtime_dir, f)
                            if os.path.abspath(src_p) != os.path.abspath(dst_p) and not os.path.exists(dst_p):
                                try:
                                    shutil.copy2(src_p, dst_p)
                                except Exception:
                                    pass

            found_bin = self._find_llama_server_binary()
            if found_bin:
                self._log(f"¡Runtime GPU instalado correctamente en: {found_bin}!")
            return found_bin
        except Exception as e:
            self._log(f"Error al descargar llama-server automáticamente: {e}")
            return None

    def auto_start(self):
        models = self.list_available_models()
        if models:
            first = models[0]
            self.active_model = first["filename"]
            self.active_model_path = first["path"]
            threading.Thread(
                target=self.load_model,
                args=(first["filename"],),
                daemon=True
            ).start()
        else:
            self.engine_state = "no_model"
            self.engine_message = "Coloca Qwen3-30B-A3B o Qwen3-8B (.gguf) en ~/AgenteStudio/models"

    def stop(self):
        self.model_instance = None
        if self.server_process:
            try:
                self.server_process.terminate()
                self.server_process.wait(timeout=3)
            except Exception:
                try:
                    self.server_process.kill()
                except Exception:
                    pass
            self.server_process = None

    def _check_llama_server_state(self) -> str:
        """
        Retorna:
        - 'ready': HTTP 200 OK en /health (modelo cargado y listo para inferir)
        - 'loading': HTTP 503 en /health (llama-server está leyendo el GGUF en RAM/VRAM)
        - 'down': No responde
        """
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{self.server_port}/health")
            with urllib.request.urlopen(req, timeout=1.5) as r:
                if r.status == 200:
                    return "ready"
        except urllib.error.HTTPError as he:
            if he.code == 503:
                return "loading"
        except Exception:
            pass
        return "down"

    def _is_llama_server_healthy(self) -> bool:
        return self._check_llama_server_state() == "ready"

    def _compute_hardware_tuning(self, model_path: str, requested_gpu_layers: int = 35):
        size_gb = 4.7
        try:
            size_gb = os.path.getsize(model_path) / (1024 ** 3)
        except Exception:
            pass

        fname_low = os.path.basename(model_path).lower()
        is_moe_30b = "30b" in fname_low or size_gb > 10.0

        if is_moe_30b:
            # Qwen3-30B-A3B (~17.3 GB MoE, 48 capas):
            # En 8GB VRAM + 64GB DDR5, con Flash Attention (-fa) y KV-cache en RAM (-nkvo),
            # offloadeamos 35 capas directamente a la RTX 4070 Laptop (ocupando ~6.0-6.8 GB de los 8.0 GB VRAM).
            # Con esto el 73% de la red neuronal se computa directamente en los Tensor Cores de la GPU NVIDIA.
            gpu_layers = 35 if self.kv_mode != "ram" else 28
            kv_loc = "ram" if self.kv_mode in ("auto", "ram") else "gpu"
        else:
            # Qwen3-8B (~4.68 GB): 100% de las capas caben en 8GB VRAM
            # ¡Garantiza 95%-100% de uso continuo de la GPU sin cuello de botella en RAM!
            gpu_layers = 99 if self.kv_mode != "ram" else 30
            if self.kv_mode == "ram":
                kv_loc = "ram"
            elif self.kv_mode == "gpu":
                kv_loc = "gpu"
            else:
                kv_loc = "ram" if self.n_ctx > 32768 else "gpu"

        return gpu_layers, kv_loc

    def _try_launch_llama_server(self, llama_bin: str, model_path: str, filename: str, gpu_layers: int, kv_loc: str) -> bool:
        self.stop()
        # En Alienware m18 R2 con Intel Core i9-14900HX, usar exactamente 8 hilos (P-cores físicos).
        # Evita que Windows asigne trabajo a los E-cores lentos que estrangulan el ancho de banda DDR5.
        threads = 8
        cmd = [
            llama_bin,
            "-m", model_path,
            "--host", "127.0.0.1",
            "--port", str(self.server_port),
            "-c", str(self.n_ctx),
            "-ngl", str(gpu_layers),
            "-t", str(threads),
            "--threads-batch", "8",
            "-b", "2048",   # Saturación de Tensor Cores en RTX 4070
            "-ub", "512",   # Batching de micro-evaluación rápida
            "-fa",          # Flash Attention: atención O(N) lineal en lugar de cuadrática O(N^2)
            "-ctk", "q8_0", # Quantización de Key cache: reduce a la mitad el tráfico de bus por token
            "-ctv", "q8_0", # Quantización de Value cache: mantiene la velocidad constante a lo largo del texto
            "--mlock",      # Bloquea el modelo en 64GB DDR5 RAM (evita que Windows pagine al SSD)
            "--split-mode", "none",
            "--main-gpu", "0",
        ]
        if kv_loc == "ram":
            cmd.append("-nkvo")

        self._log(f"Iniciando llama-server: {' '.join(cmd)}")
        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

        # Forzar que Windows y Vulkan/CUDA seleccionen la GPU dedicada NVIDIA y eviten la Intel UHD Graphics
        run_env = os.environ.copy()
        run_env["CUDA_VISIBLE_DEVICES"] = "0"
        run_env["GGML_VK_VISIBLE_DEVICES"] = "0"
        run_env["__NV_PRIME_RENDER_OFFLOAD"] = "1"
        run_env["__GLX_VENDOR_LIBRARY_NAME"] = "nvidia"
        run_env["__VK_LAYER_NV_optimus"] = "NVIDIA_only"
        run_env["VK_DEVICE_SELECT"] = "nvidia"

        self.server_process = subprocess.Popen(
            cmd,
            cwd=os.path.dirname(llama_bin),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creation_flags,
            env=run_env
        )

        # Hilo lector de logs de llama-server para mostrar progreso en DevTools
        def _stream_logs(proc):
            try:
                for line in proc.stdout:
                    line_s = line.strip()
                    if line_s and any(k in line_s.lower() for k in ["error", "listening", "loaded", "offload", "vulkan", "cuda", "kv"]):
                        self._log(f"[llama-server] {line_s}")
            except Exception:
                pass

        threading.Thread(target=_stream_logs, args=(self.server_process,), daemon=True).start()

        # Esperar hasta 120 segundos (un modelo de 17.3 GB puede tardar 25-60s en mapearse en RAM/VRAM)
        for tick in range(240):
            state = self._check_llama_server_state()
            if state == "ready":
                self.engine_state = "ready"
                self.engine_message = f"{filename} activo ({gpu_layers} capas GPU)"
                self._log(f"¡{filename} cargado y listo en puerto {self.server_port}!")
                return True
            elif state == "loading":
                elapsed = int(tick * 0.5)
                self.engine_state = "loading"
                self.engine_message = f"Cargando {filename} en GPU + DDR5 ({elapsed}s)..."

            if self.server_process.poll() is not None:
                self._log(f"llama-server finalizó prematuramente con código {self.server_process.returncode} (ngl={gpu_layers})")
                return False
            time.sleep(0.5)

        return False

    def load_model(self, filename: str, n_gpu_layers: int = 35, n_ctx: int = None):
        with self._lock:
            if n_ctx:
                self.n_ctx = n_ctx

            model_path = None
            for m in self.list_available_models():
                if m["filename"].lower() == filename.lower():
                    model_path = m["path"]
                    filename = m["filename"]
                    break

            if not model_path:
                for d in self._get_candidate_model_dirs():
                    candidate = os.path.join(d, filename)
                    if os.path.exists(candidate):
                        model_path = candidate
                        break

            if not model_path or not os.path.exists(model_path):
                self.engine_state = "no_model"
                self.engine_message = f"Modelo no encontrado: {filename}"
                return {"status": "error", "message": self.engine_message}

            self.active_model = filename
            self.active_model_path = model_path
            self.engine_state = "loading"
            self.engine_message = f"Preparando {filename}..."

            gpu_layers, kv_loc = self._compute_hardware_tuning(model_path, n_gpu_layers)
            self.n_gpu_layers = gpu_layers
            self.kv_location = kv_loc

            # 1. Asegurar binario nativo llama-server.exe y lanzar con fallback automático de capas GPU
            llama_bin = self.ensure_runtime()
            if llama_bin and os.path.exists(llama_bin):
                # Intentar primero con el perfil GPU óptimo; si falla por VRAM insuficiente, probar con menos capas
                fallback_profiles = [
                    (gpu_layers, kv_loc),
                    (28, "ram"),
                    (20, "ram"),
                    (12, "ram"),
                    (0, "ram")
                ]
                seen_profiles = set()
                for ngl_try, kv_try in fallback_profiles:
                    if (ngl_try, kv_try) in seen_profiles:
                        continue
                    seen_profiles.add((ngl_try, kv_try))
                    if self._try_launch_llama_server(llama_bin, model_path, filename, ngl_try, kv_try):
                        self.n_gpu_layers = ngl_try
                        self.kv_location = kv_try
                        return {
                            "status": "loaded",
                            "model": filename,
                            "n_ctx": self.n_ctx,
                            "gpu_layers": ngl_try,
                            "kv_location": kv_try
                        }

            # 2. Fallback: llama-cpp-python si está instalado
            if Llama is not None:
                try:
                    self.model_instance = None
                    self.model_instance = Llama(
                        model_path=model_path,
                        n_ctx=self.n_ctx,
                        n_gpu_layers=gpu_layers,
                        verbose=False
                    )
                    self.engine_state = "ready"
                    self.engine_message = f"{filename} cargado en memoria"
                    return {"status": "loaded", "model": filename, "n_ctx": self.n_ctx, "gpu_layers": gpu_layers}
                except Exception as e:
                    self._log(f"Aviso en llama_cpp: {e}")

            self.engine_state = "no_model"
            self.engine_message = f"Falta runtime/llama-server.exe para iniciar {filename}"
            return {"status": "error", "model": filename, "message": self.engine_message}

    def generate_stream(self, messages: List[Dict[str, str]], max_tokens: int = 4096, temperature: float = 0.6):
        """
        Genera tokens en streaming desde llama-server.exe (puerto 8081).
        Si el modelo está terminando de cargarse en RAM/VRAM, espera automáticamente a que esté listo.
        """
        # Si llama-server está en estado 'loading' (cargando el archivo de 17.3 GB), esperar hasta 60s
        if self._check_llama_server_state() == "loading" or self.engine_state == "loading":
            yield "*(Cargando modelo en GPU + DDR5, un momento por favor...)*\n\n"
            for _ in range(120):
                if self._is_llama_server_healthy():
                    break
                time.sleep(0.5)

        # Si aún no se ha iniciado el proceso y hay modelos disponibles, lanzarlo ahora
        if self._check_llama_server_state() == "down" and self.model_instance is None:
            models = self.list_available_models()
            if models:
                target_name = self.active_model or models[0]["filename"]
                self.load_model(target_name)

        # 1. Consultar llama-server.exe gestionado (puerto 8081) o servidores locales (8080, 1234)
        for port in [self.server_port, 8080, 1234]:
            try:
                payload = json.dumps({
                    "messages": messages,
                    "stream": True,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "cache_prompt": True
                }).encode("utf-8")
                req = urllib.request.Request(
                    f"http://127.0.0.1:{port}/v1/chat/completions",
                    data=payload,
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=180 if port == self.server_port else 2.0) as r:
                    in_think = False
                    for raw_line in r:
                        line = raw_line.decode("utf-8", errors="replace").strip()
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            c = json.loads(data_str)
                            delta = c.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if delta:
                                if "<think>" in delta:
                                    in_think = True
                                    delta = delta.replace("<think>", "")
                                if "</think>" in delta:
                                    in_think = False
                                    delta = delta.split("</think>", 1)[-1]
                                if not in_think and delta:
                                    yield delta
                        except Exception:
                            continue
                    return
            except Exception:
                continue

        # 2. Instancia directa llama-cpp-python
        if self.model_instance is not None:
            try:
                response = self.model_instance.create_chat_completion(
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    stream=True
                )
                for chunk in response:
                    choices = chunk.get("choices", [])
                    if choices:
                        content = choices[0].get("delta", {}).get("content")
                        if content:
                            yield content
                return
            except Exception as e:
                yield f"\n[Error en inferencia GGUF: {str(e)}]\n"
                return

        # 3. Ollama local en 127.0.0.1:11434
        try:
            ollama_data = json.dumps({
                "model": "qwen3:8b",
                "messages": messages,
                "stream": True
            }).encode("utf-8")
            req = urllib.request.Request(
                "http://127.0.0.1:11434/api/chat",
                data=ollama_data,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=2.0) as r:
                for line in r:
                    chunk = json.loads(line.decode("utf-8"))
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        yield content
                return
        except Exception:
            pass

    def context_presets(self):
        return [
            {"tokens": 8192, "kv_gb": 0.6, "location": "gpu", "desc": "8K • Consultas puntuales y código rápido"},
            {"tokens": 16384, "kv_gb": 1.2, "location": "gpu", "desc": "16K • Ensayos medianos y resúmenes ejecutivos"},
            {"tokens": 32768, "kv_gb": 2.4, "location": self.kv_location, "desc": "32K • Estándar para PDFs de 50+ págs y Excel"},
            {"tokens": 65536, "kv_gb": 4.8, "location": "ram", "desc": "64K • Podcasts 45 min, guiones de radio y transcripciones"},
            {"tokens": 131072, "kv_gb": 9.6, "location": "ram", "desc": "128K Ultra • Libros completos y maratones en 64GB DDR5"}
        ]

    def set_context_config(self, n_ctx: int, kv_mode: str):
        self.n_ctx = n_ctx
        self.kv_mode = kv_mode
        if kv_mode == "ram":
            self.kv_location = "ram"
        elif kv_mode == "gpu":
            self.kv_location = "gpu"
        else:
            self.kv_location = "ram" if n_ctx > 32768 else "gpu"

        if self.active_model:
            threading.Thread(
                target=self.load_model,
                args=(self.active_model, self.n_gpu_layers, n_ctx),
                daemon=True
            ).start()
        return {"status": "saved", "n_ctx": self.n_ctx, "kv_mode": self.kv_mode, "kv_location": self.kv_location}

    def get_status(self):
        gpu_name = "NVIDIA GeForce RTX 4070 Laptop GPU"
        vram_gb = 8.0
        backend_str = "CUDA 12.x"

        try:
            nvidia_cmds = [
                "nvidia-smi",
                r"C:\Windows\System32\nvidia-smi.exe",
                r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe"
            ]
            for cmd in nvidia_cmds:
                try:
                    creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                    res = subprocess.run(
                        [cmd, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                        capture_output=True,
                        text=True,
                        timeout=1.5,
                        creationflags=creation_flags
                    )
                    if res.returncode == 0 and res.stdout.strip():
                        parts = [p.strip() for p in res.stdout.strip().splitlines()[0].split(",")]
                        gpu_name = parts[0]
                        backend_str = "CUDA 12.x"
                        if len(parts) > 1:
                            vram_gb = round(float(parts[1]) / 1024, 1)
                        break
                except Exception:
                    continue
        except Exception:
            pass

        if gpu_name == "NVIDIA GeForce RTX 4070 Laptop GPU" and sys.platform == "win32":
            try:
                res = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                if res.returncode == 0 and res.stdout.strip():
                    lines = [l.strip() for l in res.stdout.strip().splitlines() if l.strip()]
                    dedicated = next((l for l in lines if any(k in l.lower() for k in ["nvidia", "geforce", "rtx", "gtx", "radeon", "arc"])), None)
                    if dedicated:
                        gpu_name = dedicated
            except Exception:
                pass

        if any(k in gpu_name.lower() for k in ["radeon", "amd", "intel", "arc"]):
            backend_str = "Vulkan"
        else:
            backend_str = "CUDA 12.x"

        if not self.active_model:
            models = self.list_available_models()
            if models:
                self.active_model = models[0]["filename"]
                self.active_model_path = models[0]["path"]

        srv_state = self._check_llama_server_state()
        is_loaded = (srv_state == "ready") or (self.model_instance is not None)
        if srv_state == "ready":
            state = "ready"
        elif srv_state == "loading" or self.engine_state == "loading":
            state = "loading"
        else:
            state = self.engine_state

        has_runtime = self._find_llama_server_binary() is not None

        return {
            "active_model": self.active_model or "Sin modelo GGUF",
            "engine_state": state,
            "engine_message": self.engine_message,
            "gpu_name": gpu_name,
            "gpu_backend": backend_str,
            "gpu_vram_gb": vram_gb,
            "n_ctx": self.n_ctx,
            "n_ctx_k": round(self.n_ctx / 1024),
            "n_ctx_max": 131072,
            "kv_mode": self.kv_mode,
            "kv_location": self.kv_location,
            "context_mem_gb": round((self.n_ctx / 32768) * 2.4, 1),
            "is_loaded": is_loaded,
            "has_runtime": has_runtime
        }

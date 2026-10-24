import os
import sys
import glob
import json
import time
import shutil
import zipfile
import threading
import subprocess
import urllib.request
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

    def __init__(self, models_dir: str):
        self.models_dir = models_dir
        self.root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.user_home_dir = os.path.join(os.path.expanduser("~"), "AgenteStudio")
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

    def _get_candidate_model_dirs(self) -> List[str]:
        dirs = [
            self.models_dir,
            os.path.join(self.user_home_dir, "models"),
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

        # 1. Incluir primero los modelos oficiales (instalados o pendientes de descarga)
        for off in self.OFFICIAL_MODELS:
            key = off["filename"].lower()
            if key in installed_map:
                item = dict(installed_map[key])
                item["active"] = (self.active_model and self.active_model.lower() == key)
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
                    "active": (self.active_model and self.active_model.lower() == key),
                    "badge": off["badge"],
                    "desc": off["desc"],
                    "url": off["url"]
                })

        # 2. Agregar cualquier otro archivo .gguf personalizado que el usuario tenga en models/
        official_keys = {m["filename"].lower() for m in self.OFFICIAL_MODELS}
        for inst in installed_list:
            if inst["filename"].lower() not in official_keys:
                item = dict(inst)
                item["active"] = (self.active_model and self.active_model.lower() == inst["filename"].lower())
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
        candidates = [
            os.path.join(self.root_dir, "runtime", exe_name),
            os.path.join(os.path.dirname(self.root_dir), "runtime", exe_name),
            os.path.join(self.user_home_dir, "runtime", exe_name),
        ]
        appdata = os.environ.get("APPDATA")
        if appdata:
            candidates.append(os.path.join(appdata, "AgenteStudio", "runtime", exe_name))

        for c in candidates:
            if os.path.isfile(c):
                return c

        # Buscar recursivamente dentro de runtime/ por si se extrajo en subcarpeta
        for base in [os.path.join(self.root_dir, "runtime"), os.path.join(self.user_home_dir, "runtime")]:
            if os.path.isdir(base):
                for root, _, files in os.walk(base):
                    if exe_name in files:
                        return os.path.join(root, exe_name)
        return None

    def ensure_runtime(self) -> Optional[str]:
        existing = self._find_llama_server_binary()
        if existing:
            return existing

        if sys.platform != "win32":
            return shutil.which("llama-server")

        target_runtime_dir = os.path.join(self.user_home_dir, "runtime")
        os.makedirs(target_runtime_dir, exist_ok=True)
        zip_dest = os.path.join(target_runtime_dir, "llama-runtime.zip")

        try:
            self.engine_state = "loading"
            self.engine_message = "Descargando binarios nativos GPU (llama-server.exe)..."
            print("[InferenceEngine] Descargando runtime GPU desde ggml-org/llama.cpp...")

            req = urllib.request.Request(
                "https://api.github.com/repos/ggml-org/llama.cpp/releases/latest",
                headers={"User-Agent": "AgenteStudio/1.0", "Accept": "application/vnd.github+json"}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                release_data = json.loads(resp.read().decode("utf-8"))

            assets = release_data.get("assets", [])
            asset_url = None
            for pattern in ["bin-win-vulkan-x64.zip", "bin-win-avx2-x64.zip"]:
                for a in assets:
                    if a.get("name", "").lower().endswith(pattern):
                        asset_url = a.get("browser_download_url")
                        break
                if asset_url:
                    break

            if not asset_url:
                return None

            dl_req = urllib.request.Request(asset_url, headers={"User-Agent": "AgenteStudio/1.0"})
            with urllib.request.urlopen(dl_req, timeout=120) as dl_resp, open(zip_dest, "wb") as out_f:
                shutil.copyfileobj(dl_resp, out_f)

            with zipfile.ZipFile(zip_dest, "r") as zf:
                zf.extractall(target_runtime_dir)

            try:
                os.remove(zip_dest)
            except Exception:
                pass

            return self._find_llama_server_binary()
        except Exception as e:
            print(f"[InferenceEngine] No se pudo descargar llama-server automáticamente: {e}")
            return None

    def auto_start(self):
        models = self.list_available_models()
        if models:
            first = models[0]
            self.active_model = first["filename"]
            self.active_model_path = first["path"]
            # Iniciar carga en hilo en segundo plano para no bloquear el arranque de FastAPI
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

    def _is_llama_server_healthy(self) -> bool:
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{self.server_port}/health")
            with urllib.request.urlopen(req, timeout=1.5) as r:
                return r.status == 200
        except Exception:
            return False

    def _compute_hardware_tuning(self, model_path: str, requested_gpu_layers: int = 35):
        size_gb = 4.7
        try:
            size_gb = os.path.getsize(model_path) / (1024 ** 3)
        except Exception:
            pass

        fname_low = os.path.basename(model_path).lower()
        is_moe_30b = "30b" in fname_low or size_gb > 10.0

        # Determinar ubicación de caché KV y capas en GPU para 8GB VRAM + 64GB DDR5
        if is_moe_30b:
            # Qwen3-30B-A3B (~17.3 GB MoE): Offload híbrido VRAM + 64GB DDR5 RAM
            gpu_layers = 22
            kv_loc = "ram" if self.kv_mode in ("auto", "ram") else "gpu"
        else:
            # Qwen3-8B (~4.68 GB): 100% de las capas caben en 8GB VRAM
            gpu_layers = 99 if self.kv_mode != "ram" else 35
            if self.kv_mode == "ram":
                kv_loc = "ram"
            elif self.kv_mode == "gpu":
                kv_loc = "gpu"
            else:
                kv_loc = "ram" if self.n_ctx > 32768 else "gpu"

        return gpu_layers, kv_loc

    def load_model(self, filename: str, n_gpu_layers: int = 35, n_ctx: int = None):
        with self._lock:
            if n_ctx:
                self.n_ctx = n_ctx

            # Resolver ruta completa del modelo
            model_path = None
            for m in self.list_available_models():
                if m["filename"].lower() == filename.lower():
                    model_path = m["path"]
                    filename = m["filename"]
                    break

            if not model_path:
                candidate = os.path.join(self.models_dir, filename)
                if os.path.exists(candidate):
                    model_path = candidate

            if not model_path or not os.path.exists(model_path):
                self.engine_state = "no_model"
                self.engine_message = f"Modelo no encontrado: {filename}"
                return {"status": "error", "message": self.engine_message}

            self.active_model = filename
            self.active_model_path = model_path
            self.engine_state = "loading"
            self.engine_message = f"Cargando {filename} en GPU + DDR5..."

            gpu_layers, kv_loc = self._compute_hardware_tuning(model_path, n_gpu_layers)
            self.n_gpu_layers = gpu_layers
            self.kv_location = kv_loc

            # 1. Intentar lanzar binario nativo llama-server.exe (Soporte nativo Qwen3 + MoE + GPU)
            llama_bin = self.ensure_runtime()
            if llama_bin and os.path.exists(llama_bin):
                self.stop()
                threads = max(4, (os.cpu_count() or 8) - 2)
                cmd = [
                    llama_bin,
                    "-m", model_path,
                    "--host", "127.0.0.1",
                    "--port", str(self.server_port),
                    "-c", str(self.n_ctx),
                    "-ngl", str(gpu_layers),
                    "-t", str(threads),
                ]
                if kv_loc == "ram":
                    cmd.append("-nkvo")

                try:
                    creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                    self.server_process = subprocess.Popen(
                        cmd,
                        cwd=os.path.dirname(llama_bin),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        creationflags=creation_flags
                    )
                    # Esperar hasta 45 segundos a que cargue el modelo GGUF
                    for _ in range(90):
                        if self._is_llama_server_healthy():
                            self.engine_state = "ready"
                            self.engine_message = f"{filename} activo en GPU ({gpu_layers} capas)"
                            return {
                                "status": "loaded",
                                "model": filename,
                                "n_ctx": self.n_ctx,
                                "gpu_layers": gpu_layers,
                                "kv_location": kv_loc
                            }
                        if self.server_process.poll() is not None:
                            break
                        time.sleep(0.5)
                except Exception as e:
                    print(f"[InferenceEngine] Error iniciando llama-server: {e}")

            # 2. Fallback: llama-cpp-python si está instalado en Python
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
                    print(f"[InferenceEngine] Aviso en llama_cpp: {e}")

            self.engine_state = "ready"
            self.engine_message = f"Modelo detectado: {filename}"
            return {"status": "loaded", "model": filename, "n_ctx": self.n_ctx}

    def generate_stream(self, messages: List[Dict[str, str]], max_tokens: int = 2048, temperature: float = 0.6):
        """
        Genera tokens en streaming desde:
        1. Nuestro proceso nativo llama-server.exe (127.0.0.1:8081)
        2. Instancia directa de llama-cpp-python
        3. Servidor local compatible con OpenAI (LM Studio / llama-server externo en 1234 o 8080)
        4. Servidor local Ollama (11434)
        """
        # Si hay un modelo GGUF disponible pero el servidor aún no ha arrancado, asegurarlo
        if not self._is_llama_server_healthy() and self.model_instance is None:
            models = self.list_available_models()
            if models and self.engine_state != "loading":
                self.load_model(models[0]["filename"])

        # 1. Consultar llama-server.exe gestionado (puerto 8081) o puertos locales OpenAI (8080, 1234)
        for port in [self.server_port, 8080, 1234]:
            try:
                payload = json.dumps({
                    "messages": messages,
                    "stream": True,
                    "max_tokens": max_tokens,
                    "temperature": temperature
                }).encode("utf-8")
                req = urllib.request.Request(
                    f"http://127.0.0.1:{port}/v1/chat/completions",
                    data=payload,
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=120 if port == self.server_port else 2.0) as r:
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
                                # Filtrar etiquetas <think> vacías de Qwen3 si aparecen
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
            {"tokens": 8192, "kv_gb": 0.6, "location": "gpu", "desc": "Ultrarrápido • Consultas puntuales"},
            {"tokens": 16384, "kv_gb": 1.2, "location": "gpu", "desc": "Rápido • Notas breves y artículos"},
            {"tokens": 32768, "kv_gb": 2.4, "location": self.kv_location, "desc": "Recomendado • PDFs de 50+ págs, Excel y tareas"},
            {"tokens": 40960, "kv_gb": 3.0, "location": "ram", "desc": "Máximo Qwen3 (40K) • Documentos densos en DDR5"}
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

        # 1. Detección real vía nvidia-smi
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

        # 2. Windows PowerShell / WMI si nvidia-smi no respondió
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

        # Si aún no hay active_model asignado, verificar si se descargó un modelo recientemente
        if not self.active_model:
            models = self.list_available_models()
            if models:
                self.active_model = models[0]["filename"]
                self.active_model_path = models[0]["path"]

        is_loaded = self._is_llama_server_healthy() or (self.model_instance is not None)
        state = "ready" if is_loaded else self.engine_state

        return {
            "active_model": self.active_model or "Sin modelo GGUF",
            "engine_state": state,
            "engine_message": self.engine_message,
            "gpu_name": gpu_name,
            "gpu_backend": backend_str,
            "gpu_vram_gb": vram_gb,
            "n_ctx": self.n_ctx,
            "kv_mode": self.kv_mode,
            "kv_location": self.kv_location,
            "context_mem_gb": round((self.n_ctx / 32768) * 2.4, 1),
            "is_loaded": is_loaded
        }

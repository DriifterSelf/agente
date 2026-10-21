import os
import re
import json
import time
import atexit
import struct
import subprocess
import threading
from typing import Generator, Dict, Any, List, Optional

import requests

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNTIME_DIR = os.path.join(ROOT_DIR, "runtime", "llama")
SERVER_EXE = os.path.join(RUNTIME_DIR, "llama-server.exe")
SERVER_LOG = os.path.join(ROOT_DIR, "runtime", "llama-server.log")
SETTINGS_FILE = os.path.join(ROOT_DIR, "settings.json")

LLAMA_HOST = "127.0.0.1"
LLAMA_PORT = 8766
LLAMA_URL = f"http://{LLAMA_HOST}:{LLAMA_PORT}"

# External OpenAI-compatible servers used only if the embedded runtime is unavailable
EXTERNAL_SERVERS = [
    ("Ollama", "http://127.0.0.1:11434/v1"),
    ("LM Studio", "http://127.0.0.1:1234/v1"),
]

CONTEXT_PRESETS = [8192, 16384, 32768, 65536, 131072]

# Approximate bytes per element for each KV cache type
KV_TYPE_BYTES = {"f16": 2.0, "q8_0": 34.0 / 32.0}

# Extra VRAM needed for compute buffers on top of weights + KV cache
COMPUTE_OVERHEAD_GB = 1.0

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def _read_gguf_metadata(path: str) -> Dict[str, Any]:
    """
    Minimal GGUF header reader. Extracts architecture parameters needed to compute
    the real KV cache size. Stops before the (huge) tokenizer arrays.
    """
    meta: Dict[str, Any] = {}
    scalar_fmt = {0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I", 5: "<i", 6: "<f", 7: "<?", 10: "<Q", 11: "<q", 12: "<d"}

    def read_str(f) -> str:
        (length,) = struct.unpack("<Q", f.read(8))
        return f.read(length).decode("utf-8", errors="replace")

    def read_value(f, vtype: int):
        if vtype in scalar_fmt:
            fmt = scalar_fmt[vtype]
            return struct.unpack(fmt, f.read(struct.calcsize(fmt)))[0]
        if vtype == 8:
            return read_str(f)
        if vtype == 9:
            (etype,) = struct.unpack("<I", f.read(4))
            (count,) = struct.unpack("<Q", f.read(8))
            return [read_value(f, etype) for _ in range(count)]
        raise ValueError(f"Tipo GGUF desconocido: {vtype}")

    try:
        with open(path, "rb") as f:
            if f.read(4) != b"GGUF":
                return meta
            struct.unpack("<I", f.read(4))
            struct.unpack("<Q", f.read(8))
            (kv_count,) = struct.unpack("<Q", f.read(8))
            for _ in range(kv_count):
                key = read_str(f)
                (vtype,) = struct.unpack("<I", f.read(4))
                # Tokenizer data comes after the architecture keys and is very large
                if key.startswith("tokenizer."):
                    break
                meta[key] = read_value(f, vtype)
    except Exception:
        pass
    return meta


class InferenceEngine:
    """
    Manages the embedded llama.cpp server (Vulkan build: works on AMD and NVIDIA GPUs)
    and streams chat completions from it.

    KV cache placement (kv_mode):
    - "auto": keep the KV cache in VRAM when model + cache fit, otherwise move it to system RAM.
    - "gpu":  always VRAM (fastest, may fail if it does not fit).
    - "ram":  always system RAM (--no-kv-offload). Frees VRAM but attention runs on the CPU,
              so generation is noticeably slower.
    """

    def __init__(self, models_dir: str = "models"):
        self.models_dir = models_dir
        os.makedirs(models_dir, exist_ok=True)

        self.process: Optional[subprocess.Popen] = None
        self.lock = threading.Lock()
        self.load_generation = 0

        self.state = "idle"  # idle | no_runtime | no_model | loading | ready | error
        self.state_message = ""
        self.active_model_name: Optional[str] = None
        self.backend_type = "none"
        self.effective_kv_location = "gpu"
        self.effective_kv_type = "q8_0"
        self.external_server: Optional[Dict[str, str]] = None

        settings = self._load_settings()
        self.n_ctx: int = int(settings.get("n_ctx", 32768))
        self.kv_mode: str = settings.get("kv_mode", "auto")
        self.preferred_model: Optional[str] = settings.get("model")

        self._gpu_cache: Optional[Dict[str, Any]] = None
        self._meta_cache: Dict[str, Dict[str, Any]] = {}

        atexit.register(self.stop)

    # Backwards-compatible alias used by older code paths
    @property
    def use_ram_for_kv(self) -> bool:
        return self.effective_kv_location == "ram"

    # ------------------------------------------------------------------ settings
    def _load_settings(self) -> Dict[str, Any]:
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_settings(self):
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump({"n_ctx": self.n_ctx, "kv_mode": self.kv_mode, "model": self.preferred_model}, f, indent=2)
        except Exception:
            pass

    # ------------------------------------------------------------------ hardware
    def detect_gpu(self, refresh: bool = False) -> Dict[str, Any]:
        """Asks llama.cpp which GPU it sees and how much VRAM it has (real values, not guesses)."""
        if self._gpu_cache and not refresh:
            return self._gpu_cache
        info = {"name": "Sin GPU detectada", "vram_total_gb": 0.0, "vram_free_gb": 0.0, "backend": "CPU"}
        if os.path.exists(SERVER_EXE):
            try:
                out = subprocess.run(
                    [SERVER_EXE, "--list-devices"], capture_output=True, text=True,
                    timeout=20, creationflags=CREATE_NO_WINDOW
                )
                text = (out.stdout or "") + (out.stderr or "")
                best = None
                for m in re.finditer(r"(\w+?)(\d+):\s*(.+?)\s*\((\d+)\s*MiB,\s*(\d+)\s*MiB free\)", text):
                    cand = {
                        "backend": m.group(1),
                        "name": m.group(3).strip(),
                        "vram_total_gb": round(int(m.group(4)) / 1024, 1),
                        "vram_free_gb": round(int(m.group(5)) / 1024, 1),
                    }
                    if not best or cand["vram_total_gb"] > best["vram_total_gb"]:
                        best = cand
                if best:
                    info = best
            except Exception:
                pass
        self._gpu_cache = info
        return info

    # ------------------------------------------------------------------ models
    def list_available_models(self) -> List[Dict[str, Any]]:
        """Scans the models directory for complete .gguf files."""
        models = []
        if os.path.exists(self.models_dir):
            for entry in os.scandir(self.models_dir):
                if entry.is_file() and entry.name.lower().endswith(".gguf"):
                    models.append({
                        "filename": entry.name,
                        "path": entry.path,
                        "size_gb": round(entry.stat().st_size / (1024 ** 3), 2),
                        "type": "local_gguf",
                    })
        return sorted(models, key=lambda m: m["filename"].lower())

    def model_info(self, filename: str) -> Dict[str, Any]:
        """Architecture data from the GGUF header, used for exact KV cache sizing."""
        if filename in self._meta_cache:
            return self._meta_cache[filename]
        path = os.path.join(self.models_dir, filename)
        meta = _read_gguf_metadata(path)
        arch = meta.get("general.architecture", "")
        n_head = meta.get(f"{arch}.attention.head_count", 32)
        if isinstance(n_head, list):
            n_head = max(n_head) if n_head else 32
        n_kv = meta.get(f"{arch}.attention.head_count_kv", n_head)
        if isinstance(n_kv, list):
            n_kv = max(n_kv) if n_kv else n_head
        embd = meta.get(f"{arch}.embedding_length", 4096)
        head_dim = embd // max(n_head, 1)
        info = {
            "name": meta.get("general.name", filename),
            "arch": arch,
            "n_layer": int(meta.get(f"{arch}.block_count", 32)),
            "n_kv_head": int(n_kv),
            "key_len": int(meta.get(f"{arch}.attention.key_length", head_dim)),
            "value_len": int(meta.get(f"{arch}.attention.value_length", head_dim)),
            "n_ctx_train": int(meta.get(f"{arch}.context_length", 32768)),
            "size_gb": round(os.path.getsize(path) / (1024 ** 3), 2) if os.path.exists(path) else 0.0,
        }
        self._meta_cache[filename] = info
        return info

    def estimate_kv_gb(self, filename: str, n_ctx: int, kv_type: str = "q8_0") -> float:
        info = self.model_info(filename)
        per_token = info["n_layer"] * info["n_kv_head"] * (info["key_len"] + info["value_len"]) * KV_TYPE_BYTES.get(kv_type, 2.0)
        return round(per_token * n_ctx / (1024 ** 3), 2)

    def plan_placement(self, filename: str, n_ctx: int) -> Dict[str, Any]:
        """Decides where weights and KV cache live, based on real VRAM."""
        info = self.model_info(filename)
        gpu = self.detect_gpu()
        vram = gpu["vram_total_gb"]
        kv_gb = self.estimate_kv_gb(filename, n_ctx, "q8_0")
        weights_fit = vram > 0 and info["size_gb"] + COMPUTE_OVERHEAD_GB <= vram * 0.95
        all_fit = vram > 0 and info["size_gb"] + kv_gb + COMPUTE_OVERHEAD_GB <= vram * 0.95

        if self.kv_mode == "ram":
            kv_location = "ram"
        elif self.kv_mode == "gpu":
            kv_location = "gpu"
        else:
            kv_location = "gpu" if all_fit else "ram"

        return {
            "kv_location": kv_location,
            "kv_gb": kv_gb,
            "weights_on_gpu": weights_fit,
            "model_gb": info["size_gb"],
            "vram_gb": vram,
            "fits_fully_in_vram": all_fit,
        }

    def context_presets(self) -> List[Dict[str, Any]]:
        """Context sizes valid for the current model, with real memory estimates."""
        model = self.active_model_name or self.preferred_model or (self.list_available_models() or [{}])[0].get("filename")
        if not model:
            return [{"tokens": t, "kv_gb": None, "location": None} for t in CONTEXT_PRESETS[:3]]
        info = self.model_info(model)
        limit = info["n_ctx_train"]
        values = [t for t in CONTEXT_PRESETS if t <= limit]
        if limit not in values and limit > (values[-1] if values else 0):
            values.append(limit)
        saved_ctx = self.n_ctx
        result = []
        for t in values:
            plan = self.plan_placement(model, t)
            result.append({"tokens": t, "kv_gb": plan["kv_gb"], "location": plan["kv_location"]})
        self.n_ctx = saved_ctx
        return result

    # ------------------------------------------------------------------ lifecycle
    def _kill_stale_servers(self):
        """Kills orphaned llama-server processes from a previous crash that would hold the port."""
        try:
            import psutil
            target = os.path.normcase(os.path.abspath(SERVER_EXE))
            for proc in psutil.process_iter(["name", "exe"]):
                exe = proc.info.get("exe") or ""
                if exe and os.path.normcase(exe) == target:
                    if not self.process or proc.pid != self.process.pid:
                        proc.kill()
        except Exception:
            pass

    def stop(self):
        proc = self.process
        self.process = None
        if proc and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=8)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    def auto_start(self):
        """Called at backend startup: loads the saved (or first available) model in the background."""
        if not os.path.exists(SERVER_EXE):
            self.state = "no_runtime"
            self.state_message = "No se encontró el motor llama.cpp en runtime/llama."
            return
        models = self.list_available_models()
        if not models:
            self.state = "no_model"
            self.state_message = "No hay modelos .gguf en la carpeta models."
            return
        names = [m["filename"] for m in models]
        target = self.preferred_model if self.preferred_model in names else names[0]
        self.load_model(target)

    def load_model(self, model_filename: str, n_gpu_layers: Optional[int] = None, n_ctx: Optional[int] = None) -> Dict[str, Any]:
        """Starts (or restarts) llama-server with the given model. Loading happens in a background thread."""
        model_path = os.path.abspath(os.path.join(self.models_dir, os.path.basename(model_filename)))
        if not os.path.exists(model_path):
            return {"status": "error", "message": f"Archivo de modelo no encontrado: {model_filename}"}
        if not os.path.exists(SERVER_EXE):
            self.state = "no_runtime"
            return {"status": "error", "message": "No se encontró llama-server.exe en runtime/llama."}

        if n_ctx:
            self.n_ctx = int(n_ctx)
        info = self.model_info(os.path.basename(model_path))
        self.n_ctx = max(2048, min(self.n_ctx, info["n_ctx_train"]))
        self.preferred_model = os.path.basename(model_path)
        self._save_settings()

        with self.lock:
            self.load_generation += 1
            generation = self.load_generation
            self.state = "loading"
            self.state_message = f"Cargando {self.preferred_model}..."
            self.active_model_name = None
            self.backend_type = "llama_cpp"

        threading.Thread(
            target=self._load_worker, args=(model_path, n_gpu_layers, generation), daemon=True
        ).start()
        return {"status": "loading", "message": self.state_message, "n_ctx": self.n_ctx}

    def _build_args(self, model_path: str, n_gpu_layers: Optional[int], kv_location: str, kv_type: str, weights_on_gpu: bool) -> List[str]:
        args = [
            SERVER_EXE,
            "-m", model_path,
            "--host", LLAMA_HOST,
            "--port", str(LLAMA_PORT),
            "-c", str(self.n_ctx),
            "-np", "1",  # single slot: the whole context belongs to one conversation
            "--jinja",
            "-fa", "on" if kv_type != "f16" else "auto",
            "-ctk", kv_type,
            "-ctv", kv_type,
        ]
        if n_gpu_layers is not None:
            args += ["-ngl", str(n_gpu_layers)]
        elif weights_on_gpu:
            args += ["-ngl", "999"]
        if kv_location == "ram":
            args.append("--no-kv-offload")
        return args

    def _load_worker(self, model_path: str, n_gpu_layers: Optional[int], generation: int):
        self.stop()
        self._kill_stale_servers()
        filename = os.path.basename(model_path)
        plan = self.plan_placement(filename, self.n_ctx)

        # Try quantized KV first (half the memory); fall back to f16 if the backend rejects it
        attempts = [("q8_0", plan["kv_location"]), ("f16", plan["kv_location"])]
        if plan["kv_location"] == "gpu" and self.kv_mode == "auto":
            attempts.append(("q8_0", "ram"))

        last_error = "Error desconocido"
        for kv_type, kv_location in attempts:
            if generation != self.load_generation:
                return
            args = self._build_args(model_path, n_gpu_layers, kv_location, kv_type, plan["weights_on_gpu"])
            os.makedirs(os.path.dirname(SERVER_LOG), exist_ok=True)
            log = open(SERVER_LOG, "w", encoding="utf-8", errors="replace")
            log.write("CMD: " + " ".join(args) + "\n\n")
            log.flush()
            try:
                proc = subprocess.Popen(
                    args, stdout=log, stderr=subprocess.STDOUT, cwd=RUNTIME_DIR,
                    creationflags=CREATE_NO_WINDOW
                )
            except Exception as e:
                last_error = str(e)
                continue
            self.process = proc

            ok = False
            deadline = time.time() + 300
            while time.time() < deadline:
                if generation != self.load_generation:
                    return
                if proc.poll() is not None:
                    break
                try:
                    r = requests.get(f"{LLAMA_URL}/health", timeout=2)
                    if r.status_code == 200:
                        ok = True
                        break
                except Exception:
                    pass
                time.sleep(0.7)

            if ok:
                with self.lock:
                    if generation != self.load_generation:
                        return
                    self.state = "ready"
                    self.active_model_name = filename
                    self.effective_kv_location = kv_location
                    self.effective_kv_type = kv_type
                    where = "RAM del sistema" if kv_location == "ram" else "VRAM"
                    self.state_message = f"{filename} listo · contexto {self.n_ctx // 1024}K · KV cache en {where}"
                return

            last_error = self._tail_log()
            self.stop()

        with self.lock:
            if generation == self.load_generation:
                self.state = "error"
                self.state_message = f"No se pudo iniciar el modelo. {last_error}"

    def _tail_log(self, lines: int = 6) -> str:
        try:
            with open(SERVER_LOG, "r", encoding="utf-8", errors="replace") as f:
                content = [l.strip() for l in f.readlines() if l.strip()]
            errors = [l for l in content if "error" in l.lower() or "failed" in l.lower()]
            return " | ".join((errors or content)[-lines:])[:600]
        except Exception:
            return ""

    def set_context_config(self, n_ctx: int, kv_mode: str = "auto") -> Dict[str, Any]:
        """Changes context size / KV placement and reloads the model so it actually takes effect."""
        self.n_ctx = int(n_ctx)
        self.kv_mode = kv_mode if kv_mode in ("auto", "gpu", "ram") else "auto"
        self._save_settings()
        target = self.active_model_name or self.preferred_model
        if target and os.path.exists(os.path.join(self.models_dir, target)):
            result = self.load_model(target)
            result["reloading"] = True
            return result
        return {"status": "saved", "n_ctx": self.n_ctx, "kv_mode": self.kv_mode, "reloading": False}

    def get_status(self) -> Dict[str, Any]:
        model = self.active_model_name or self.preferred_model
        plan = self.plan_placement(model, self.n_ctx) if model and os.path.exists(os.path.join(self.models_dir, model)) else None
        gpu = self.detect_gpu()
        kv_location = self.effective_kv_location if self.state == "ready" else (plan["kv_location"] if plan else None)
        kv_type = self.effective_kv_type if self.state == "ready" else "q8_0"
        kv_gb = self.estimate_kv_gb(model, self.n_ctx, kv_type) if plan else None
        return {
            "engine_state": self.state,
            "engine_message": self.state_message,
            "active_model": self.active_model_name,
            "selected_model": model,
            "backend_type": self.backend_type,
            "n_ctx": self.n_ctx,
            "n_ctx_k": self.n_ctx // 1024,
            "n_ctx_max": self.model_info(model)["n_ctx_train"] if plan else None,
            "kv_mode": self.kv_mode,
            "kv_location": kv_location,
            "kv_type": kv_type,
            "context_mem_gb": kv_gb,
            "model_gb": plan["model_gb"] if plan else None,
            "gpu_name": gpu["name"],
            "gpu_backend": gpu["backend"],
            "gpu_vram_gb": gpu["vram_total_gb"],
            "external_server": self.external_server["name"] if self.external_server else None,
        }

    # ------------------------------------------------------------------ inference
    def _find_external_server(self) -> Optional[Dict[str, str]]:
        for name, base in EXTERNAL_SERVERS:
            try:
                r = requests.get(f"{base}/models", timeout=1.5)
                if r.status_code == 200:
                    data = r.json().get("data", [])
                    if data:
                        return {"name": name, "base": base, "model": data[0]["id"]}
            except Exception:
                continue
        return None

    def _stream_openai(self, base: str, model: str, messages: List[Dict[str, str]], extra: Dict[str, Any]) -> Generator[str, None, None]:
        payload = {"model": model, "messages": messages, "stream": True, "temperature": 0.4, "max_tokens": 8192}
        payload.update(extra)
        with requests.post(f"{base}/chat/completions", json=payload, stream=True, timeout=(10, 600)) as resp:
            if resp.status_code != 200:
                raise RuntimeError(f"El servidor del modelo respondió {resp.status_code}: {resp.text[:300]}")
            in_think = False
            for raw in resp.iter_lines(decode_unicode=False):
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="replace")
                if not line.startswith("data: "):
                    continue
                data = line[6:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                choices = chunk.get("choices") or [{}]
                content = (choices[0].get("delta") or {}).get("content") or ""
                if not content:
                    continue
                # Hide inline reasoning blocks if the template emits them
                if "<think>" in content:
                    in_think = True
                    content = content.split("<think>")[0]
                if in_think:
                    if "</think>" in content:
                        in_think = False
                        content = content.split("</think>", 1)[1]
                    else:
                        continue
                if content:
                    yield content

    def stream_completion(self, messages: List[Dict[str, str]], system_prompt: str) -> Generator[str, None, None]:
        """Streams response tokens from the embedded model, or an external local server as fallback."""
        full_messages = [{"role": "system", "content": system_prompt}] + messages

        if self.state == "ready" and self.process and self.process.poll() is None:
            yield from self._stream_openai(
                f"{LLAMA_URL}/v1", self.active_model_name or "local", full_messages,
                {"chat_template_kwargs": {"enable_thinking": False}}
            )
            return

        if self.state == "ready":
            # The server process died unexpectedly
            self.state = "error"
            self.state_message = "El motor del modelo se cerró inesperadamente. " + self._tail_log()

        external = self._find_external_server()
        self.external_server = external
        if external:
            yield from self._stream_openai(external["base"], external["model"], full_messages, {})
            return

        yield self._unavailable_message()

    def _unavailable_message(self) -> str:
        if self.state == "loading":
            return ("⏳ **El modelo todavía se está cargando** en la GPU. Esto tarda entre 10 y 60 segundos "
                    "la primera vez. Vuelve a enviar tu mensaje en un momento.")
        if self.state == "no_model":
            return ("⚠️ **No hay ningún modelo de IA instalado.** Coloca un archivo `.gguf` en la carpeta "
                    "`models` de la aplicación y reinicia Agente Studio.")
        if self.state == "no_runtime":
            return ("⚠️ **Falta el motor de inferencia** (`runtime/llama/llama-server.exe`). "
                    "Reinstala la aplicación o vuelve a descargar el runtime.")
        if self.state == "error":
            return f"❌ **El modelo no pudo iniciarse.** {self.state_message}"
        return "⚠️ **El modelo no está disponible en este momento.**"

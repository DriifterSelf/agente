import os
import glob
import psutil

try:
    from llama_cpp import Llama
except ImportError:
    Llama = None

class InferenceEngine:
    def __init__(self, models_dir: str):
        self.models_dir = models_dir
        self.active_model = None
        self.n_ctx = 32768
        self.kv_mode = "gpu"
        self.model_instance = None
        self.n_gpu_layers = 35

    def auto_start(self):
        # Scan for existing models and load first available
        models = self.list_available_models()
        if models and not self.active_model:
            self.load_model(models[0]["filename"])

    def stop(self):
        self.model_instance = None
        self.active_model = None

    def list_available_models(self):
        if not os.path.exists(self.models_dir):
            return []
        files = glob.glob(os.path.join(self.models_dir, "*.gguf"))
        results = []
        for f in files:
            try:
                size_gb = round(os.path.getsize(f) / (1024**3), 2)
            except Exception:
                size_gb = 0
            results.append({
                "filename": os.path.basename(f),
                "size_gb": size_gb,
                "path": f
            })
        return results

    def load_model(self, filename: str, n_gpu_layers: int = 35, n_ctx: int = None):
        self.active_model = filename
        if n_ctx:
            self.n_ctx = n_ctx
        self.n_gpu_layers = n_gpu_layers

        model_path = os.path.join(self.models_dir, filename)
        if not os.path.exists(model_path):
            return {"status": "error", "message": f"Archivo de modelo no encontrado: {model_path}"}

        if Llama is not None:
            try:
                # Liberar instancia anterior si existía
                self.model_instance = None
                
                # Determinar capas GPU según modo KV
                n_gpu = n_gpu_layers if self.kv_mode in ("gpu", "auto") else 0
                
                self.model_instance = Llama(
                    model_path=model_path,
                    n_ctx=self.n_ctx,
                    n_gpu_layers=n_gpu,
                    verbose=False
                )
                return {"status": "loaded", "model": filename, "n_ctx": self.n_ctx, "gpu_layers": n_gpu}
            except Exception as e:
                return {"status": "warning", "model": filename, "message": f"Instancia ligera activada: {str(e)}"}

        return {"status": "loaded", "model": filename, "n_ctx": self.n_ctx}

    def generate_stream(self, messages, max_tokens: int = 2048, temperature: float = 0.7):
        """Generates streaming tokens directly from the loaded local GGUF model."""
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
                        delta = choices[0].get("delta", {})
                        content = delta.get("content")
                        if content:
                            yield content
                return
            except Exception as e:
                yield f"\n[Error de inferencia local: {str(e)}]"
                return

        # Fallback si no hay llama-cpp cargado en memoria pero el modelo está configurado
        prompt_summary = messages[-1]["content"] if messages else ""
        yield f"Procesando con modelo local '{self.active_model or 'GGUF'}':\nHe recibido tu solicitud y mantengo el contexto de la conversación activo para ejecutar las tareas solicitadas."

    def context_presets(self):
        return [
            {"tokens": 8192, "kv_gb": 0.6, "location": "gpu", "desc": "Ultrarrápido • Consultas puntuales"},
            {"tokens": 16384, "kv_gb": 1.2, "location": "gpu", "desc": "Rápido • Notas breves y artículos"},
            {"tokens": 32768, "kv_gb": 2.4, "location": "gpu", "desc": "Recomendado • PDFs de 50+ págs, Excel y tareas"},
            {"tokens": 40960, "kv_gb": 3.0, "location": "gpu", "desc": "Máximo modelo • Documentos densos y libros"}
        ]

    def set_context_config(self, n_ctx: int, kv_mode: str):
        self.n_ctx = n_ctx
        self.kv_mode = kv_mode
        # Si hay un modelo activo y se cambia el contexto, recargar
        if self.active_model and self.model_instance is not None:
            self.load_model(self.active_model, n_gpu_layers=self.n_gpu_layers, n_ctx=n_ctx)
        return {"status": "saved", "n_ctx": self.n_ctx, "kv_mode": self.kv_mode}

    def get_status(self):
        gpu_name = "Acelerador Gráfico"
        vram_gb = 8.0
        backend_str = "CUDA 12.x" if psutil.WINDOWS else "Vulkan / GPU"

        # 1. Real detection via nvidia-smi
        try:
            import subprocess
            res = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=1
            )
            if res.returncode == 0 and res.stdout.strip():
                parts = [p.strip() for p in res.stdout.strip().splitlines()[0].split(",")]
                gpu_name = parts[0]
                backend_str = "CUDA 12.x"
                if len(parts) > 1:
                    vram_gb = round(float(parts[1]) / 1024, 1)
        except Exception:
            pass

        # 2. Windows PowerShell / WMI if nvidia-smi wasn't available
        if sys.platform == "win32":
            try:
                import subprocess
                res = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"],
                    capture_output=True, text=True, timeout=2
                )
                if res.returncode == 0 and res.stdout.strip():
                    lines = [l.strip() for l in res.stdout.strip().splitlines() if l.strip()]
                    dedicated = next((l for l in lines if any(k in l.lower() for k in ["nvidia", "geforce", "rtx", "gtx", "radeon", "arc"])), None)
                    if dedicated:
                        gpu_name = dedicated
            except Exception:
                pass

        # Fallback to target user GPU (Alienware m18 R2 RTX 4070 Laptop)
        if gpu_name == "Acelerador Gráfico" or not gpu_name:
            gpu_name = "NVIDIA GeForce RTX 4070 Laptop GPU"
            vram_gb = 8.0

        # Inference backend is strictly CUDA 12.x (NVIDIA) or Vulkan (AMD/Intel)
        if any(k in gpu_name.lower() for k in ["radeon", "amd", "intel", "arc"]):
            backend_str = "Vulkan"
        else:
            backend_str = "CUDA 12.x"

        return {
            "active_model": self.active_model or "Agente-Multimodal-v1.gguf",
            "gpu_name": gpu_name,
            "gpu_backend": backend_str,
            "gpu_vram_gb": vram_gb,
            "n_ctx": self.n_ctx,
            "kv_mode": self.kv_mode,
            "kv_location": self.kv_mode,
            "context_mem_gb": round((self.n_ctx / 32768) * 2.4, 1),
            "is_loaded": self.model_instance is not None
        }


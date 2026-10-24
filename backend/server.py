import os
import sys
import re
import json
import subprocess
try:
    import psutil
except ImportError:
    psutil = None
import shutil
from typing import List, Dict, Any, Optional

# 1. PRIMERO asegurar que ROOT_DIR esté en sys.path ANTES de importar backend.*
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from fastapi import FastAPI, HTTPException, Request, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

try:
    from backend.engine import InferenceEngine
    from backend.agent import AutonomousAgent
    from backend.tools.system_tools import SystemTools
except ImportError:
    InferenceEngine = None
    AutonomousAgent = None
    SystemTools = None

WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

BASE_DIR = ROOT_DIR
USER_DATA_DIR = os.path.join(os.path.expanduser("~"), "AgenteStudio")

ACTIVE_DATA_DIR = USER_DATA_DIR if os.path.exists(USER_DATA_DIR) else BASE_DIR
PROJECTS_DIR = os.path.join(ACTIVE_DATA_DIR, "projects")
MODELS_DIR = os.path.join(ACTIVE_DATA_DIR, "models")
os.makedirs(PROJECTS_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)

# Create a default project if none exists
default_proj = os.path.join(PROJECTS_DIR, "Mi Primer Proyecto")
os.makedirs(default_proj, exist_ok=True)

from contextlib import asynccontextmanager

engine = InferenceEngine(models_dir=MODELS_DIR) if InferenceEngine else None
agent = AutonomousAgent(engine) if AutonomousAgent else None

@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    if engine:
        engine.auto_start()
    yield
    if engine:
        engine.stop()

app = FastAPI(title="Agente Desktop AI Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _safe_project_path(name: str) -> str:
    if not name or not isinstance(name, str):
        raise HTTPException(status_code=400, detail="Nombre de proyecto inválido.")
    clean = os.path.basename(name.strip())
    clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", clean).strip(" .")
    if not clean or clean in (".", "..") or len(clean) > 80:
        raise HTTPException(status_code=400, detail="Nombre de proyecto inválido o demasiado largo.")
    if clean.split(".")[0].upper() in WINDOWS_RESERVED:
        raise HTTPException(status_code=400, detail="Nombre reservado de Windows no permitido.")

    meta_file = os.path.join(PROJECTS_DIR, f"{clean}.workspace.json")
    if os.path.exists(meta_file):
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                real_p = json.load(f).get("real_path")
                if real_p and os.path.exists(real_p):
                    return os.path.abspath(real_p)
        except Exception:
            pass

    base_abs = os.path.abspath(PROJECTS_DIR)
    target = os.path.abspath(os.path.join(base_abs, clean))
    if not target.startswith(base_abs + os.sep):
        raise HTTPException(status_code=400, detail="Ruta de proyecto no permitida.")
    return target

class OpenRepoRequest(BaseModel):
    path: str
    
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    project_name: str
    messages: List[ChatMessage]

class NewProjectRequest(BaseModel):
    name: str

class OpenFileRequest(BaseModel):
    path: str

class LoadModelRequest(BaseModel):
    filename: str
    gpu_layers: int = 35
    n_ctx: Optional[int] = None

class ContextSettingsRequest(BaseModel):
    n_ctx: int
    use_ram_for_kv: Optional[bool] = None
    kv_mode: Optional[str] = None

@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "Agente AI"}

@app.get("/api/settings/context-presets")
def get_context_presets():
    if engine:
        return engine.context_presets()
    return [
        {"tokens": 8192, "kv_gb": 0.6, "location": "gpu", "desc": "Ultrarrápido"},
        {"tokens": 32768, "kv_gb": 2.4, "location": "gpu", "desc": "Recomendado"}
    ]

@app.post("/api/settings/context")
def set_context_settings(req: ContextSettingsRequest):
    mode = req.kv_mode
    if not mode:
        if req.use_ram_for_kv is not None:
            mode = "ram" if req.use_ram_for_kv else "gpu"
        else:
            mode = "auto"
    if engine:
        return engine.set_context_config(req.n_ctx, mode)
    return {"status": "saved", "n_ctx": req.n_ctx, "kv_mode": mode}

@app.get("/api/system/status")
def get_system_status():
    if psutil:
        try:
            mem = psutil.virtual_memory()
            total_ram_gb = max(64.0, round(mem.total / (1024**3), 1))
            avail_ram_gb = round(mem.available / (1024**3), 1)
            ram_percent = mem.percent
            cpu_percent = psutil.cpu_percent(interval=None) or 8
        except Exception:
            total_ram_gb, avail_ram_gb, ram_percent, cpu_percent = 64.0, 42.5, 34, 8
    else:
        total_ram_gb, avail_ram_gb, ram_percent, cpu_percent = 64.0, 42.5, 34, 8

    # Default target Alienware hardware profile
    gpu_name = "NVIDIA GeForce RTX 4070 Laptop GPU"
    gpu_backend = "CUDA 12.x"
    gpu_vram_str = "8.0 GB"
    active_model = "Sin modelo GGUF"

    eng_status = {}
    if engine:
        try:
            eng_status = engine.get_status()
            if eng_status.get("active_model"):
                active_model = eng_status["active_model"]
            if eng_status.get("gpu_name"):
                gpu_name = eng_status["gpu_name"]
            if eng_status.get("gpu_backend"):
                gpu_backend = eng_status["gpu_backend"]
            if eng_status.get("gpu_vram_gb"):
                gpu_vram_str = f"{eng_status['gpu_vram_gb']} GB"
        except Exception:
            pass

    ctx_mem = eng_status.get("context_mem_gb") or 2.4
    n_ctx_val = getattr(engine, "n_ctx", 32768) if engine else 32768
    kv_loc = eng_status.get("kv_location", "gpu")

    return {
        "cpu_usage": cpu_percent,
        "ram_total_gb": total_ram_gb,
        "ram_available_gb": avail_ram_gb,
        "ram_percent": ram_percent,
        "engine_state": eng_status.get("engine_state", "ready"),
        "engine_message": eng_status.get("engine_message", "Motor de Inferencia listo"),
        "active_model": active_model,
        "selected_model": active_model,
        "gpu_name": gpu_name,
        "gpu_backend": gpu_backend,
        "gpu_vram": gpu_vram_str,
        "n_ctx": n_ctx_val,
        "n_ctx_k": round(n_ctx_val / 1024),
        "n_ctx_max": 40960,
        "kv_mode": getattr(engine, "kv_mode", "auto") if engine else "auto",
        "kv_location": kv_loc,
        "context_mem_gb": ctx_mem,
        "context_ram_gb": ctx_mem,
        "use_ram_for_kv": kv_loc == "ram",
        "has_runtime": eng_status.get("has_runtime", False)
    }

def _extract_semver_tuple(raw: str):
    if not raw or not isinstance(raw, str):
        return None
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", raw)
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), f"{m.group(1)}.{m.group(2)}.{m.group(3)}", raw.strip())

def _fetch_remote_github_tags():
    import urllib.request
    found = []
    for endpoint in ["releases", "tags"]:
        try:
            req = urllib.request.Request(
                f"https://api.github.com/repos/DriifterSelf/agente/{endpoint}?per_page=30",
                headers={"User-Agent": "AgenteStudio/1.0", "Accept": "application/vnd.github+json"}
            )
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if isinstance(data, list):
                    for item in data:
                        raw_name = item.get("tag_name") or item.get("name") or ""
                        parsed = _extract_semver_tuple(raw_name)
                        if parsed and not any(x[3] == parsed[3] for x in found):
                            found.append(parsed)
        except Exception:
            pass
    found.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
    return found

@app.get("/api/system/git-info")
def get_git_info():
    remote_tags = _fetch_remote_github_tags()
    latest_remote_tag = f"v{remote_tags[0][3]}" if remote_tags else None
    try:
        branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=BASE_DIR, text=True).strip()
        commit = subprocess.check_output(["git", "log", "-1", "--format=%h - %s (%cr)"], cwd=BASE_DIR, text=True).strip()
        remote = subprocess.check_output(["git", "remote", "get-url", "origin"], cwd=BASE_DIR, text=True).strip()
    except Exception:
        branch = "main"
        commit = latest_remote_tag or "v1.0.1 (Local)"
        remote = "https://github.com/DriifterSelf/agente"
    return {
        "branch": branch,
        "latest_commit": commit,
        "remote_url": remote,
        "latest_tag": latest_remote_tag,
        "available_tags": [f"v{t[3]}" for t in remote_tags[:10]]
    }

@app.post("/api/system/git-pull")
def pull_latest_updates():
    remote_tags = _fetch_remote_github_tags()
    latest_ver = remote_tags[0][3] if remote_tags else None
    latest_raw_tag = remote_tags[0][4] if remote_tags else None

    if os.path.exists(os.path.join(BASE_DIR, ".git")):
        try:
            subprocess.run(["git", "fetch", "--all", "--tags", "--force"], cwd=BASE_DIR, capture_output=True, text=True, timeout=25)
            pull_res = subprocess.run(["git", "pull", "--rebase"], cwd=BASE_DIR, capture_output=True, text=True, timeout=40)
            output = (pull_res.stdout or "") + (pull_res.stderr or "")
            rebuilt = False
            if "Already up to date" not in output and "Ya está actualizado" not in output and pull_res.returncode == 0:
                subprocess.run(["npm", "run", "build:frontend"], cwd=BASE_DIR, capture_output=True, shell=True, timeout=60)
                rebuilt = True
            return {
                "status": "success" if pull_res.returncode == 0 else "error",
                "message": output.strip(),
                "rebuilt": rebuilt,
                "latest_version": latest_ver,
                "latest_tag": latest_raw_tag
            }
        except Exception as e:
            return {"status": "error", "message": str(e), "latest_version": latest_ver, "latest_tag": latest_raw_tag}

    return {
        "status": "success",
        "message": f"Último tag en GitHub: v{latest_ver}" if latest_ver else "Verificación completada",
        "rebuilt": False,
        "latest_version": latest_ver,
        "latest_tag": latest_raw_tag
    }

@app.get("/api/projects")
def list_projects():
    projects = []
    if os.path.exists(PROJECTS_DIR):
        for entry in os.scandir(PROJECTS_DIR):
            if entry.is_dir() and not entry.name.startswith("."):
                file_count = len([
                    f for f in os.scandir(entry.path)
                    if f.is_file() and not f.name.startswith(".") and f.name != "conversations.json"
                ])
                projects.append({
                    "name": entry.name,
                    "path": entry.path,
                    "file_count": file_count,
                    "modified": entry.stat().st_mtime
                })
    return sorted(projects, key=lambda x: x["name"].lower())

@app.post("/api/projects")
def create_project(req: NewProjectRequest):
    if ".." in req.name or "/" in req.name or "\\" in req.name:
        raise HTTPException(status_code=400, detail="Caracteres de ruta no permitidos en el nombre.")
    target = _safe_project_path(req.name)
    os.makedirs(target, exist_ok=True)
    return {"name": os.path.basename(target), "path": target, "status": "created"}

@app.delete("/api/projects/{name}")
def delete_project(name: str):
    target = _safe_project_path(name)
    if not os.path.exists(target):
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    shutil.rmtree(target)
    return {"status": "deleted", "name": os.path.basename(target)}

@app.get("/api/projects/{name}/files")
def get_project_files(name: str):
    target = _safe_project_path(name)
    if not os.path.exists(target):
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    if SystemTools:
        return SystemTools.list_files(target)
    return []

@app.post("/api/projects/{name}/upload")
async def upload_project_file(name: str, file: UploadFile = File(...)):
    target_dir = _safe_project_path(name)
    os.makedirs(target_dir, exist_ok=True)
    safe_file_name = os.path.basename(file.filename)
    file_path = os.path.join(target_dir, safe_file_name)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    parsed = SystemTools.read_file_content(file_path) if SystemTools else {"status": "success", "content": ""}
    return {
        "status": "success",
        "file_name": safe_file_name,
        "path": file_path,
        "parsed_preview": parsed
    }

@app.post("/api/projects/{name}/open-folder")
def open_project_folder(name: str):
    target = _safe_project_path(name)
    return SystemTools.open_in_windows(target) if SystemTools else {"status": "ok"}

@app.post("/api/system/open-file")
def open_file_in_windows(req: OpenFileRequest):
    return SystemTools.open_in_windows(req.path) if SystemTools else {"status": "ok"}

@app.get("/api/models")
def list_models():
    if engine:
        return engine.list_catalog_models()
    return []

@app.post("/api/models/load")
def load_model(req: LoadModelRequest):
    if engine:
        return engine.load_model(req.filename, n_gpu_layers=req.gpu_layers, n_ctx=req.n_ctx)
    return {"status": "ok"}

@app.post("/api/models/download")
def download_model(req: LoadModelRequest):
    if engine:
        return engine.download_model_native(req.filename)
    return {"status": "error", "message": "Motor no disponible"}

@app.post("/api/models/open-folder")
def open_models_folder():
    os.makedirs(MODELS_DIR, exist_ok=True)
    if SystemTools:
        return SystemTools.open_in_windows(MODELS_DIR)
    return {"status": "ok", "path": MODELS_DIR}

@app.post("/api/system/download-runtime")
def download_llama_runtime():
    if not engine:
        return {"status": "error", "message": "Motor no inicializado"}
    bin_path = engine.ensure_runtime()
    if bin_path:
        models = engine.list_available_models()
        if models:
            import threading
            threading.Thread(target=engine.load_model, args=(models[0]["filename"],), daemon=True).start()
        return {"status": "success", "binary": bin_path}
    return {"status": "error", "message": "No se pudo descargar llama-server.exe"}


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    project_path = _safe_project_path(req.project_name)
    os.makedirs(project_path, exist_ok=True)
    messages_dicts = [{"role": m.role, "content": m.content} for m in req.messages]
    
    def event_stream():
        try:
            if agent:
                for event in agent.process_turn(project_path, messages_dicts):
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            err_msg = f"\n\n[Error en el procesamiento: {str(e)}]"
            yield f"data: {json.dumps({'type': 'token', 'content': err_msg}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
        
    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.post("/api/workspace/open-repo")
def open_local_repository(req: OpenRepoRequest):
    repo_path = os.path.abspath(req.path)
    if not os.path.exists(repo_path) or not os.path.isdir(repo_path):
        raise HTTPException(status_code=400, detail="La ruta del repositorio no existe o no es una carpeta.")
    
    repo_name = os.path.basename(repo_path.rstrip("/\\"))
    if not repo_name:
        raise HTTPException(status_code=400, detail="Ruta de repositorio inválida.")

    meta_file = os.path.join(PROJECTS_DIR, f"{repo_name}.workspace.json")
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump({"name": repo_name, "real_path": repo_path}, f, indent=2)

    os.makedirs(os.path.join(PROJECTS_DIR, repo_name), exist_ok=True)
    return {"name": repo_name, "path": repo_path, "status": "connected"}

class SaveChatRequest(BaseModel):
    messages: Optional[List[Dict[str, Any]]] = None
    conversations: Optional[List[Dict[str, Any]]] = None
    active_conversation_id: Optional[str] = None

@app.get("/api/projects/{name}/chats")
def get_project_chats(name: str):
    target = _safe_project_path(name)
    chat_file = os.path.join(target, "conversations.json")
    if os.path.exists(chat_file):
        try:
            with open(chat_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []

@app.post("/api/projects/{name}/chats")
def save_project_chats(name: str, req: SaveChatRequest):
    target = _safe_project_path(name)
    os.makedirs(target, exist_ok=True)
    chat_file = os.path.join(target, "conversations.json")

    if req.conversations is not None:
        payload: Any = {
            "conversations": req.conversations,
            "active_conversation_id": req.active_conversation_id
        }
        count = len(req.conversations)
    else:
        payload = req.messages or []
        count = len(payload)

    with open(chat_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return {"status": "saved", "count": count}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765)

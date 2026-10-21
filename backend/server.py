import os
import sys

# Ensure root directory is in sys.path regardless of how server.py is launched
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import json
import subprocess
import psutil
import shutil
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from backend.engine import InferenceEngine
from backend.agent import AutonomousAgent
from backend.tools.system_tools import SystemTools

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECTS_DIR = os.path.join(BASE_DIR, "projects")
MODELS_DIR = os.path.join(BASE_DIR, "models")
os.makedirs(PROJECTS_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)

# Create a default project if none exists
default_proj = os.path.join(PROJECTS_DIR, "Mi Primer Proyecto")
os.makedirs(default_proj, exist_ok=True)

app = FastAPI(title="Agente Desktop AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = InferenceEngine(models_dir=MODELS_DIR)
agent = AutonomousAgent(engine)

@app.on_event("startup")
def on_startup():
    engine.auto_start()

@app.on_event("shutdown")
def on_shutdown():
    engine.stop()

def _safe_project_path(name: str) -> str:
    if not name or not isinstance(name, str):
        raise HTTPException(status_code=400, detail="Nombre de proyecto inválido.")
    clean = os.path.basename(name.strip())
    if not clean or clean in (".", ".."):
        raise HTTPException(status_code=400, detail="Nombre de proyecto inválido.")
    target = os.path.abspath(os.path.join(PROJECTS_DIR, clean))
    if not target.startswith(os.path.abspath(PROJECTS_DIR)):
        raise HTTPException(status_code=400, detail="Ruta de proyecto no permitida.")
    return target

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
    return engine.context_presets()

@app.post("/api/settings/context")
def set_context_settings(req: ContextSettingsRequest):
    mode = req.kv_mode
    if not mode:
        if req.use_ram_for_kv is not None:
            mode = "ram" if req.use_ram_for_kv else "gpu"
        else:
            mode = "auto"
    return engine.set_context_config(req.n_ctx, mode)

@app.get("/api/system/status")
def get_system_status():
    mem = psutil.virtual_memory()
    total_ram_gb = round(mem.total / (1024**3), 1)
    avail_ram_gb = round(mem.available / (1024**3), 1)
    ram_percent = mem.percent
    
    cpu_percent = psutil.cpu_percent(interval=None)
    eng_status = engine.get_status()
    
    ctx_mem = eng_status.get("context_mem_gb")
    if ctx_mem is None:
        ctx_mem = round((engine.n_ctx / 32768) * 6.0, 1)

    gpu_vram_str = f"{eng_status.get('gpu_vram_gb', 0)} GB" if eng_status.get("gpu_vram_gb") else "VRAM"

    return {
        "cpu_usage": cpu_percent,
        "ram_total_gb": total_ram_gb,
        "ram_available_gb": avail_ram_gb,
        "ram_percent": ram_percent,
        **eng_status,
        "gpu_vram": gpu_vram_str,
        "use_ram_for_kv": eng_status.get("kv_location") == "ram",
        "context_ram_gb": ctx_mem,
    }

# --- GIT & OTA UPDATE ENDPOINTS ---
@app.get("/api/system/git-info")
def get_git_info():
    try:
        branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=BASE_DIR, text=True).strip()
        commit = subprocess.check_output(["git", "log", "-1", "--format=%h - %s (%cr)"], cwd=BASE_DIR, text=True).strip()
        remote = subprocess.check_output(["git", "remote", "get-url", "origin"], cwd=BASE_DIR, text=True).strip()
    except Exception:
        branch = "main"
        commit = "v1.0.0 (Local)"
        remote = "No configurado"
    return {
        "branch": branch,
        "latest_commit": commit,
        "remote_url": remote
    }

@app.post("/api/system/git-pull")
def pull_latest_updates():
    try:
        # 1. git pull
        pull_res = subprocess.run(["git", "pull", "--rebase"], cwd=BASE_DIR, capture_output=True, text=True, timeout=40)
        output = pull_res.stdout + pull_res.stderr
        
        # 2. Rebuild frontend if changes occurred
        rebuilt = False
        if "Already up to date" not in output and "Ya está actualizado" not in output:
            subprocess.run(["npm", "run", "build:frontend"], cwd=BASE_DIR, capture_output=True, shell=True, timeout=60)
            rebuilt = True
            
        return {
            "status": "success" if pull_res.returncode == 0 else "error",
            "message": output.strip(),
            "rebuilt": rebuilt
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/projects")
def list_projects():
    projects = []
    if os.path.exists(PROJECTS_DIR):
        for entry in os.scandir(PROJECTS_DIR):
            if entry.is_dir() and not entry.name.startswith("."):
                file_count = len([f for f in os.scandir(entry.path) if f.is_file()])
                projects.append({
                    "name": entry.name,
                    "path": entry.path,
                    "file_count": file_count,
                    "modified": entry.stat().st_mtime
                })
    return sorted(projects, key=lambda x: x["name"].lower())

@app.post("/api/projects")
def create_project(req: NewProjectRequest):
    safe_name = req.name.strip().replace("/", "_").replace("\\", "_")
    target = _safe_project_path(safe_name)
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
    return SystemTools.list_files(target)

@app.post("/api/projects/{name}/upload")
async def upload_project_file(name: str, file: UploadFile = File(...)):
    target_dir = _safe_project_path(name)
    os.makedirs(target_dir, exist_ok=True)
    safe_file_name = os.path.basename(file.filename)
    file_path = os.path.join(target_dir, safe_file_name)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Analyze uploaded file immediately with multimodal reader
    parsed = SystemTools.read_file_content(file_path)
    return {
        "status": "success",
        "file_name": safe_file_name,
        "path": file_path,
        "parsed_preview": parsed
    }

@app.post("/api/projects/{name}/open-folder")
def open_project_folder(name: str):
    target = _safe_project_path(name)
    return SystemTools.open_in_windows(target)

@app.post("/api/system/open-file")
def open_file_in_windows(req: OpenFileRequest):
    return SystemTools.open_in_windows(req.path)

@app.get("/api/models")
def list_models():
    return engine.list_available_models()

@app.post("/api/models/load")
def load_model(req: LoadModelRequest):
    return engine.load_model(req.filename, n_gpu_layers=req.gpu_layers, n_ctx=req.n_ctx)

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    project_path = _safe_project_path(req.project_name)
    os.makedirs(project_path, exist_ok=True)
    messages_dicts = [{"role": m.role, "content": m.content} for m in req.messages]
    
    def event_stream():
        try:
            for event in agent.process_turn(project_path, messages_dicts):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            err_msg = f"\n\n[Error en el procesamiento: {str(e)}]"
            yield f"data: {json.dumps({'type': 'token', 'content': err_msg}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
        
    return StreamingResponse(event_stream(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765)

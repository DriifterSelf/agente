import os
import sys

# Ensure root directory is in sys.path regardless of how server.py is launched
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import json
import subprocess
import psutil
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request
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
    use_ram_for_kv: bool = True

@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "Agente AI"}

@app.post("/api/settings/context")
def set_context_settings(req: ContextSettingsRequest):
    return engine.set_context_config(req.n_ctx, req.use_ram_for_kv)

def detect_active_gpu():
    try:
        res = subprocess.check_output(
            ['powershell', '-NoProfile', '-Command', 
             'Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name'], 
            text=True, timeout=3
        )
        names = [n.strip() for n in res.strip().splitlines() if n.strip() and 'Virtual' not in n]
        for name in names:
            if 'Radeon' in name or 'AMD' in name:
                return {"name": name, "backend": "ROCm / HIP / Vulkan", "vram": "16 GB"}
            if 'NVIDIA' in name or 'GeForce' in name or 'RTX' in name:
                return {"name": name, "backend": "CUDA (NVIDIA)", "vram": "8 GB"}
        if names:
            return {"name": names[0], "backend": "Vulkan / DirectML", "vram": "Automático"}
    except Exception:
        pass
    return {"name": "GPU Acelerada", "backend": "ROCm / CUDA", "vram": "VRAM"}

@app.get("/api/system/status")
def get_system_status():
    mem = psutil.virtual_memory()
    total_ram_gb = round(mem.total / (1024**3), 1)
    avail_ram_gb = round(mem.available / (1024**3), 1)
    ram_percent = mem.percent
    
    cpu_percent = psutil.cpu_percent(interval=None)
    gpu_info = detect_active_gpu()
    
    ram_ctx_gb = round((engine.n_ctx / 32768) * 6.0, 1)

    return {
        "cpu_usage": cpu_percent,
        "ram_total_gb": total_ram_gb,
        "ram_available_gb": avail_ram_gb,
        "ram_percent": ram_percent,
        "active_model": engine.active_model_name,
        "backend_type": engine.backend_type,
        "gpu_name": gpu_info["name"],
        "gpu_backend": gpu_info["backend"],
        "gpu_vram": gpu_info["vram"],
        "n_ctx": engine.n_ctx,
        "n_ctx_k": engine.n_ctx // 1024,
        "use_ram_for_kv": engine.use_ram_for_kv,
        "context_ram_gb": ram_ctx_gb
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
    if not safe_name:
        raise HTTPException(status_code=400, detail="Nombre inválido.")
    target = os.path.join(PROJECTS_DIR, safe_name)
    os.makedirs(target, exist_ok=True)
    return {"name": safe_name, "path": target, "status": "created"}

@app.delete("/api/projects/{name}")
def delete_project(name: str):
    target = os.path.join(PROJECTS_DIR, name)
    if not os.path.exists(target):
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    shutil.rmtree(target)
    return {"status": "deleted", "name": name}

@app.get("/api/projects/{name}/files")
def get_project_files(name: str):
    target = os.path.join(PROJECTS_DIR, name)
    if not os.path.exists(target):
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    return SystemTools.list_files(target)

from fastapi import File, UploadFile
import shutil

@app.post("/api/projects/{name}/upload")
async def upload_project_file(name: str, file: UploadFile = File(...)):
    target_dir = os.path.join(PROJECTS_DIR, name)
    os.makedirs(target_dir, exist_ok=True)
    file_path = os.path.join(target_dir, file.filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Analyze uploaded file immediately with multimodal reader
    parsed = SystemTools.read_file_content(file_path)
    return {
        "status": "success",
        "file_name": file.filename,
        "path": file_path,
        "parsed_preview": parsed
    }

@app.post("/api/projects/{name}/open-folder")
def open_project_folder(name: str):
    target = os.path.join(PROJECTS_DIR, name)
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
    project_path = os.path.join(PROJECTS_DIR, req.project_name)
    messages_dicts = [{"role": m.role, "content": m.content} for m in req.messages]
    
    def event_stream():
        for event in agent.process_turn(project_path, messages_dicts):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
        
    return StreamingResponse(event_stream(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765)

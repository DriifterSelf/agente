import os
import re
import json
import glob
import concurrent.futures
import requests

BASE_URL = "http://127.0.0.1:8765"
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

passed = 0
warnings = 0
failed = 0

def log_ok(msg):
    global passed
    passed += 1
    print(f"  [OK]   {msg}")

def log_warn(msg):
    global warnings
    warnings += 1
    print(f"  [WARN] {msg}")

def log_fail(msg):
    global failed
    failed += 1
    print(f"  [FAIL] {msg}")


# =====================================================================
# 1. AUDITORÍA ESTÁTICA: RUTAS API (FRONTEND vs BACKEND) Y BOTONES
# =====================================================================
def audit_static_code():
    print("\n" + "="*65)
    print("1. AUDITORÍA DE CÓDIGO: RUTAS FANTASMA, IPC Y BOTONES EN UI")
    print("="*65)

    server_path = os.path.join(ROOT_DIR, "backend", "server.py")
    server_code = open(server_path, "r", encoding="utf-8", errors="ignore").read() if os.path.exists(server_path) else ""

    # Extraer rutas declaradas en FastAPI/Flask en server.py
    backend_routes = set(re.findall(r'@\w+\.(?:get|post|put|delete|patch)\(["\']([^"\']+)["\']', server_code))
    print(f"  -> Rutas detectadas en backend/server.py: {len(backend_routes)}")

    # Escanear archivos de src/
    src_files = glob.glob(os.path.join(ROOT_DIR, "src", "**", "*.*"), recursive=True)
    frontend_calls = []
    buttons_without_action = []

    for fpath in src_files:
        if not fpath.endswith((".js", ".jsx", ".ts", ".tsx")):
            continue
        rel = os.path.relpath(fpath, ROOT_DIR)
        content = open(fpath, "r", encoding="utf-8", errors="ignore").read()

        # Buscar llamadas a /api/...
        for m in re.finditer(r'["\'`](?:https?://[^"\'`]+)?(/api/[a-zA-Z0-9_/\-\$\{\}]+)["\'`]', content):
            frontend_calls.append((rel, m.group(1)))

        # Buscar <button> que no tengan onClick ni type="submit"
        for m in re.finditer(r'<button\b([^>]*)>', content, re.DOTALL):
            attrs = m.group(1)
            if "onClick" not in attrs and 'type="submit"' not in attrs and "type='submit'" not in attrs:
                line_num = content[:m.start()].count("\n") + 1
                buttons_without_action.append(f"{rel}:{line_num}")

    # Comparar rutas Frontend vs Backend
    for rel, api_call in frontend_calls:
        # Normalizar interpolaciones JS ${...} a comodín
        norm_call = re.sub(r'\$\{[^}]+\}', '{param}', api_call).rstrip('/')
        matched = False
        for b_route in backend_routes:
            norm_b = re.sub(r'\{[^}]+\}', '{param}', b_route).rstrip('/')
            if norm_call == norm_b or norm_call.startswith(norm_b + "?"):
                matched = True
                break
        if matched:
            log_ok(f"Ruta conectada: {api_call} ({rel})")
        else:
            log_fail(f"Ruta en UI NO existe en server.py: {api_call} (llamada en {rel})")

    if buttons_without_action:
        for b in buttons_without_action:
            log_warn(f"Botón <button> sin onClick detectado en: {b}")
    else:
        log_ok("Todos los elementos <button> en src/ tienen un evento asignado.")


# =====================================================================
# 2. AUDITORÍA DE EMPAQUETADO Y DISTRIBUCIÓN (.EXE)
# =====================================================================
def audit_packaging():
    print("\n" + "="*65)
    print("2. AUDITORÍA DE DISTRIBUCIÓN (ELECTRON-BUILDER & PORTABILIDAD)")
    print("="*65)

    pkg_path = os.path.join(ROOT_DIR, "package.json")
    pkg = json.load(open(pkg_path, "r", encoding="utf-8"))
    build = pkg.get("build", {})
    extra = [ (x["from"] if isinstance(x, dict) else x) for x in build.get("extraResources", []) ]
    files = build.get("files", [])

    if "runtime" not in extra:
        log_fail("CRÍTICO: 'runtime' NO está en extraResources de package.json (llama-server.exe no se incluirá en el .exe)")
    else:
        log_ok("'runtime' incluido en extraResources.")

    if "backend/**/*" in files and "backend" not in extra:
        log_fail("CRÍTICO: 'backend/**/*' está en 'files' (quedará atrapado dentro de app.asar y Python no podrá ejecutarlo).")
    else:
        log_ok("'backend' fuera de app.asar.")

    bm_path = os.path.join(ROOT_DIR, "electron", "backend_manager.js")
    if os.path.exists(bm_path):
        bm_code = open(bm_path, "r", encoding="utf-8").read()
        if "venv" in bm_code and "resourcesPath" not in bm_code:
            log_fail("CRÍTICO: backend_manager.js usa 'venv' local y no distingue app.isPackaged / process.resourcesPath.")


# =====================================================================
# 3. EDGE CASES RIDÍCULOS CONTRA EL BACKEND EN VIVO
# =====================================================================
def test_ridiculous_edge_cases():
    print("\n" + "="*65)
    print("3. TORTURA DE API Y EDGE CASES RIDÍCULOS (CHAOS TESTING)")
    print("="*65)

    # Verificar que el servidor esté encendido
    try:
        r = requests.get(f"{BASE_URL}/api/health", timeout=3)
        log_ok(f"Servidor activo en {BASE_URL} (Status {r.status_code})")
    except Exception:
        log_warn("El servidor no estaba corriendo en 8765. Iniciando instancia temporal de FastAPI TestClient...")
        from fastapi.testclient import TestClient
        from backend.server import app
        run_edge_cases_with_client(TestClient(app))
        return

    run_edge_cases_with_client(requests, base=BASE_URL)


def run_edge_cases_with_client(client, base=""):
    def req(method, path, **kwargs):
        url = f"{base}{path}"
        return getattr(client, method)(url, **kwargs)

    # --- EDGE CASE A: Nombres de proyectos maliciosos o reservados de Windows ---
    ridiculous_project_names = [
        ("", "Nombre vacío"),
        ("   ", "Solo espacios"),
        ("../../Windows/System32", "Path Traversal ../.."),
        ("CON", "Nombre reservado de Windows (CON)"),
        ("NUL", "Nombre reservado de Windows (NUL)"),
        ("PRN", "Nombre reservado de Windows (PRN)"),
        ("proyecto<>:\"/\\|?*", "Caracteres ilegales en NTFS"),
        ("🔥💀🚀_Proyecto_Con_Emojis_Ñáéíóú_测试", "Unicode extremo + Emojis + CJK"),
        ("A" * 400, "Nombre de 400 caracteres (Supera MAX_PATH de Windows)"),
        ("'; DROP TABLE projects; --", "Inyección SQL/Comandos"),
    ]

    for bad_name, desc in ridiculous_project_names:
        try:
            r = req("post", "/api/projects", json={"name": bad_name})
            if r.status_code == 500:
                log_fail(f"CRASH 500 al crear proyecto [{desc}]: {r.text[:120]}")
            elif r.status_code in (200, 201, 400, 422):
                log_ok(f"Manejo seguro ({r.status_code}) para nombre de proyecto: {desc}")
            else:
                log_warn(f"Status inesperado ({r.status_code}) para [{desc}]")
        except Exception as e:
            log_fail(f"Excepción en cliente con proyecto [{desc}]: {e}")

    # --- EDGE CASE B: Subida de archivos corruptos / falsos / 0 bytes ---
    req("post", "/api/projects", json={"name": "_chaos_test_proj"})
    corrupt_files = [
        ("vacio.txt", b"", "text/plain", "Archivo de 0 bytes"),
        ("falso_word.docx", b"ESTO NO ES UN ZIP NI UN DOCX REAL \x00\xff\xfe", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "Archivo .docx corrupto (no es ZIP)"),
        ("falso_excel.xlsx", b"\x00\x01\x02\x03GARBAGE", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "Archivo .xlsx corrupto"),
        ("imagen_rota.png", b"NOT_A_PNG_HEADER", "image/png", "Imagen PNG con cabecera falsa"),
        ("../../escape.txt", b"hola", "text/plain", "Filename con Path Traversal"),
    ]

    for fname, content, mime, desc in corrupt_files:
        try:
            r = req("post", "/api/projects/_chaos_test_proj/upload", files={"file": (fname, content, mime)})
            if r.status_code == 500:
                log_fail(f"CRASH 500 al subir [{desc}]: {r.text[:120]}")
            else:
                log_ok(f"Subida de [{desc}] no tumbó el servidor (Status {r.status_code})")
        except Exception as e:
            log_fail(f"Excepción subiendo [{desc}]: {e}")

    # --- EDGE CASE C: Configuración de Contexto y Modelo con valores absurdos ---
    bad_contexts = [
        {"n_ctx": -9999, "kv_mode": "auto"},
        {"n_ctx": 0, "kv_mode": "gpu"},
        {"n_ctx": 999999999, "kv_mode": "HackMode"},
        {"n_ctx": "no_soy_un_numero", "kv_mode": None},
    ]
    for payload in bad_contexts:
        for endpoint in ["/api/context", "/api/system/context", "/api/models/context"]:
            try:
                r = req("post", endpoint, json=payload)
                if r.status_code == 404:
                    continue
                if r.status_code == 500:
                    log_fail(f"CRASH 500 en {endpoint} con payload {payload}: {r.text[:100]}")
                else:
                    log_ok(f"Contexto absurdo {payload} manejado en {endpoint} ({r.status_code})")
            except Exception:
                pass

    # --- EDGE CASE D: Doble/Triple clic rápido (Condición de carrera / Concurrencia) ---
    def rapid_call(_):
        return req("get", "/api/system/status").status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        statuses = list(ex.map(rapid_call, range(15)))
    if all(s == 200 for s in statuses):
        log_ok("15 peticiones simultáneas (spam de clics) a /api/system/status respondieron 200 sin bloqueo.")
    else:
        log_fail(f"Fallo bajo concurrencia en /api/system/status: {statuses}")


if __name__ == "__main__":
    print("INICIANDO SUITE DE CAOS Y AUDITORÍA DE AGENTE STUDIO...")
    audit_static_code()
    audit_packaging()
    test_ridiculous_edge_cases()
    print("\n" + "="*65)
    print(f"RESUMEN: {passed} OK | {warnings} ADVERTENCIAS | {failed} FALLOS CRÍTICOS")
    print("="*65)
    
# --- LIMPIEZA AUTOMÁTICA DE PROYECTOS DE CAOS ---
    import shutil
    projects_dir = os.path.join(ROOT_DIR, "projects")
    for p in os.listdir(projects_dir):
        if p in ("CON", "PRN", "_chaos_test_proj") or "DROP" in p or "🔥" in p or "System32" in p:
            shutil.rmtree(os.path.join(projects_dir, p), ignore_errors=True)
    log_ok("Limpieza automática de proyectos de prueba completada.")
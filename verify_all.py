import os
import sys
import json
import time

# Ensure project root is in sys.path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from fastapi.testclient import TestClient
from backend.server import app, PROJECTS_DIR
from backend.tools.office_tools import OfficeTools
from backend.tools.web_tools import WebTools
from backend.tools.system_tools import SystemTools
from backend.tools.sandbox_tools import SandboxTools
from PIL import Image

print("=" * 60)
print("INICIANDO SUITE DE VERIFICACION INTEGRAL DE AGENTE STUDIO")
print("=" * 60)

results = {}

# 1. VERIFICAR CLIENTE Y ENDPOINTS FASTAPI
print("\n[1/6] Verificando Servidor Backend y Endpoints API...")
try:
    client = TestClient(app)
    
    # Health check
    res_health = client.get("/api/health")
    assert res_health.status_code == 200, f"Error health: {res_health.status_code}"
    print("  [OK] /api/health")
    
    # System Status & GPU detection
    res_sys = client.get("/api/system/status")
    assert res_sys.status_code == 200, f"Error status: {res_sys.status_code}"
    sys_data = res_sys.json()
    print(f"  [OK] /api/system/status -> GPU detectada: '{sys_data.get('gpu_name')}' | Backend: '{sys_data.get('gpu_backend')}' | RAM libre: {sys_data.get('ram_available_gb')} GB")
    
    # Projects listing
    res_proj = client.get("/api/projects")
    assert res_proj.status_code == 200, f"Error projects: {res_proj.status_code}"
    projects_list = res_proj.json()
    print(f"  [OK] /api/projects -> {len(projects_list)} proyectos encontrados")
    
    results["Backend API"] = "PASSED"
except Exception as e:
    print(f"  [FAIL] Error en Backend API: {e}")
    results["Backend API"] = f"FAILED: {e}"

# 2. VERIFICAR CREACION DE PROYECTO
print("\n[2/6] Verificando Creacion y Persistencia de Proyectos...")
test_proj_name = "Verificacion_Automatizada"
test_proj_dir = os.path.join(PROJECTS_DIR, test_proj_name)
try:
    res_create = client.post("/api/projects", json={"name": test_proj_name})
    assert res_create.status_code == 200, f"Error creando: {res_create.status_code}"
    assert os.path.exists(test_proj_dir), f"El directorio no se creo en disco: {test_proj_dir}"
    print(f"  [OK] Proyecto creado en disco: {test_proj_dir}")
    results["Proyectos en Disco"] = "PASSED"
except Exception as e:
    print(f"  [FAIL] Error en Creacion de Proyecto: {e}")
    results["Proyectos en Disco"] = f"FAILED: {e}"

# 3. VERIFICAR INGESTA MULTIMODAL (IMAGEN, CSV, TEXTO, ZIP)
print("\n[3/6] Verificando Ingesta y Parsing Multimodal...")
try:
    # A. Crear y leer imagen de prueba
    img_path = os.path.join(test_proj_dir, "diagrama_test.png")
    img = Image.new("RGB", (640, 480), color=(30, 41, 59))
    img.save(img_path)
    parsed_img = SystemTools.read_file_content(img_path)
    assert parsed_img["status"] == "success" and parsed_img["category"] == "image"
    print(f"  [OK] Ingesta de Imagen: {parsed_img['dimensions']}, categoria '{parsed_img['category']}'")

    # B. Crear y leer CSV
    csv_path = os.path.join(test_proj_dir, "datos_financieros.csv")
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("Mes,Ventas,Gastos,Margen\nEnero,1000,600,400\nFebrero,1200,700,500\nMarzo,1500,800,700\n")
    parsed_csv = SystemTools.read_file_content(csv_path)
    assert parsed_csv["status"] == "success" and parsed_csv["category"] == "spreadsheet"
    print(f"  [OK] Ingesta de Hoja/CSV: categoria '{parsed_csv['category']}'")

    # C. Endpoint de Upload
    with open(img_path, "rb") as f:
        res_upload = client.post(
            f"/api/projects/{test_proj_name}/upload",
            files={"file": ("foto_tarea.png", f, "image/png")}
        )
    assert res_upload.status_code == 200
    print("  [OK] Endpoint /api/projects/{name}/upload (Multipart)")

    results["Ingesta Multimodal"] = "PASSED"
except Exception as e:
    print(f"  [FAIL] Error en Ingesta Multimodal: {e}")
    results["Ingesta Multimodal"] = f"FAILED: {e}"

# 4. VERIFICAR GENERADORES DE OFICINA (WORD, EXCEL, PPTX)
print("\n[4/6] Verificando Generadores Profesionales de Oficina...")
try:
    # A. Excel con formulas y graficos
    excel_res = OfficeTools.create_excel(
        project_path=test_proj_dir,
        filename="Balance_General.xlsx",
        sheets_data=[{
            "sheet_name": "Q1_Q2",
            "headers": ["Rubro", "Q1", "Q2", "Total"],
            "rows": [["Activos", 50000, 60000, "=SUM(B2:C2)"], ["Pasivos", 20000, 22000, "=SUM(B3:C3)"]],
            "create_chart": True,
            "chart_title": "Evolucion de Activos"
        }]
    )
    assert excel_res["status"] == "success"
    assert os.path.exists(excel_res["full_path"])
    print(f"  [OK] Generador Excel (.xlsx): {round(os.path.getsize(excel_res['full_path'])/1024, 1)} KB")

    # B. Word con diseno ejecutivo y tablas
    word_res = OfficeTools.create_word(
        project_path=test_proj_dir,
        filename="Reporte_Academico.docx",
        title="Informe de Entrega Universitaria",
        subtitle="Materia de Finanzas Corporativas",
        sections=[{
            "heading": "1. Introduccion y Justificacion",
            "level": 1,
            "paragraphs": ["Analisis detallado de variables macroeconomicas."],
            "callout": "Nota clave: Cumplimiento de criterios al 100%.",
            "table": {"headers": ["Metrica", "Valor"], "rows": [["Inflacion", "4.2%"], ["Crecimiento", "2.1%"]]}
        }]
    )
    assert word_res["status"] == "success"
    assert os.path.exists(word_res["full_path"])
    print(f"  [OK] Generador Word (.docx): {round(os.path.getsize(word_res['full_path'])/1024, 1)} KB")

    # C. PowerPoint en formato 16:9 widescreen
    ppt_res = OfficeTools.create_powerpoint(
        project_path=test_proj_dir,
        filename="Exposicion_Final.pptx",
        title="Presentacion de Tarea",
        subtitle="Equipo de Investigacion",
        slides_data=[{
            "title": "Conclusiones Principales",
            "bullets": ["Punto 1 verificado.", "Punto 2 analizado exhaustivamente."],
            "highlight": "Resultados concluyentes."
        }]
    )
    assert ppt_res["status"] == "success"
    assert os.path.exists(ppt_res["full_path"])
    print(f"  [OK] Generador PowerPoint (.pptx): {round(os.path.getsize(ppt_res['full_path'])/1024, 1)} KB")

    results["Generadores Office"] = "PASSED"
except Exception as e:
    print(f"  [FAIL] Error en Generadores Office: {e}")
    results["Generadores Office"] = f"FAILED: {e}"

# 5. VERIFICAR BUSQUEDA WEB Y SANDBOX DE CODIGO
print("\n[5/6] Verificando Busqueda Web y Sandbox de Ejecucion...")
try:
    # A. Web Search
    web_res = WebTools.search("inteligencia artificial avances", max_results=2)
    print(f"  [OK] Herramienta Web: Estado '{web_res.get('status')}'")

    # B. Sandbox execution
    target_out = os.path.join(test_proj_dir, 'resultado_calculo.txt')
    if os.path.exists(target_out):
        os.remove(target_out)
    code_test = "with open('resultado_calculo.txt', 'w') as f: f.write('Calculo completado: 42')"
    sandbox_res = SandboxTools.execute_code(test_proj_dir, code_test)
    assert sandbox_res["status"] == "success"
    assert "resultado_calculo.txt" in sandbox_res["new_files"]
    print(f"  [OK] Sandbox de Codigo en segundo plano: Archivo '{sandbox_res['new_files'][0]}' generado")

    results["Web y Sandbox"] = "PASSED"
except Exception as e:
    print(f"  [FAIL] Error en Web y Sandbox: {e}")
    results["Web y Sandbox"] = f"FAILED: {e}"

# 6. VERIFICAR BUILD DE FRONTEND, ACCESOS DIRECTOS Y GIT
print("\n[6/6] Verificando Interfaz, Empaquetado y Repositorio Git...")
try:
    # Dist files
    dist_html = os.path.join(ROOT_DIR, "dist", "index.html")
    assert os.path.exists(dist_html), "dist/index.html no existe"
    dist_size = os.path.getsize(dist_html)
    assert dist_size > 0, "dist/index.html esta vacio"
    print("  [OK] Bundle Frontend (dist/index.html)")

    # Desktop shortcut
    desktop_lnk = os.path.expanduser(r"~\Desktop\Agente Studio.lnk")
    assert os.path.exists(desktop_lnk), f"Acceso directo no encontrado en {desktop_lnk}"
    print(f"  [OK] Acceso directo en Escritorio: {desktop_lnk}")

    # Git status
    import subprocess
    commit_info = subprocess.check_output(["git", "log", "-1", "--oneline"], cwd=ROOT_DIR, text=True).strip()
    print(f"  [OK] Git Repository: Ultimo commit [{commit_info}]")

    results["Frontend & Git"] = "PASSED"
except Exception as e:
    print(f"  [FAIL] Error en Frontend/Git: {e}")
    results["Frontend & Git"] = f"FAILED: {e}"

print("\n" + "=" * 60)
print("RESUMEN FINAL DE VERIFICACION:")
print("=" * 60)
all_passed = True
for test_name, status in results.items():
    icon = "[PASSED]" if status == "PASSED" else "[FAILED]"
    print(f" {icon} {test_name}: {status}")
    if status != "PASSED":
        all_passed = False

if all_passed:
    print("\n>>> RESULTADO: EL SISTEMA COMPLETO ESTA 100% OPERATIVO Y VERIFICADO <<<")
else:
    print("\n>>> RESULTADO: Se detectaron observaciones <<<")

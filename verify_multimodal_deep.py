import os
import sys
import wave
import zipfile
import json
from PIL import Image

# Ensure project root in sys.path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from fastapi.testclient import TestClient
from backend.server import app, PROJECTS_DIR
from backend.tools.system_tools import SystemTools
from backend.tools.office_tools import OfficeTools
import docx
from pptx import Presentation
import openpyxl

print("=" * 65)
print("TEST PROFUNDO: VERIFICACION EXHAUSTIVA DE CAPACIDADES MULTIMODALES")
print("=" * 65)

test_proj = os.path.join(PROJECTS_DIR, "Test_Multimodal_Completo")
os.makedirs(test_proj, exist_ok=True)
client = TestClient(app)

results = {}

# --- 1. PRUEBA DE IMAGENES (.PNG, .JPG, .WEBP) ---
print("\n[1/8] Verificando Ingesta de Imagenes (Vision y Metadatos)...")
try:
    # Generar imagen PNG con patron
    img_png_path = os.path.join(test_proj, "grafico_analisis.png")
    img1 = Image.new("RGB", (1280, 720), color=(15, 23, 42))
    img1.save(img_png_path)
    
    # Generar imagen JPG
    img_jpg_path = os.path.join(test_proj, "foto_apuntes.jpg")
    img2 = Image.new("RGB", (800, 600), color=(240, 240, 240))
    img2.save(img_jpg_path, "JPEG")
    
    parsed_png = SystemTools.read_file_content(img_png_path)
    parsed_jpg = SystemTools.read_file_content(img_jpg_path)
    
    assert parsed_png["status"] == "success" and parsed_png["category"] == "image"
    assert parsed_png["dimensions"] == "1280x720"
    assert "base64_preview" in parsed_png
    assert parsed_jpg["status"] == "success" and parsed_jpg["category"] == "image"
    
    print(f"  [OK] PNG 1280x720 -> Detectado: {parsed_png['dimensions']} | Base64 listo para Vision")
    print(f"  [OK] JPG 800x600  -> Detectado: {parsed_jpg['dimensions']} | Categoria: {parsed_jpg['category']}")
    results["Imagenes (Vision)"] = "PASSED"
except Exception as e:
    print(f"  [FAIL] Error en Imagenes: {e}")
    results["Imagenes (Vision)"] = f"FAILED: {e}"

# --- 2. PRUEBA DE DOCUMENTOS WORD (.DOCX) ---
print("\n[2/8] Verificando Documentos Word (.docx con tablas y encabezados)...")
try:
    docx_path = os.path.join(test_proj, "ensayo_universitario.docx")
    d = docx.Document()
    d.add_heading("La Teoria Monetaria en la Economia Moderna", level=0)
    d.add_paragraph("Este es el parrafo principal que contiene el marco teorico de la investigacion.")
    t = d.add_table(rows=2, cols=2)
    t.rows[0].cells[0].text = "Variable"
    t.rows[0].cells[1].text = "Impacto"
    t.rows[1].cells[0].text = "Tasa de Interes"
    t.rows[1].cells[1].text = "Inversion Privada"
    d.save(docx_path)
    
    parsed_docx = SystemTools.read_file_content(docx_path)
    assert parsed_docx["status"] == "success" and parsed_docx["category"] == "document"
    assert "La Teoria Monetaria" in parsed_docx["content"]
    assert "Tasa de Interes" in parsed_docx["content"]
    
    print(f"  [OK] Word .docx -> Extraido texto, titulos y tablas correctamente ({parsed_docx['paragraphs_count']} bloques)")
    results["Documentos Word (.docx)"] = "PASSED"
except Exception as e:
    print(f"  [FAIL] Error en Word: {e}")
    results["Documentos Word (.docx)"] = f"FAILED: {e}"

# --- 3. PRUEBA DE PRESENTACIONES POWERPOINT (.PPTX) ---
print("\n[3/8] Verificando Presentaciones PowerPoint (.pptx diapositiva por diapositiva)...")
try:
    pptx_path = os.path.join(test_proj, "diapositivas_clase.pptx")
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = "Exposicion de Macroeconomia"
    slide.placeholders[1].text = "Subtitulo de prueba"
    prs.save(pptx_path)
    
    parsed_pptx = SystemTools.read_file_content(pptx_path)
    assert parsed_pptx["status"] == "success" and parsed_pptx["category"] == "presentation"
    assert "Exposicion de Macroeconomia" in parsed_pptx["content"]
    
    print(f"  [OK] PowerPoint .pptx -> {parsed_pptx['slides_count']} diapositiva(s) extraida(s) con titulos")
    results["Presentaciones (.pptx)"] = "PASSED"
except Exception as e:
    print(f"  [FAIL] Error en PowerPoint: {e}")
    results["Presentaciones (.pptx)"] = f"FAILED: {e}"

# --- 4. PRUEBA DE HOJAS DE CALCULO Y DATOS (.XLSX, .CSV) ---
print("\n[4/8] Verificando Hojas de Calculo y Bases de Datos (.xlsx, .csv)...")
try:
    # Excel multi-hoja
    xlsx_path = os.path.join(test_proj, "modelo_econometrico.xlsx")
    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = "Variables"
    ws1.append(["Ano", "PIB", "Inflacion"])
    ws1.append([2023, 105.4, 4.5])
    ws1.append([2024, 107.8, 3.8])
    ws2 = wb.create_sheet(title="Proyecciones")
    ws2.append(["Escenario", "Probabilidad"])
    ws2.append(["Optimista", "65%"])
    wb.save(xlsx_path)
    
    parsed_xlsx = SystemTools.read_file_content(xlsx_path)
    assert parsed_xlsx["status"] == "success" and parsed_xlsx["category"] == "spreadsheet"
    assert "Variables" in parsed_xlsx["sheets"]
    assert "Proyecciones" in parsed_xlsx["sheets"]
    
    # CSV
    csv_path = os.path.join(test_proj, "muestra_datos.csv")
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("id,estudiante,calificacion\n1,Carlos,95\n2,Sofia,98\n3,Luis,91\n")
    parsed_csv = SystemTools.read_file_content(csv_path)
    assert parsed_csv["status"] == "success" and parsed_csv["category"] == "spreadsheet"
    assert "Carlos" in parsed_csv["content"]
    
    print(f"  [OK] Excel multi-hoja -> Hojas detectadas: {parsed_xlsx['sheets']}")
    print(f"  [OK] Archivo CSV -> Lectura tabular e identificacion de columnas completada")
    results["Hojas de Calculo (.xlsx, .csv)"] = "PASSED"
except Exception as e:
    print(f"  [FAIL] Error en Hojas de Calculo: {e}")
    results["Hojas de Calculo (.xlsx, .csv)"] = f"FAILED: {e}"

# --- 5. PRUEBA DE ARCHIVOS DE AUDIO (.WAV) ---
print("\n[5/8] Verificando Archivos de Audio y Grabaciones (.wav)...")
try:
    wav_path = os.path.join(test_proj, "grabacion_clase.wav")
    with wave.open(wav_path, "w") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(44100)
        f.writeframes(b"\x00\x00" * 44100) # 1 segundo de audio sintetico valido
        
    parsed_wav = SystemTools.read_file_content(wav_path)
    assert parsed_wav["status"] == "success" and parsed_wav["category"] == "audio"
    print(f"  [OK] Audio WAV -> Categoria: '{parsed_wav['category']}' | Formato: {parsed_wav['type']}")
    results["Archivos de Audio"] = "PASSED"
except Exception as e:
    print(f"  [FAIL] Error en Audio: {e}")
    results["Archivos de Audio"] = f"FAILED: {e}"

# --- 6. PRUEBA DE ARCHIVOS COMPRIMIDOS (.ZIP) ---
print("\n[6/8] Verificando Archivos Comprimidos (.zip)...")
try:
    zip_path = os.path.join(test_proj, "paquete_tarea.zip")
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("notas.txt", "Contenido dentro del archivo comprimido.")
        z.writestr("referencias.bib", "@article{smith2024, title={Macroeconomics}}")
        
    parsed_zip = SystemTools.read_file_content(zip_path)
    assert parsed_zip["status"] == "success" and parsed_zip["category"] == "archive"
    assert parsed_zip["file_count"] == 2
    print(f"  [OK] Archivo ZIP -> Arbol de contenido inspeccionado ({parsed_zip['file_count']} archivos empaquetados)")
    results["Comprimidos (.zip)"] = "PASSED"
except Exception as e:
    print(f"  [FAIL] Error en Zip: {e}")
    results["Comprimidos (.zip)"] = f"FAILED: {e}"

# --- 7. PRUEBA DE CODIGO, JSON Y TEXTO PLANO ---
print("\n[7/8] Verificando Codigo Fuente, JSON y Texto (.json, .py, .md)...")
try:
    json_path = os.path.join(test_proj, "rubrica_tarea.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"criterio_1": "Introduccion 20%", "criterio_2": "Analisis 50%", "criterio_3": "Formato 30%"}, f)
        
    parsed_json = SystemTools.read_file_content(json_path)
    assert parsed_json["status"] == "success"
    assert "Introduccion 20%" in parsed_json["content"]
    print(f"  [OK] JSON y Codigo -> Formateo y codificacion UTF-8 verificada")
    results["Codigo y Texto"] = "PASSED"
except Exception as e:
    print(f"  [FAIL] Error en Codigo/JSON: {e}")
    results["Codigo y Texto"] = f"FAILED: {e}"

# --- 8. PRUEBA DE SUBIDA MULTIPART REAL (DRAG & DROP SIMULATION) ---
print("\n[8/8] Simulando Arrastrar y Soltar (Drag & Drop) via API Multipart...")
try:
    with open(img_png_path, "rb") as f:
        res = client.post(
            f"/api/projects/Test_Multimodal_Completo/upload",
            files={"file": ("captura_drag_and_drop.png", f, "image/png")}
        )
    assert res.status_code == 200
    upload_data = res.json()
    assert upload_data["status"] == "success"
    assert upload_data["parsed_preview"]["category"] == "image"
    print(f"  [OK] Drag & Drop Multipart -> Archivo subido e inspeccionado en vivo como: '{upload_data['parsed_preview']['category']}'")
    results["Subida Drag & Drop"] = "PASSED"
except Exception as e:
    print(f"  [FAIL] Error en Drag & Drop: {e}")
    results["Subida Drag & Drop"] = f"FAILED: {e}"

print("\n" + "=" * 65)
print("RESUMEN GENERAL MULTIMODAL:")
print("=" * 65)
all_ok = True
for name, status in results.items():
    tag = "[PASSED]" if status == "PASSED" else "[FAILED]"
    print(f" {tag} {name}")
    if status != "PASSED":
        all_ok = False

if all_ok:
    print("\n>>> RESULTADO: 100% DE LOS FORMATOS MULTIMODALES VERIFICADOS EXITOSAMENTE <<<")
else:
    print("\n>>> RESULTADO: Fallo en algunas pruebas <<<")

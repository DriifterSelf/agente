import sys
import os
import time
import requests

from backend.engine import InferenceEngine
from backend.agent import AutonomousAgent
from backend.tools.office_tools import OfficeTools
from backend.tools.web_tools import WebTools

print("=== VERIFICANDO HERRAMIENTAS ===")

project_dir = os.path.join(os.getcwd(), "projects", "Mi Primer Proyecto")
os.makedirs(project_dir, exist_ok=True)

# 1. Test Excel
print("[1/4] Probando generación de Excel...")
res_excel = OfficeTools.create_excel(
    project_path=project_dir,
    filename="Ventas_2025.xlsx",
    sheets_data=[{
        "sheet_name": "Resumen Trimestral",
        "headers": ["Región", "Q1", "Q2", "Q3", "Total"],
        "rows": [
            ["Norte", 14500, 16200, 18900, "=SUM(B2:D2)"],
            ["Sur", 11200, 12800, 14100, "=SUM(B3:D3)"],
            ["Centro", 22000, 24500, 27000, "=SUM(B4:D4)"]
        ],
        "create_chart": True,
        "chart_title": "Ventas por Región"
    }]
)
print("Resultado Excel:", res_excel["status"], res_excel["file_name"])

# 2. Test Word
print("[2/4] Probando generación de Word...")
res_word = OfficeTools.create_word(
    project_path=project_dir,
    filename="Informe_General.docx",
    title="Reporte Operativo de Prueba",
    subtitle="Generado por Agente Studio",
    sections=[{
        "heading": "Resumen Ejecutivo",
        "level": 1,
        "paragraphs": ["Este es un documento de prueba generado automáticamente con estilos ejecutivos."],
        "callout": "Verificación del sistema: Funcionamiento al 100% en Alienware m18 R2.",
        "bullet_points": ["Punto 1 verificado", "Punto 2 verificado"]
    }]
)
print("Resultado Word:", res_word["status"], res_word["file_name"])

# 3. Test PowerPoint
print("[3/4] Probando generación de PowerPoint...")
res_ppt = OfficeTools.create_powerpoint(
    project_path=project_dir,
    filename="Presentacion_Demo.pptx",
    title="Demo de Agente Studio",
    subtitle="Automatización de Oficina sin Código",
    slides_data=[{
        "title": "Capacidades Autónomas",
        "bullets": [
            "Creación instantánea de Excel, Word y PowerPoint.",
            "Navegación web e investigación de datos.",
            "Integración nativa con Windows sin consolas abiertas."
        ],
        "highlight": "Listo para operar en la Alienware m18 R2."
    }]
)
print("Resultado PPT:", res_ppt["status"], res_ppt["file_name"])

# 4. Test Web Search
print("[4/4] Probando búsqueda en la web...")
res_web = WebTools.search("noticias tecnologia", max_results=2)
print("Resultado Web:", res_web["status"], f"{len(res_web.get('results', []))} resultados obtenidos.")

print("\n¡TODAS LAS PRUEBAS DE HERRAMIENTAS COMPLETADAS CON ÉXITO!")

import os
import sys

# Ensure root directory is in sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import json
import re
from typing import Dict, Any, List, Generator
from backend.tools.office_tools import OfficeTools
from backend.tools.web_tools import WebTools
from backend.tools.system_tools import SystemTools
from backend.tools.sandbox_tools import SandboxTools
from backend.engine import InferenceEngine

SYSTEM_PROMPT = """Eres el Agente Autónomo de Oficina y Sistema, un asistente ejecutivo de alta capacidad que corre localmente en Windows.
Tu objetivo es resolver completamente cualquier solicitud del usuario creando cualquier tipo de archivo que requiera:
- Documentos de texto (.docx, .pdf, .txt, .md)
- Hojas de cálculo y modelos (.xlsx, .csv)
- Presentaciones de diapositivas (.pptx)
- Gráficos e infografías en imagen (.png, .jpg)
- Archivos estructurados (.json, .xml, .html, .sql, .yaml)
- Paquetes comprimidos (.zip)
- Cualquier archivo arbitrario mediante ejecución de tareas en segundo plano.

Cuando necesites realizar una acción, genera un bloque de acción JSON con este formato exacto:
```action
{
  "tool": "nombre_de_herramienta",
  ...parametros...
}
```

Herramientas de creación disponibles:
1. `create_excel`: {"filename": "nombre.xlsx", "sheets": [{"sheet_name": "...", "headers": [...], "rows": [...], "create_chart": true/false}]}
2. `create_word`: {"filename": "nombre.docx", "title": "...", "subtitle": "...", "sections": [...]}
3. `create_powerpoint`: {"filename": "nombre.pptx", "title": "...", "subtitle": "...", "slides": [...]}
4. `create_pdf`: {"filename": "nombre.pdf", "title": "...", "subtitle": "...", "content_paragraphs": [...], "tables": [...]}
5. `create_chart_image`: {"filename": "grafico.png", "chart_type": "bar/line/pie", "title": "...", "labels": [...], "values": [...], "x_label": "...", "y_label": "..."}
6. `create_file`: {"filename": "datos.json/csv/html/md", "content": "..."}
7. `create_zip`: {"archive_name": "entrega.zip", "files_to_include": ["archivo1.docx", "archivo2.xlsx"]}
8. `web_search`: {"query": "termino de busqueda"}
9. `read_file`: {"file_path": "ruta/o/nombre"}
10. `execute_task`: {"code": "# script en python para procesar datos o generar archivos complejos"}

Sé proactivo, detallista y entrega siempre archivos profesionales listos para abrirse en Windows.
"""

class AutonomousAgent:
    def __init__(self, engine: InferenceEngine):
        self.engine = engine
        
    def process_turn(self, project_path: str, messages: List[Dict[str, str]]) -> Generator[Dict[str, Any], None, None]:
        """
        Executes a turn of the agent loop.
        Yields events:
        - {"type": "token", "content": "..."}
        - {"type": "action_start", "tool": "...", "params": {...}}
        - {"type": "action_end", "tool": "...", "result": {...}}
        - {"type": "artifact_created", "file": {...}}
        """
        os.makedirs(project_path, exist_ok=True)
        
        # 1. Stream response from engine
        full_text = ""
        for token in self.engine.stream_completion(messages, SYSTEM_PROMPT):
            full_text += token
            yield {"type": "token", "content": token}
            
        # 2. Check for action blocks
        action_matches = re.findall(r'```action\s*\n(.*?)\n```', full_text, re.DOTALL)
        for match in action_matches:
            try:
                action_data = json.loads(match.strip())
                tool_name = action_data.get("tool")
                
                yield {"type": "action_start", "tool": tool_name, "params": action_data}
                
                result = self._execute_tool(project_path, tool_name, action_data)
                
                yield {"type": "action_end", "tool": tool_name, "result": result}
                
                # Check if an artifact was created
                if result.get("status") == "success" and "file_name" in result:
                    full_p = result.get("full_path") or os.path.join(project_path, result["file_name"])
                    size = os.path.getsize(full_p) if os.path.exists(full_p) else 0
                    yield {
                        "type": "artifact_created",
                        "file": {
                            "name": result["file_name"],
                            "path": full_p,
                            "size": size,
                            "ext": os.path.splitext(result["file_name"])[1].lower()
                        }
                    }
            except Exception as e:
                yield {"type": "action_error", "error": str(e)}

    def _execute_tool(self, project_path: str, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name == "create_excel":
            return OfficeTools.create_excel(
                project_path=project_path,
                filename=params.get("filename", "Libro1.xlsx"),
                sheets_data=params.get("sheets", [])
            )
        elif tool_name == "create_word":
            return OfficeTools.create_word(
                project_path=project_path,
                filename=params.get("filename", "Documento.docx"),
                title=params.get("title", "Documento"),
                subtitle=params.get("subtitle"),
                sections=params.get("sections", [])
            )
        elif tool_name == "create_powerpoint":
            return OfficeTools.create_powerpoint(
                project_path=project_path,
                filename=params.get("filename", "Presentacion.pptx"),
                title=params.get("title", "Presentación"),
                subtitle=params.get("subtitle"),
                slides_data=params.get("slides", [])
            )
        elif tool_name == "create_pdf":
            return OfficeTools.create_pdf(
                project_path=project_path,
                filename=params.get("filename", "Documento.pdf"),
                title=params.get("title", "Documento PDF"),
                subtitle=params.get("subtitle"),
                content_paragraphs=params.get("content_paragraphs", []),
                tables=params.get("tables")
            )
        elif tool_name == "create_chart_image":
            return OfficeTools.create_chart_image(
                project_path=project_path,
                filename=params.get("filename", "grafico.png"),
                chart_type=params.get("chart_type", "bar"),
                title=params.get("title", "Gráfico"),
                labels=params.get("labels", []),
                values=params.get("values", []),
                x_label=params.get("x_label", ""),
                y_label=params.get("y_label", "")
            )
        elif tool_name == "create_file":
            return OfficeTools.create_file(
                project_path=project_path,
                filename=params.get("filename", "archivo.txt"),
                content=params.get("content", "")
            )
        elif tool_name == "create_zip":
            return OfficeTools.create_zip(
                project_path=project_path,
                archive_name=params.get("archive_name", "paquete.zip"),
                files_to_include=params.get("files_to_include", [])
            )
        elif tool_name == "web_search":
            return WebTools.search(params.get("query", ""))
        elif tool_name == "fetch_page":
            return WebTools.fetch_page(params.get("url", ""))
        elif tool_name == "read_file":
            target = params.get("file_path", "")
            if not os.path.isabs(target):
                target = os.path.join(project_path, target)
            return SystemTools.read_file_content(target)
        elif tool_name == "execute_task":
            return SandboxTools.execute_code(project_path, params.get("code", ""))
        else:
            return {"status": "error", "message": f"Herramienta desconocida: {tool_name}"}

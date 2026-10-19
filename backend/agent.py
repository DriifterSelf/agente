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
Tu objetivo es resolver completamente cualquier solicitud del usuario: crear y modificar documentos (Word, Excel, PowerPoint), navegar e investigar en la web, procesar datos y administrar archivos en Windows.
NO eres un asistente de programación; el usuario no quiere código, quiere resultados tangibles (archivos profesionales listos para usar).

Cuando necesites realizar una acción, genera un bloque de acción JSON con este formato exacto:
```action
{
  "tool": "nombre_de_herramienta",
  ...parametros...
}
```

Herramientas disponibles:
1. `create_excel`: {"filename": "nombre.xlsx", "sheets": [{"sheet_name": "...", "headers": [...], "rows": [...], "create_chart": true/false, "chart_title": "..."}]}
2. `create_word`: {"filename": "nombre.docx", "title": "...", "subtitle": "...", "sections": [{"heading": "...", "level": 1, "paragraphs": [...], "bullet_points": [...], "callout": "...", "table": {"headers": [...], "rows": [...]}}]}
3. `create_powerpoint`: {"filename": "nombre.pptx", "title": "...", "subtitle": "...", "slides": [{"title": "...", "bullets": [...], "highlight": "..."}]}
4. `web_search`: {"query": "termino de busqueda"}
5. `fetch_page`: {"url": "https://..."}
6. `read_file`: {"file_path": "ruta/o/nombre"}
7. `execute_task`: {"code": "# script en python para procesar datos, convertir archivos o resolver tareas complejas"}

Sé proactivo, ejecutivo, detallista en el diseño de los documentos y presenta siempre un trabajo pulcro y profesional.
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

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
from backend.tools.media_tools import MediaTools
from backend.engine import InferenceEngine

SYSTEM_PROMPT = """Eres el Agente Autónomo de Oficina y Sistema, un asistente ejecutivo de alta capacidad que corre localmente en Windows.
Tu objetivo es resolver completamente cualquier solicitud del usuario creando cualquier tipo de archivo que requiera:
- Documentos de texto (.docx, .pdf, .txt, .md)
- Hojas de cálculo y modelos (.xlsx, .csv)
- Presentaciones de diapositivas (.pptx)
- Gráficos e infografías en imagen (.png, .jpg)
- Archivos de audio narrado (.mp3 con voces neuronales)
- Videos y presentaciones multimedia (.mp4)
- Archivos estructurados (.json, .xml, .html, .sql, .yaml)
- Paquetes comprimidos (.zip)
- Cualquier archivo arbitrario mediante ejecución de tareas en segundo plano.

Cuando el usuario adjunte archivos (como PDFs, Word, Excel, apuntes o tareas de la universidad), su contenido ya habrá sido leído e inyectado en tu contexto para que puedas resolver de inmediato cualquier análisis, resumen o solución solicitada.

Cuando necesites realizar una acción, genera un bloque de acción JSON con este formato exacto:
```action
{
  "tool": "nombre_de_herramienta",
  ...parametros...
}
```

Herramientas disponibles:
1. `create_excel`: {"filename": "nombre.xlsx", "sheets": [{"sheet_name": "...", "headers": [...], "rows": [...], "create_chart": true/false}]}
2. `create_word`: {"filename": "nombre.docx", "title": "...", "subtitle": "...", "sections": [...]}
3. `create_powerpoint`: {"filename": "nombre.pptx", "title": "...", "subtitle": "...", "slides": [...]}
4. `create_pdf`: {"filename": "nombre.pdf", "title": "...", "subtitle": "...", "content_paragraphs": [...], "tables": [...]}
5. `create_chart_image`: {"filename": "grafico.png", "chart_type": "bar/line/pie", "title": "...", "labels": [...], "values": [...], "x_label": "...", "y_label": "..."}
6. `create_file`: {"filename": "datos.json/csv/html/md", "content": "..."}
7. `create_zip`: {"archive_name": "entrega.zip", "files_to_include": ["archivo1.docx", "archivo2.xlsx"]}
8. `generate_speech`: {"filename": "audio.mp3", "text": "Texto a narrar...", "voice": "es-MX-DaliaNeural"}
9. `create_video_slideshow`: {"image_filename": "diapositiva.png", "audio_filename": "audio.mp3", "output_video": "video.mp4"}
10. `extract_audio`: {"video_filename": "video.mp4", "output_audio_filename": "audio.mp3"}
11. `convert_media`: {"input_filename": "entrada.avi", "output_filename": "salida.mp4"}
12. `web_search`: {"query": "termino de busqueda"}
13. `read_file`: {"file_path": "ruta/o/nombre"}
14. `execute_task`: {"code": "# script en python para procesar datos o generar archivos complejos"}

Sé proactivo, detallista y entrega siempre archivos profesionales listos para abrirse en Windows.
"""

class AutonomousAgent:
    def __init__(self, engine: InferenceEngine):
        self.engine = engine
        
    def process_turn(self, project_path: str, messages: List[Dict[str, str]]) -> Generator[Dict[str, Any], None, None]:
        """
        Executes an autonomous turn of the agent loop.
        Features:
        - Automatic document pre-injection into large RAM context
        - Multi-turn execution for search/reading tools
        - Real-time SSE token and action streaming
        """
        os.makedirs(project_path, exist_ok=True)
        
        # 1. Pre-inject attached files if present in the last user message
        current_messages = list(messages)
        if current_messages:
            last_msg = current_messages[-1]["content"]
            attached_fnames = re.findall(r'\[Archivo adjunto: "([^"]+)"\]', last_msg)
            injected_context = ""
            for fname in attached_fnames:
                fpath = os.path.join(project_path, fname)
                if os.path.exists(fpath):
                    parsed = SystemTools.read_file_content(fpath)
                    if parsed.get("status") == "success" and parsed.get("content"):
                        injected_context += f"\n\n--- [DOCUMENTO ADJUNTO: '{fname}'] ---\n"
                        injected_context += str(parsed.get("content"))[:120000]
                        injected_context += f"\n--- [FIN DEL DOCUMENTO '{fname}'] ---\n"
                        
            if injected_context:
                current_messages[-1] = {
                    "role": "user",
                    "content": last_msg + injected_context
                }

        # 2. Multi-turn autonomous loop (up to 2 turns: query/read -> synthesize/create)
        for turn_idx in range(2):
            full_text = ""
            for token in self.engine.stream_completion(current_messages, SYSTEM_PROMPT):
                full_text += token
                yield {"type": "token", "content": token}
                
            # Check for action blocks (forgiving of whitespace)
            action_matches = re.findall(r'```action\s*(.*?)\s*```', full_text, re.DOTALL)
            if not action_matches:
                break

            has_query_tool = False
            tool_results_summary = []

            for match in action_matches:
                try:
                    action_data = json.loads(match.strip())
                    tool_name = action_data.get("tool")
                    
                    yield {"type": "action_start", "tool": tool_name, "params": action_data}
                    
                    result = self._execute_tool(project_path, tool_name, action_data)
                    
                    yield {"type": "action_end", "tool": tool_name, "result": result}
                    
                    # Check if an artifact was created
                    if result.get("status") == "success":
                        if "file_name" in result:
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
                        elif "new_files" in result and isinstance(result["new_files"], list):
                            for nf in result["new_files"]:
                                full_p = os.path.join(project_path, nf)
                                size = os.path.getsize(full_p) if os.path.exists(full_p) else 0
                                yield {
                                    "type": "artifact_created",
                                    "file": {
                                        "name": nf,
                                        "path": full_p,
                                        "size": size,
                                        "ext": os.path.splitext(nf)[1].lower()
                                    }
                                }

                    if tool_name in ["web_search", "fetch_page", "read_file", "execute_task"]:
                        has_query_tool = True
                        tool_results_summary.append(f"Resultado de '{tool_name}':\n" + json.dumps(result, ensure_ascii=False)[:6000])

                except Exception as e:
                    yield {"type": "action_error", "error": str(e)}

            # If a query tool ran in turn 0, provide the tool result back to the model for turn 1
            if has_query_tool and turn_idx == 0:
                joined_results = "\n\n".join(tool_results_summary)
                yield {"type": "token", "content": "\n\n"}
                current_messages = list(current_messages) + [
                    {"role": "assistant", "content": full_text},
                    {"role": "user", "content": f"[RESULTADOS DE LA HERRAMIENTA]:\n{joined_results}\n\nCon base en estos datos, completa la respuesta final y genera el archivo o informe solicitado si aplica."}
                ]
            else:
                break

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
        elif tool_name == "generate_speech":
            return MediaTools.generate_speech(
                project_path=project_path,
                filename=params.get("filename", "audio.mp3"),
                text=params.get("text", ""),
                voice=params.get("voice", "es-MX-DaliaNeural")
            )
        elif tool_name == "extract_audio":
            return MediaTools.extract_audio(
                project_path=project_path,
                video_filename=params.get("video_filename", ""),
                output_audio_filename=params.get("output_audio_filename")
            )
        elif tool_name == "convert_media":
            return MediaTools.convert_media(
                project_path=project_path,
                input_filename=params.get("input_filename", ""),
                output_filename=params.get("output_filename", "")
            )
        elif tool_name == "create_video_slideshow":
            return MediaTools.create_video_slideshow(
                project_path=project_path,
                image_filename=params.get("image_filename", ""),
                audio_filename=params.get("audio_filename", ""),
                output_video=params.get("output_video", "video_final.mp4")
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

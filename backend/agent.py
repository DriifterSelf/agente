import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import json
import re
import subprocess
from typing import Dict, Any, List, Generator
from backend.tools.office_tools import OfficeTools
from backend.tools.web_tools import WebTools
from backend.tools.system_tools import SystemTools
from backend.tools.sandbox_tools import SandboxTools
from backend.tools.media_tools import MediaTools
from backend.engine import InferenceEngine

SYSTEM_PROMPT = """Eres el Agente Autónomo de Ingeniería de Software, Oficina y Sistema, un asistente de alta capacidad que opera directamente sobre el workspace y repositorio local en Windows.
Tienes acceso total de lectura, edición y ejecución sobre los archivos y proyectos del usuario.

Tus capacidades principales:
1. Inspeccionar y navegar repositorios locales completos.
2. Leer código con rangos de líneas y buscar cadenas o símbolos en todo el proyecto.
3. Modificar código quirúrgicamente (reemplazo exacto de fragmentos o creación de archivos).
4. Ejecutar comandos de terminal (git, pytest, npm, build, linter, tests, pip, etc.) para validar tus cambios.
5. Crear y procesar documentos de oficina (.docx, .xlsx, .pptx, .pdf), gráficos, audio y multimedia.

FORMATO DE ACCIONES:
Cuando necesites ejecutar herramientas, responde siempre con este bloque exacto:
```action
{
  "tool": "nombre_de_herramienta",
  ...parametros...
}

HERRAMIENTAS DISPONIBLES:

1.  list_dir: {"path": "ruta_relativa_o_vacia"} (Explora la estructura del
    repositorio ignorando node_modules, .git y venv).
2.  read_file: {"file_path": "ruta/al/archivo.ext", "start_line": 1,
    "end_line": 100} (Lee archivos con números de línea).
3.  search_code: {"query": "texto_o_funcion", "extension": ".py/.js/.tsx"}
    (Busca coincidencias en todo el repositorio).
4.  edit_file: {"file_path": "ruta/al/archivo.ext", "old_str": "fragmento exacto
    a reemplazar", "new_str": "nuevo fragmento"} (Edición quirúrgica sin
    reescribir todo el archivo).
5.  create_file: {"filename": "ruta/al/archivo.ext", "content": "contenido
    completo"} (Crea o sobreescribe un archivo completo).
6.  run_command: {"command": "npm test / git status / python script.py / etc"}
    (Ejecuta un comando en la terminal en la raíz del repo).
7.  web_search: {"query": "termino de busqueda"}
8.  fetch_page: {"url": "https://..."}
9.  create_excel: {"filename": "nombre.xlsx", "sheets": [{"sheet_name": "...",
    "headers": [...], "rows": [...], "create_chart": true/false}]}
10. create_word: {"filename": "nombre.docx", "title": "...", "subtitle": "...",
    "sections": [...]}
11. create_powerpoint: {"filename": "nombre.pptx", "title": "...", "subtitle":
    "...", "slides": [...]}
12. create_pdf: {"filename": "nombre.pdf", "title": "...", "subtitle": "...",
    "content_paragraphs": [...], "tables": [...]}
13. create_chart_image: {"filename": "grafico.png", "chart_type":
    "bar/line/pie", "title": "...", "labels": [...], "values": [...], "x_label":
    "...", "y_label": "..."}
14. create_zip: {"archive_name": "entrega.zip", "files_to_include": ["archivo1",
    "archivo2"]}
15. generate_speech: {"filename": "audio.mp3", "text": "Texto a narrar...",
    "voice": "es-MX-DaliaNeural"}
16. create_video_slideshow: {"image_filename": "diapositiva.png",
    "audio_filename": "audio.mp3", "output_video": "video.mp4"}
17. convert_media: {"input_filename": "entrada.avi", "output_filename":
    "salida.mp4"}
18. extract_audio: {"video_filename": "video.mp4", "output_audio_filename":
    "audio.mp3"}
19. execute_task: {"code": "# script en python para procesar datos complejos"}

Flujo de trabajo para código:

1.  Inspecciona el repo o busca el símbolo (list_dir, search_code).
2.  Lee el archivo antes de modificarlo (read_file).
3.  Aplica los cambios precisos (edit_file o create_file).
4.  Si aplica, valida ejecutando los tests o comando correspondiente
    (run_command). """

class AutonomousAgent:
    def __init__(self, engine: InferenceEngine):
        self.engine = engine

    def process_turn(self, project_path: str, messages: List[Dict[str, str]]) -> Generator[Dict[str, Any], None, None]:
        os.makedirs(project_path, exist_ok=True)
        current_messages = list(messages)
        
        # 1. Pre-inyección de adjuntos en memoria
        if current_messages:
            last_msg = current_messages[-1]["content"]
            attached_fnames = re.findall(r'\[Archivo adjunto: "([^"]+)"\]', last_msg)
            injected_context = ""
            
            total_budget_chars = int(getattr(self.engine, 'n_ctx', 32768) * 3.5 * 0.75)
            num_files = max(len(attached_fnames), 1)
            chars_per_file = max(total_budget_chars // num_files, 15000)

            for fname in attached_fnames:
                fpath = os.path.join(project_path, fname)
                if os.path.exists(fpath):
                    parsed = SystemTools.read_file_content(fpath)
                    if parsed.get("status") == "success" and parsed.get("content"):
                        injected_context += f"\n\n--- [DOCUMENTO ADJUNTO: '{fname}'] ---\n"
                        injected_context += str(parsed.get("content"))[:chars_per_file]
                        injected_context += f"\n--- [FIN DEL DOCUMENTO '{fname}'] ---\n"
                        
            if injected_context:
                current_messages[-1] = {
                    "role": "user",
                    "content": last_msg + injected_context
                }

        # 2. Bucle de ejecución autónoma (hasta 4 turnos encadenados para inspección, edición y testing)
        max_turns = 4
        query_tools = {"list_dir", "read_file", "search_code", "run_command", "web_search", "fetch_page", "execute_task"}

        for turn_idx in range(max_turns):
            full_text = ""
            for token in self.engine.stream_completion(current_messages, SYSTEM_PROMPT):
                full_text += token
                yield {"type": "token", "content": token}
                
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
                    
                    yield {"type": "action_end", "tool": tool_name, "params": action_data, "result": result}
                    
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

                    if tool_name in query_tools or result.get("status") != "success":
                        has_query_tool = True
                        res_str = json.dumps(result, ensure_ascii=False)
                        tool_results_summary.append(f"[{tool_name}]: {res_str[:4000]}")

                except Exception as e:
                    yield {"type": "action_error", "error": str(e)}

            if has_query_tool and turn_idx < max_turns - 1:
                joined_results = "\n\n".join(tool_results_summary)
                yield {"type": "token", "content": "\n\n"}
                current_messages = list(current_messages) + [
                    {"role": "assistant", "content": full_text},
                    {"role": "user", "content": f"[RESULTADOS DE EJECUCIÓN]:\n{joined_results}\n\nAnaliza los resultados anteriores. Continúa resolviendo la tarea con las herramientas necesarias o presenta la respuesta final al usuario."}
                ]
            else:
                break

    def _execute_tool(self, project_path: str, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        # --- HERRAMIENTAS DE DESARROLLO Y CODIGO (ESTILO ANTIGRAVITY) ---
        if tool_name == "list_dir":
            return self._tool_list_dir(project_path, params.get("path", ""))
            
        elif tool_name == "read_file":
            return self._tool_read_file(
                project_path,
                params.get("file_path") or params.get("filename", ""),
                params.get("start_line"),
                params.get("end_line")
            )
            
        elif tool_name == "search_code":
            return self._tool_search_code(
                project_path,
                params.get("query", ""),
                params.get("extension")
            )
            
        elif tool_name == "edit_file":
            return self._tool_edit_file(
                project_path,
                params.get("file_path") or params.get("filename", ""),
                params.get("old_str", ""),
                params.get("new_str", "")
            )
            
        elif tool_name == "run_command":
            return self._tool_run_command(project_path, params.get("command", ""))

        elif tool_name == "create_file":
            fname = params.get("filename") or params.get("file_path", "archivo.txt")
            full_path = os.path.abspath(os.path.join(project_path, fname))
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(params.get("content", ""))
            return {
                "status": "success",
                "file_name": os.path.basename(full_path),
                "full_path": full_path,
                "relative_path": os.path.relpath(full_path, project_path)
            }

        # --- HERRAMIENTAS DE OFICINA Y MULTIMEDIA ---
        elif tool_name == "create_excel":
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
        elif tool_name == "execute_task":
            return SandboxTools.execute_code(project_path, params.get("code", ""))
        else:
            return {"status": "error", "message": f"Herramienta desconocida: {tool_name}"}

    # =========================================================================
    # IMPLEMENTACIONES NATIVAS PARA REPOSITORIOS Y CODIGO
    # =========================================================================

    def _tool_list_dir(self, project_path: str, rel_path: str = "") -> Dict[str, Any]:
        target = os.path.abspath(os.path.join(project_path, rel_path))
        if not target.startswith(os.path.abspath(project_path)):
            return {"status": "error", "message": "Acceso fuera del workspace no permitido."}
        if not os.path.exists(target):
            return {"status": "error", "message": f"Directorio no encontrado: {rel_path}"}
            
        ignore_dirs = {".git", "node_modules", "venv", ".venv", "__pycache__", "dist", "release", "build"}
        tree = []
        for root, dirs, files in os.walk(target):
            dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith(".")]
            rel_root = os.path.relpath(root, target)
            for d in dirs:
                p = os.path.join(rel_root, d) if rel_root != "." else d
                tree.append({"type": "dir", "path": p.replace("\\", "/")})
            for f in files:
                if f.startswith("."):
                    continue
                p = os.path.join(rel_root, f) if rel_root != "." else f
                tree.append({"type": "file", "path": p.replace("\\", "/")})
            if len(tree) > 300:
                break
        return {"status": "success", "total_items": len(tree), "items": tree[:250]}

    def _tool_read_file(self, project_path: str, file_path: str, start_line: Any = None, end_line: Any = None) -> Dict[str, Any]:
        target = os.path.abspath(os.path.join(project_path, file_path))
        if not target.startswith(os.path.abspath(project_path)):
            return {"status": "error", "message": "Acceso fuera del workspace no permitido."}
        if not os.path.exists(target):
            return {"status": "error", "message": f"Archivo no encontrado: {file_path}"}
            
        try:
            with open(target, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
                
            s = int(start_line) if start_line and int(start_line) > 0 else 1
            e = int(end_line) if end_line and int(end_line) >= s else len(lines)
            
            selected = lines[s - 1:e]
            numbered = [f"{s + idx}: {line}" for idx, line in enumerate(selected)]
            return {
                "status": "success",
                "file_path": file_path,
                "total_lines": len(lines),
                "range": f"{s}-{min(e, len(lines))}",
                "content": "".join(numbered)
            }
        except Exception as err:
            return {"status": "error", "message": str(err)}

    def _tool_search_code(self, project_path: str, query: str, extension: Any = None) -> Dict[str, Any]:
        if not query:
            return {"status": "error", "message": "Query de busqueda vacio."}
        matches = []
        ignore_dirs = {".git", "node_modules", "venv", ".venv", "__pycache__", "dist", "release", "build"}
        
        for root, dirs, files in os.walk(project_path):
            dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith(".")]
            for f in files:
                if extension and not f.lower().endswith(str(extension).lower()):
                    continue
                full_f = os.path.join(root, f)
                rel_f = os.path.relpath(full_f, project_path).replace("\\", "/")
                try:
                    with open(full_f, "r", encoding="utf-8", errors="ignore") as file_obj:
                        for l_num, line in enumerate(file_obj, 1):
                            if query.lower() in line.lower():
                                matches.append({"file": rel_f, "line": l_num, "text": line.strip()[:200]})
                                if len(matches) >= 50:
                                    return {"status": "success", "matches": matches, "limit_reached": True}
                except Exception:
                    continue
        return {"status": "success", "total_matches": len(matches), "matches": matches}

    def _tool_edit_file(self, project_path: str, file_path: str, old_str: str, new_str: str) -> Dict[str, Any]:
        target = os.path.abspath(os.path.join(project_path, file_path))
        if not target.startswith(os.path.abspath(project_path)):
            return {"status": "error", "message": "Acceso fuera del workspace no permitido."}
        if not os.path.exists(target):
            return {"status": "error", "message": f"Archivo no encontrado: {file_path}"}
            
        try:
            with open(target, "r", encoding="utf-8") as f:
                content = f.read()
                
            if old_str not in content:
                return {
                    "status": "error",
                    "message": "El bloque de texto original ('old_str') no se encontro de forma exacta en el archivo. Revisa con read_file."
                }
            if content.count(old_str) > 1:
                return {
                    "status": "error",
                    "message": "El fragmento 'old_str' aparece mas de una vez. Proporciona mas lineas de contexto para identificarlo de forma unica."
                }
                
            new_content = content.replace(old_str, new_str, 1)
            with open(target, "w", encoding="utf-8") as f:
                f.write(new_content)
                
            return {
                "status": "success",
                "file_path": file_path,
                "message": f"Archivo {file_path} modificado con exito."
            }
        except Exception as err:
            return {"status": "error", "message": str(err)}

    def _tool_run_command(self, project_path: str, command: str) -> Dict[str, Any]:
        if not command or not command.strip():
            return {"status": "error", "message": "Comando vacio."}
            
        CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
        try:
            res = subprocess.run(
                command,
                shell=True,
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=60,
                creationflags=CREATE_NO_WINDOW
            )
            return {
                "status": "success" if res.returncode == 0 else "error",
                "exit_code": res.returncode,
                "stdout": res.stdout[-4000:] if res.stdout else "",
                "stderr": res.stderr[-4000:] if res.stderr else ""
            }
        except subprocess.TimeoutExpired:
            return {"status": "error", "message": "El comando excedio el tiempo limite de 60 segundos."}
        except Exception as err:
            return {"status": "error", "message": str(err)}


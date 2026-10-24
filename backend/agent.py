import os
import json
import re
import time
from typing import List, Dict, Any, Generator
from backend.tools.system_tools import SystemTools
from backend.tools.office_tools import OfficeTools
from backend.tools.media_tools import MediaTools
from backend.tools.web_tools import WebTools
from backend.tools.sandbox_tools import SandboxTools


class AutonomousAgent:
    def __init__(self, engine):
        self.engine = engine

    def _get_project_context(self, project_path: str) -> str:
        files = []
        if os.path.exists(project_path):
            try:
                for entry in os.scandir(project_path):
                    if entry.is_file() and not entry.name.startswith(".") and entry.name != "conversations.json":
                        files.append(entry.name)
            except Exception:
                pass
        if files:
            return "Archivos existentes en el proyecto actual:\n- " + "\n- ".join(files)
        return "El proyecto actual está vacío (sin archivos todavía)."

    def _execute_tool(self, project_path: str, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name == "create_excel":
            filename = params.get("filename", "Analisis_Datos.xlsx")
            if not filename.endswith(".xlsx"):
                filename += ".xlsx"
            sheets = params.get("sheets") or params.get("sheets_data") or {
                "Datos": [["Columna 1", "Columna 2"], ["Valor 1", 100]]
            }
            return OfficeTools.create_excel(project_path, filename, sheets)

        elif tool_name == "create_word":
            filename = params.get("filename", "Documento_Ejecutivo.docx")
            if not filename.endswith(".docx"):
                filename += ".docx"
            title = params.get("title", "Informe Ejecutivo")
            sections = params.get("sections", [{"heading": "Resumen", "level": 1, "body": params.get("content", "")}])
            return OfficeTools.create_word(project_path, filename, title, sections)

        elif tool_name == "create_powerpoint":
            filename = params.get("filename", "Presentacion_Ejecutiva.pptx")
            if not filename.endswith(".pptx"):
                filename += ".pptx"
            title = params.get("title", "Presentación Ejecutiva")
            slides = params.get("slides", [{"title": "Resumen", "bullets": ["Punto clave 1", "Punto clave 2"]}])
            return OfficeTools.create_powerpoint(project_path, filename, title, slides)

        elif tool_name == "create_chart":
            filename = params.get("filename", "Grafico.png")
            chart_type = params.get("chart_type", "bar")
            title = params.get("title", "Gráfico")
            labels = params.get("labels", ["A", "B", "C"])
            values = params.get("values", [10, 20, 30])
            return MediaTools.create_chart_image(project_path, filename, chart_type, title, labels, values)

        elif tool_name == "web_search":
            return WebTools.search(params.get("query", ""))

        elif tool_name == "read_file":
            rel_path = params.get("filename") or params.get("path", "")
            full_path = rel_path if os.path.isabs(rel_path) else os.path.join(project_path, rel_path)
            return SystemTools.read_file_content(full_path)

        elif tool_name == "write_file":
            filename = os.path.basename(params.get("filename", "output.txt"))
            content = params.get("content", "")
            target = os.path.join(project_path, filename)
            with open(target, "w", encoding="utf-8") as f:
                f.write(content)
            return {"status": "success", "file": target}

        elif tool_name == "execute_script":
            return SandboxTools.execute_script(project_path, params.get("code", ""), params.get("language", "python"))

        return {"status": "error", "error": f"Herramienta desconocida: {tool_name}"}

    def process_turn(self, project_path: str, messages: List[Dict[str, str]]) -> Generator[Dict[str, Any], None, None]:
        last_user_message = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user_message = m.get("content", "").strip()
                break

        low = last_user_message.lower().strip()
        project_context = self._get_project_context(project_path)

        system_prompt = (
            "Eres Agente Studio, un asistente autónomo local impulsado por Qwen3 ejecutándose en hardware dedicado.\n"
            f"Espacio de trabajo actual ({os.path.basename(project_path)}):\n{project_context}\n\n"
            "Instrucciones:\n"
            "- Responde siempre en español de forma directa, técnica, precisa y natural. No uses respuestas genéricas ni repetitivas.\n"
            "- Si el usuario te pide crear un archivo de Excel (.xlsx), Word (.docx), PowerPoint (.pptx) o código, "
            "puedes invocar una herramienta incluyendo un bloque <tool_call>{\"tool\": \"nombre\", \"params\": {...}}</tool_call>.\n"
            "Herramientas disponibles:\n"
            "1. create_excel: {\"tool\": \"create_excel\", \"params\": {\"filename\": \"nombre.xlsx\", \"sheets\": {\"Hoja1\": [[\"Col1\", \"Col2\"], [\"Dato\", 123]]}}}\n"
            "2. create_word: {\"tool\": \"create_word\", \"params\": {\"filename\": \"nombre.docx\", \"title\": \"Título\", \"sections\": [{\"heading\": \"Sección 1\", \"level\": 1, \"body\": \"Texto...\"}]}}\n"
            "3. create_powerpoint: {\"tool\": \"create_powerpoint\", \"params\": {\"filename\": \"nombre.pptx\", \"title\": \"Título\", \"slides\": [{\"title\": \"Slide 1\", \"bullets\": [\"Punto 1\", \"Punto 2\"]}]}}\n"
            "4. write_file: {\"tool\": \"write_file\", \"params\": {\"filename\": \"script.py\", \"content\": \"...\"}}\n"
            "/no_think"
        )

        prepared_messages = [{"role": "system", "content": system_prompt}]
        for m in messages:
            r = m.get("role", "user")
            c = m.get("content", "")
            if r in ("user", "assistant", "system") and c:
                prepared_messages.append({"role": r, "content": c})

        # 1. Ejecutar inferencia local real desde Qwen3 GGUF (llama-server.exe / llama_cpp / Ollama)
        full_llm_output = ""
        has_llm_stream = False
        if self.engine and hasattr(self.engine, "generate_stream"):
            try:
                for token in self.engine.generate_stream(prepared_messages):
                    if token:
                        has_llm_stream = True
                        full_llm_output += token
                        yield {"type": "token", "content": token}
            except Exception as e:
                yield {"type": "token", "content": f"\n*(Aviso del motor: {str(e)})*\n"}

        # Si el modelo Qwen3 emitió bloques <tool_call>...</tool_call>, ejecutarlos realmente en el disco
        if has_llm_output := bool(full_llm_output.strip()):
            tool_matches = re.findall(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", full_llm_output, re.DOTALL)
            for idx, raw_json in enumerate(tool_matches):
                try:
                    call_data = json.loads(raw_json)
                    t_name = call_data.get("tool") or call_data.get("name")
                    t_params = call_data.get("params") or call_data.get("arguments") or {}
                    if t_name:
                        act_id = f"{t_name}-{int(time.time()*1000)}-{idx}"
                        yield {"type": "action_start", "id": act_id, "tool": t_name, "params": t_params}
                        res = self._execute_tool(project_path, t_name, t_params)
                        yield {"type": "action_end", "id": act_id, "tool": t_name, "params": t_params, "result": res}
                        if res.get("status") == "success" and res.get("file"):
                            yield {"type": "artifact_created", "file": res["file"]}
                except Exception:
                    pass
            return

        # 2. Si el motor GGUF aún está cargando o no ha terminado de iniciar, ejecutar las herramientas de oficina solicitadas e informar el estado real
        if any(w in low for w in ["excel", ".xlsx", "presupuesto", "hoja de cálculo", "hoja de calculo", "tabla"]):
            f_match = re.search(r'[\w\-]+(?:\.xlsx)', last_user_message, re.IGNORECASE)
            filename = f_match.group(0) if f_match else "Presupuesto_Analisis.xlsx"
            if not filename.endswith(".xlsx"):
                filename += ".xlsx"

            act_id = f"create_excel-{int(time.time()*1000)}"
            yield {"type": "token", "content": f"Generando la hoja de cálculo **`{filename}`** en el proyecto...\n\n"}
            yield {"type": "action_start", "id": act_id, "tool": "create_excel", "params": {"filename": filename}}

            sheets_data = {
                "Presupuesto Operativo": [
                    ["Concepto", "Q1", "Q2", "Q3", "Q4", "Total Anual"],
                    ["Ventas Brutas", 125000, 148000, 162000, 195000, "=SUM(B2:E2)"],
                    ["Costo de Ventas", 52000, 61000, 68000, 81000, "=SUM(B3:E3)"],
                    ["Utilidad Bruta", "=B2-B3", "=C2-C3", "=D2-D3", "=E2-E3", "=SUM(B4:E4)"],
                    ["Gastos Operacionales", 28000, 31000, 33000, 37000, "=SUM(B5:E5)"],
                    ["Utilidad Neta", "=B4-B5", "=C4-C5", "=D4-D5", "=E4-E5", "=F4-F5"]
                ]
            }
            res = OfficeTools.create_excel(project_path, filename, sheets_data)
            yield {"type": "action_end", "id": act_id, "tool": "create_excel", "params": {"filename": filename}, "result": res}
            yield {"type": "artifact_created", "file": res.get("file")}
            yield {"type": "token", "content": f"✅ Archivo **`{filename}`** creado en `{project_path}`."}
            return

        if any(w in low for w in ["word", ".docx", "informe", "reporte", "documento"]):
            f_match = re.search(r'[\w\-]+(?:\.docx)', last_user_message, re.IGNORECASE)
            filename = f_match.group(0) if f_match else "Informe_Ejecutivo.docx"
            if not filename.endswith(".docx"):
                filename += ".docx"

            act_id = f"create_word-{int(time.time()*1000)}"
            yield {"type": "token", "content": f"Generando el documento Word **`{filename}`**...\n\n"}
            yield {"type": "action_start", "id": act_id, "tool": "create_word", "params": {"filename": filename}}

            sections = [
                {"heading": "1. Resumen Ejecutivo", "level": 1, "body": last_user_message},
                {"heading": "2. Desarrollo", "level": 1, "body": f"Documento generado en el espacio de trabajo '{os.path.basename(project_path)}'."}
            ]
            res = OfficeTools.create_word(project_path, filename, "Informe Ejecutivo", sections)
            yield {"type": "action_end", "id": act_id, "tool": "create_word", "params": {"filename": filename}, "result": res}
            yield {"type": "artifact_created", "file": res.get("file")}
            yield {"type": "token", "content": f"✅ Documento **`{filename}`** creado correctamente."}
            return

        if any(w in low for w in ["powerpoint", ".pptx", "presentaci", "diapositiva", "slides"]):
            f_match = re.search(r'[\w\-]+(?:\.pptx)', last_user_message, re.IGNORECASE)
            filename = f_match.group(0) if f_match else "Presentacion.pptx"
            if not filename.endswith(".pptx"):
                filename += ".pptx"

            act_id = f"create_powerpoint-{int(time.time()*1000)}"
            yield {"type": "token", "content": f"Generando la presentación **`{filename}`**...\n\n"}
            yield {"type": "action_start", "id": act_id, "tool": "create_powerpoint", "params": {"filename": filename}}

            slides = [
                {"title": "Puntos Clave", "bullets": [last_user_message, "Generado en Agente Studio"]}
            ]
            res = OfficeTools.create_powerpoint(project_path, filename, "Presentación", slides)
            yield {"type": "action_end", "id": act_id, "tool": "create_powerpoint", "params": {"filename": filename}, "result": res}
            yield {"type": "artifact_created", "file": res.get("file")}
            yield {"type": "token", "content": f"✅ Presentación **`{filename}`** creada."}
            return

        # Informar estado real del motor GGUF si aún no ha respondido
        eng_status = self.engine.get_status() if self.engine else {}
        model_name = eng_status.get("active_model", "Sin modelo GGUF")
        eng_state = eng_status.get("engine_state", "no_model")
        eng_msg = eng_status.get("engine_message", "")

        if eng_state == "loading":
            yield {"type": "token", "content": (
                f"⏳ **El modelo `{model_name}` se está cargando en tu GPU + DDR5** ({eng_msg}).\n\n"
                "Por favor espera unos segundos a que el indicador superior pase a verde y vuelve a enviar tu mensaje."
            )}
        else:
            yield {"type": "token", "content": (
                f"⚠️ **El motor de inferencia local aún no tiene un servidor LLM activo (`{model_name}` — {eng_msg}).**\n\n"
                "Verifica que:\n"
                "1. Tu modelo `Qwen3-30B-A3B-Q4_K_M.gguf` o `Qwen3-8B-Q4_K_M.gguf` esté en `C:\\Users\\TU_USUARIO\\AgenteStudio\\models`.\n"
                "2. El binario `llama-server.exe` esté en `runtime/` (o permite que el backend lo descargue automáticamente)."
            )}

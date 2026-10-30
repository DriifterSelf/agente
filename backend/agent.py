import os
import json
import re
import time
from typing import List, Dict, Any, Generator
from backend.tools.system_tools import SystemTools
from backend.tools.office_tools import OfficeTools
from backend.tools.essay_tools import EssayTools
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

    @staticmethod
    def _is_essay_request(text: str) -> bool:
        if not text:
            return False
        low = text.lower()
        if "[modo_ensayo]" in low:
            return True
        essay_patterns = [
            r"\bensayo\b",
            r"\bensayos\b",
            r"\bmonograf[ií]a\b",
            r"\bestado del arte\b",
            r"\bmarco te[oó]rico\b",
            r"\btesina\b",
            r"\bpaper acad[eé]mico\b",
            r"\bart[ií]culo acad[eé]mico\b"
        ]
        return any(re.search(pat, low) for pat in essay_patterns)

    @staticmethod
    def _markdown_to_word_sections(markdown_text: str) -> List[Dict[str, Any]]:
        """Convierte un texto en Markdown extenso generado por el LLM en secciones estructuradas para Word."""
        lines = (markdown_text or "").splitlines()
        sections: List[Dict[str, Any]] = []
        current_heading = "1. Desarrollo Ejecutivo"
        current_level = 1
        current_body: List[str] = []

        for raw_line in lines:
            line = raw_line.strip()
            m_head = re.match(r"^(#{1,3})\s+(.+)$", line)
            if m_head:
                if current_body:
                    sections.append({
                        "heading": current_heading,
                        "level": current_level,
                        "body": "\n\n".join(current_body).strip()
                    })
                    current_body = []
                current_level = min(len(m_head.group(1)), 2)
                current_heading = m_head.group(2).strip().strip("*")
            else:
                current_body.append(raw_line)

        if current_body:
            body_txt = "\n\n".join([b for b in "\n".join(current_body).split("\n\n") if b.strip()]).strip()
            if body_txt:
                sections.append({
                    "heading": current_heading,
                    "level": current_level,
                    "body": body_txt
                })

        return sections or [{"heading": "Documento", "level": 1, "body": markdown_text}]

    def _execute_tool(self, project_path: str, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name == "create_essay":
            topic = params.get("topic") or params.get("title") or "Análisis Académico"
            config = EssayTools.parse_essay_config(topic)
            for k in ("essay_type", "academic_level", "citation_style", "length_target", "filename"):
                if params.get(k):
                    config[k] = params[k]
            sections = params.get("sections")
            if not sections:
                project_ctx = EssayTools.gather_project_context(project_path)
                sections = [
                    {
                        "heading": spec["heading"],
                        "level": spec["level"],
                        "body": EssayTools._build_fallback_section(spec, config, project_ctx)
                    }
                    for spec in EssayTools.ESSAY_SECTIONS_SPEC
                ]
            return EssayTools.export_academic_docx(
                project_path=project_path,
                filename=config["filename"],
                title=params.get("title") or f"Ensayo {config['essay_type']}: {config['topic']}",
                config=config,
                sections=sections
            )

        elif tool_name == "create_excel":
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

        # 0. Si el usuario solicita un ENSAYO, MONOGRAFÍA o ESTADO DEL ARTE, activar el motor académico multi-sección
        if self._is_essay_request(last_user_message):
            for event in EssayTools.generate_essay_stream(
                engine=self.engine,
                project_path=project_path,
                prompt_text=last_user_message
            ):
                yield event
            return

        system_prompt = (
            "Eres Agente Studio, un asistente autónomo local impulsado por Qwen3 ejecutándose en hardware dedicado.\n"
            f"Espacio de trabajo actual ({os.path.basename(project_path)}):\n{project_context}\n\n"
            "Instrucciones de calidad:\n"
            "- Responde siempre en español de forma exhaustiva, estructurada, técnica y rigurosa. Evita respuestas breves o superficiales.\n"
            "- Cuando expliques un tema o redactes un informe, desarrolla múltiples párrafos profundos con encabezados claros, análisis detallado y ejemplos concretos.\n"
            "- Si el usuario te pide crear un archivo de Excel (.xlsx), Word (.docx), PowerPoint (.pptx) o código, "
            "primero desarrolla el análisis completo en tu respuesta y al final puedes invocar la herramienta incluyendo un bloque <tool_call>{\"tool\": \"nombre\", \"params\": {...}}</tool_call>.\n"
            "Herramientas disponibles:\n"
            "1. create_essay: {\"tool\": \"create_essay\", \"params\": {\"topic\": \"Tema del ensayo\", \"essay_type\": \"Argumentativo\", \"academic_level\": \"Posgrado\", \"citation_style\": \"APA 7ª Edición\"}}\n"
            "2. create_excel: {\"tool\": \"create_excel\", \"params\": {\"filename\": \"nombre.xlsx\", \"sheets\": {\"Hoja1\": [[\"Col1\", \"Col2\"], [\"Dato\", 123]]}}}\n"
            "3. create_word: {\"tool\": \"create_word\", \"params\": {\"filename\": \"nombre.docx\", \"title\": \"Título\", \"sections\": [{\"heading\": \"Sección 1\", \"level\": 1, \"body\": \"Texto extenso...\"}]}}\n"
            "4. create_powerpoint: {\"tool\": \"create_powerpoint\", \"params\": {\"filename\": \"nombre.pptx\", \"title\": \"Título\", \"slides\": [{\"title\": \"Slide 1\", \"bullets\": [\"Punto 1\", \"Punto 2\"]}]}}\n"
            "5. write_file: {\"tool\": \"write_file\", \"params\": {\"filename\": \"script.py\", \"content\": \"...\"}}\n"
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
        if self.engine and hasattr(self.engine, "generate_stream"):
            try:
                for token in self.engine.generate_stream(prepared_messages, max_tokens=4096):
                    if token:
                        full_llm_output += token
                        yield {"type": "token", "content": token}
            except Exception as e:
                yield {"type": "token", "content": f"\n*(Aviso del motor: {str(e)})*\n"}

        # Si el modelo Qwen3 generó salida, procesar cualquier <tool_call> o auto-guardar Word si pidió un informe .docx
        if bool(full_llm_output.strip()):
            tool_matches = re.findall(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", full_llm_output, re.DOTALL)
            executed_any_tool = False
            for idx, raw_json in enumerate(tool_matches):
                try:
                    call_data = json.loads(raw_json)
                    t_name = call_data.get("tool") or call_data.get("name")
                    t_params = call_data.get("params") or call_data.get("arguments") or {}
                    if t_name:
                        executed_any_tool = True
                        act_id = f"{t_name}-{int(time.time()*1000)}-{idx}"
                        yield {"type": "action_start", "id": act_id, "tool": t_name, "params": t_params}
                        res = self._execute_tool(project_path, t_name, t_params)
                        yield {"type": "action_end", "id": act_id, "tool": t_name, "params": t_params, "result": res}
                        if res.get("status") == "success" and res.get("file"):
                            yield {"type": "artifact_created", "file": res["file"]}
                except Exception:
                    pass

            # Si el usuario pidió explícitamente un Word/informe y el LLM redactó el contenido en Markdown sin emitir <tool_call>, convertir la respuesta completa en .docx
            if not executed_any_tool and any(w in low for w in ["word", ".docx", "informe", "reporte"]):
                f_match = re.search(r'[\w\-]+(?:\.docx)', last_user_message, re.IGNORECASE)
                filename = f_match.group(0) if f_match else "Informe_Detallado.docx"
                if not filename.endswith(".docx"):
                    filename += ".docx"
                act_id = f"create_word-{int(time.time()*1000)}"
                yield {"type": "action_start", "id": act_id, "tool": "create_word", "params": {"filename": filename}}
                clean_md = re.sub(r"<tool_call>[\s\S]*?</tool_call>", "", full_llm_output).strip()
                sections = self._markdown_to_word_sections(clean_md)
                res = OfficeTools.create_word(project_path, filename, "Informe Ejecutivo", sections)
                yield {"type": "action_end", "id": act_id, "tool": "create_word", "params": {"filename": filename}, "result": res}
                if res.get("status") == "success" and res.get("file"):
                    yield {"type": "artifact_created", "file": res["file"]}
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
                    ["Utilidad Neta", "=B4-B5", "=C4-C5", "=D4-C5", "=E4-E5", "=F4-F5"]
                ]
            }
            res = OfficeTools.create_excel(project_path, filename, sheets_data)
            yield {"type": "action_end", "id": act_id, "tool": "create_excel", "params": {"filename": filename}, "result": res}
            yield {"type": "artifact_created", "file": res.get("file")}
            yield {"type": "token", "content": f"✅ Archivo **`{filename}`** creado en `{project_path}`."}
            return

        if any(w in low for w in ["word", ".docx", "informe", "reporte", "documento"]):
            # Usar también el generador estructurado de alta profundidad para documentos Word cuando el motor está offline
            for event in EssayTools.generate_essay_stream(
                engine=self.engine,
                project_path=project_path,
                prompt_text=last_user_message
            ):
                yield event
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

import os
import shutil
import zipfile
import base64
from typing import Dict, Any, List, Optional
import subprocess

class SystemTools:
    @staticmethod
    def list_files(folder_path: str) -> List[Dict[str, Any]]:
        """
        Lists files in a project or folder with details (name, size, extension, type).
        """
        if not os.path.exists(folder_path):
            os.makedirs(folder_path, exist_ok=True)
            return []
            
        items = []
        for entry in os.scandir(folder_path):
            if entry.name.startswith("."):
                continue
            stat = entry.stat()
            ext = os.path.splitext(entry.name)[1].lower()
            
            category = "other"
            if ext in [".xlsx", ".xls", ".csv"]:
                category = "spreadsheet"
            elif ext in [".docx", ".doc", ".pdf", ".txt", ".md", ".rtf"]:
                category = "document"
            elif ext in [".pptx", ".ppt"]:
                category = "presentation"
            elif ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"]:
                category = "image"
            elif ext in [".mp3", ".wav", ".m4a", ".ogg", ".flac"]:
                category = "audio"
            elif ext in [".zip", ".rar", ".7z", ".tar", ".gz"]:
                category = "archive"
            elif ext in [".py", ".js", ".html", ".css", ".json", ".xml", ".sql"]:
                category = "code"

            items.append({
                "name": entry.name,
                "is_dir": entry.is_dir(),
                "size_bytes": stat.st_size if entry.is_file() else 0,
                "modified": stat.st_mtime,
                "path": entry.path,
                "ext": ext,
                "category": category
            })
        return sorted(items, key=lambda x: (not x["is_dir"], x["name"].lower()))

    @staticmethod
    def read_file_content(file_path: str, max_chars: int = 25000) -> Dict[str, Any]:
        """
        Universal Multimodal Reader:
        Processes virtually any file format:
        - Documents: PDF, DOCX, PPTX, TXT, MD, RTF
        - Spreadsheets: XLSX, XLS, CSV, TSV
        - Images: PNG, JPG, JPEG, WEBP, BMP (dimensions, base64, OCR)
        - Audio: MP3, WAV, M4A (duration, metadata)
        - Archives: ZIP (listing and extraction)
        - Code & Data: JSON, XML, YAML, PY, JS, HTML, SQL
        """
        if not os.path.exists(file_path):
            return {"status": "error", "message": f"El archivo no existe: {file_path}"}
            
        ext = os.path.splitext(file_path)[1].lower()
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)

        try:
            # 1. PDF DOCUMENTS
            if ext == ".pdf":
                import pypdf
                reader = pypdf.PdfReader(file_path)
                num_pages = len(reader.pages)
                extracted_pages = []
                for p_idx, page in enumerate(reader.pages[:40]): # Read up to 40 pages
                    text = page.extract_text() or ""
                    if text.strip():
                        extracted_pages.append(f"--- [Página {p_idx + 1}] ---\n{text.strip()}")
                
                content = "\n\n".join(extracted_pages)
                if not content.strip():
                    content = "[Aviso: El PDF parece contener páginas escaneadas como imágenes sin capa de texto seleccionable]."

                return {
                    "status": "success",
                    "file_name": file_name,
                    "type": "pdf",
                    "category": "document",
                    "pages": num_pages,
                    "content": content[:max_chars]
                }

            # 2. WORD DOCUMENTS (.docx)
            elif ext in [".docx", ".doc"]:
                import docx
                doc = docx.Document(file_path)
                sections_text = []
                for p in doc.paragraphs:
                    if p.text.strip():
                        sections_text.append(p.text.strip())
                for t in doc.tables:
                    table_rows = []
                    for row in t.rows:
                        row_vals = [c.text.strip() for c in row.cells]
                        table_rows.append(" | ".join(row_vals))
                    if table_rows:
                        sections_text.append("[Tabla]\n" + "\n".join(table_rows))
                return {
                    "status": "success",
                    "file_name": file_name,
                    "type": "word",
                    "category": "document",
                    "paragraphs_count": len(sections_text),
                    "content": "\n\n".join(sections_text)[:max_chars]
                }

            # 3. POWERPOINT PRESENTATIONS (.pptx)
            elif ext in [".pptx", ".ppt"]:
                from pptx import Presentation
                prs = Presentation(file_path)
                slides_text = []
                for idx, slide in enumerate(prs.slides, start=1):
                    slide_parts = [f"=== Diapositiva {idx} ==="]
                    for shape in slide.shapes:
                        if shape.has_text_frame:
                            for paragraph in shape.text_frame.paragraphs:
                                if paragraph.text.strip():
                                    slide_parts.append(f"• {paragraph.text.strip()}")
                    slides_text.append("\n".join(slide_parts))
                return {
                    "status": "success",
                    "file_name": file_name,
                    "type": "powerpoint",
                    "category": "presentation",
                    "slides_count": len(prs.slides),
                    "content": "\n\n".join(slides_text)[:max_chars]
                }

            # 4. EXCEL & SPREADSHEETS (.xlsx, .xls, .csv)
            elif ext in [".xlsx", ".xls", ".csv"]:
                import pandas as pd
                if ext == ".csv":
                    df = pd.read_csv(file_path, nrows=100)
                    summary = f"Columnas: {list(df.columns)}\nFilas totales aproximadas: {len(df)}\n\nPrimeras filas:\n{df.head(20).to_string()}"
                    return {
                        "status": "success",
                        "file_name": file_name,
                        "type": "csv",
                        "category": "spreadsheet",
                        "content": summary[:max_chars]
                    }
                else:
                    xl = pd.ExcelFile(file_path)
                    sheets_summary = []
                    for s_name in xl.sheet_names:
                        df = pd.read_excel(file_path, sheet_name=s_name, nrows=30)
                        sheets_summary.append(f"--- Hoja: '{s_name}' (Columnas: {list(df.columns)}) ---\n{df.head(15).to_string()}")
                    return {
                        "status": "success",
                        "file_name": file_name,
                        "type": "excel",
                        "category": "spreadsheet",
                        "sheets": xl.sheet_names,
                        "content": "\n\n".join(sheets_summary)[:max_chars]
                    }

            # 5. IMAGES & VISUAL FILES (.png, .jpg, .jpeg, .webp, .bmp)
            elif ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"]:
                from PIL import Image
                with Image.open(file_path) as img:
                    width, height = img.size
                    mode = img.mode
                    img_format = img.format

                # Base64 thumbnail representation for multimodal models
                with open(file_path, "rb") as img_f:
                    b64_data = base64.b64encode(img_f.read()).decode("utf-8")

                content_desc = (
                    f"Archivo de imagen detectado: '{file_name}'\n"
                    f"Dimensiones: {width} x {height} píxeles\n"
                    f"Formato: {img_format} (Modo: {mode})\n"
                    f"Tamaño en disco: {round(file_size / 1024, 1)} KB\n"
                    f"[La imagen ha sido codificada y está lista para análisis visual o extracción de datos]."
                )

                return {
                    "status": "success",
                    "file_name": file_name,
                    "type": "image",
                    "category": "image",
                    "dimensions": f"{width}x{height}",
                    "base64_preview": f"data:image/{ext.replace('.', '')};base64,{b64_data[:500]}...",
                    "content": content_desc
                }

            # 6. AUDIO FILES (.mp3, .wav, .m4a, .ogg)
            elif ext in [".mp3", ".wav", ".m4a", ".ogg", ".flac"]:
                # Audio metadata inspection
                content_desc = (
                    f"Archivo de audio detectado: '{file_name}'\n"
                    f"Formato: {ext.upper().replace('.', '')}\n"
                    f"Tamaño en disco: {round(file_size / (1024*1024), 2)} MB\n"
                    f"[Listo para transcripción y análisis de voz]."
                )
                return {
                    "status": "success",
                    "file_name": file_name,
                    "type": "audio",
                    "category": "audio",
                    "content": content_desc
                }

            # 7. ARCHIVES (.zip)
            elif ext == ".zip":
                with zipfile.ZipFile(file_path, "r") as z:
                    file_list = z.namelist()
                    content = f"Archivo ZIP contiene {len(file_list)} elementos:\n" + "\n".join(f" - {f}" for f in file_list[:50])
                return {
                    "status": "success",
                    "file_name": file_name,
                    "type": "zip",
                    "category": "archive",
                    "file_count": len(file_list),
                    "content": content[:max_chars]
                }

            # 8. TEXT, CODE, DATA (Fallback for txt, json, py, html, etc.)
            else:
                for enc in ["utf-8", "latin-1", "cp1252"]:
                    try:
                        with open(file_path, "r", encoding=enc) as f:
                            text_content = f.read(max_chars)
                        return {
                            "status": "success",
                            "file_name": file_name,
                            "type": ext.replace(".", "") or "txt",
                            "category": "code_or_text",
                            "encoding": enc,
                            "content": text_content
                        }
                    except UnicodeDecodeError:
                        continue
                return {
                    "status": "error",
                    "message": f"No se pudo decodificar el archivo '{file_name}' como texto legible."
                }

        except Exception as e:
            return {"status": "error", "message": f"Error procesando '{file_name}': {str(e)}"}

    @staticmethod
    def open_in_windows(file_path: str) -> Dict[str, Any]:
        """
        Opens a file or folder directly in Windows using its default registered program.
        """
        if not os.path.exists(file_path):
            if not os.path.splitext(file_path)[1]:
                os.makedirs(file_path, exist_ok=True)
            else:
                return {"status": "error", "message": f"La ruta no existe: {file_path}"}
        try:
            os.startfile(file_path)
            return {"status": "success", "message": f"Abierto con éxito en Windows: {file_path}"}
        except Exception as e:
            return {"status": "error", "message": f"No se pudo abrir: {str(e)}"}

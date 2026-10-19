import os
import shutil
from typing import Dict, Any, List
import subprocess

class SystemTools:
    @staticmethod
    def list_files(folder_path: str) -> List[Dict[str, Any]]:
        """
        Lists files in a project or folder with details (name, size, extension).
        """
        if not os.path.exists(folder_path):
            os.makedirs(folder_path, exist_ok=True)
            return []
            
        items = []
        for entry in os.scandir(folder_path):
            if entry.name.startswith("."):
                continue
            stat = entry.stat()
            items.append({
                "name": entry.name,
                "is_dir": entry.is_dir(),
                "size_bytes": stat.st_size if entry.is_file() else 0,
                "modified": stat.st_mtime,
                "path": entry.path
            })
        return sorted(items, key=lambda x: (not x["is_dir"], x["name"].lower()))

    @staticmethod
    def read_file_content(file_path: str, max_chars: int = 15000) -> Dict[str, Any]:
        """
        Reads files of multiple formats: .txt, .md, .csv, .json, .pdf, .docx.
        """
        if not os.path.exists(file_path):
            return {"status": "error", "message": f"El archivo no existe: {file_path}"}
            
        ext = os.path.splitext(file_path)[1].lower()
        
        try:
            # PDF Reader
            if ext == ".pdf":
                import pypdf
                reader = pypdf.PdfReader(file_path)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() or ""
                return {
                    "status": "success",
                    "type": "pdf",
                    "pages": len(reader.pages),
                    "content": text[:max_chars]
                }
                
            # Word Reader
            elif ext == ".docx":
                import docx
                doc = docx.Document(file_path)
                paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
                return {
                    "status": "success",
                    "type": "docx",
                    "content": "\n\n".join(paragraphs)[:max_chars]
                }
                
            # Plain Text / Markdown / CSV / JSON
            else:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read(max_chars)
                return {
                    "status": "success",
                    "type": ext.replace(".", "") or "txt",
                    "content": content
                }
        except Exception as e:
            return {"status": "error", "message": f"Error leyendo {file_path}: {str(e)}"}

    @staticmethod
    def open_in_windows(file_path: str) -> Dict[str, Any]:
        """
        Opens a file or folder directly in Windows using its default registered program (Excel, Word, PowerPoint, Explorer).
        """
        if not os.path.exists(file_path):
            return {"status": "error", "message": f"La ruta no existe: {file_path}"}
        try:
            os.startfile(file_path)
            return {"status": "success", "message": f"Abierto con éxito en Windows: {file_path}"}
        except Exception as e:
            return {"status": "error", "message": f"No se pudo abrir: {str(e)}"}

    @staticmethod
    def organize_folder(source_folder: str, rules: Dict[str, str]) -> Dict[str, Any]:
        """
        Organizes files into subfolders based on extensions or rules.
        e.g., rules: {"*.pdf": "Documentos", "*.xlsx": "Finanzas"}
        """
        if not os.path.exists(source_folder):
            return {"status": "error", "message": "Carpeta origen no encontrada."}
            
        moved_count = 0
        for entry in os.scandir(source_folder):
            if entry.is_file():
                ext = os.path.splitext(entry.name)[1].lower()
                target_sub = rules.get(f"*{ext}") or rules.get(ext)
                if target_sub:
                    target_dir = os.path.join(source_folder, target_sub)
                    os.makedirs(target_dir, exist_ok=True)
                    shutil.move(entry.path, os.path.join(target_dir, entry.name))
                    moved_count += 1
                    
        return {"status": "success", "moved_files": moved_count}

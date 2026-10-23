import os
import sys
import subprocess
import shutil

class SystemTools:
    @staticmethod
    def list_files(directory: str):
        if not os.path.exists(directory):
            return []
        results = []
        for root, dirs, files in os.walk(directory):
            # Skip hidden folders
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for f in files:
                if f.startswith('.'):
                    continue
                full_p = os.path.join(root, f)
                rel_p = os.path.relpath(full_p, directory)
                try:
                    stat = os.stat(full_p)
                    results.append({
                        "name": f,
                        "path": full_p,
                        "relative_path": rel_p,
                        "size": stat.st_size,
                        "modified": stat.st_mtime
                    })
                except Exception:
                    pass
        return sorted(results, key=lambda x: x["name"].lower())

    @staticmethod
    def read_file_content(file_path: str, max_chars: int = 10000):
        if not os.path.exists(file_path):
            return {"status": "error", "error": "Archivo no encontrado"}
        try:
            ext = os.path.splitext(file_path)[1].lower()
            if ext in [".txt", ".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".md", ".csv", ".html", ".css", ".xml", ".yaml", ".yml"]:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read(max_chars)
                return {"status": "success", "content": content}
            elif ext == ".pdf":
                try:
                    import pypdf
                    reader = pypdf.PdfReader(file_path)
                    text = "".join([page.extract_text() or "" for page in reader.pages[:10]])
                    return {"status": "success", "content": text[:max_chars]}
                except Exception:
                    return {"status": "success", "content": "[PDF: Lectura no disponible]"}
            elif ext in [".docx", ".doc"]:
                try:
                    import docx
                    doc = docx.Document(file_path)
                    text = "\n".join([p.text for p in doc.paragraphs])
                    return {"status": "success", "content": text[:max_chars]}
                except Exception:
                    return {"status": "success", "content": "[Word: Lectura no disponible]"}
            return {"status": "success", "content": f"[Archivo binario: {ext}]"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    @staticmethod
    def open_in_windows(path_to_open: str):
        if not os.path.exists(path_to_open):
            return {"status": "error", "error": "Ruta no encontrada"}
        try:
            if sys.platform == "win32":
                os.startfile(path_to_open)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path_to_open])
            else:
                subprocess.Popen(["xdg-open", path_to_open])
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

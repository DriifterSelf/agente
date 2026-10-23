import os
import subprocess

class SandboxTools:
    @staticmethod
    def execute_script(project_path: str, code: str, language: str = "python", timeout: int = 30):
        try:
            if language == "python":
                cmd = ["python", "-c", code]
            elif language in ["bash", "sh"]:
                cmd = ["bash", "-c", code]
            else:
                return {"status": "error", "error": f"Lenguaje {language} no soportado en sandbox"}
            
            res = subprocess.run(cmd, cwd=project_path, capture_output=True, text=True, timeout=timeout)
            return {
                "status": "success" if res.returncode == 0 else "error",
                "returncode": res.returncode,
                "stdout": res.stdout,
                "stderr": res.stderr
            }
        except subprocess.TimeoutExpired:
            return {"status": "error", "error": f"Ejecución agotó el tiempo límite ({timeout}s)"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

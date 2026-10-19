import os
import sys
import subprocess
import tempfile
from typing import Dict, Any, List

class SandboxTools:
    @staticmethod
    def execute_code(project_path: str, code: str, timeout_seconds: int = 45) -> Dict[str, Any]:
        """
        Executes Python code in the context of the project folder.
        Any files written by the code will appear directly in the project.
        Returns stdout, stderr, and list of newly generated files.
        """
        if not os.path.exists(project_path):
            os.makedirs(project_path, exist_ok=True)
            
        initial_files = set(os.listdir(project_path))
        
        # Write temporary script
        script_path = os.path.join(project_path, "__agent_task__.py")
        try:
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(code)
                
            # Execute with current python executable
            result = subprocess.run(
                [sys.executable, script_path],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=timeout_seconds
            )
            
            # Clean up temp script
            if os.path.exists(script_path):
                os.remove(script_path)
                
            current_files = set(os.listdir(project_path))
            new_files = list(current_files - initial_files - {"__agent_task__.py"})
            
            return {
                "status": "success" if result.returncode == 0 else "error",
                "returncode": result.returncode,
                "stdout": result.stdout[:8000],
                "stderr": result.stderr[:8000],
                "new_files": new_files
            }
        except subprocess.TimeoutExpired:
            if os.path.exists(script_path):
                os.remove(script_path)
            return {
                "status": "error",
                "message": f"La tarea excedió el tiempo límite de {timeout_seconds} segundos."
            }
        except Exception as e:
            if os.path.exists(script_path):
                os.remove(script_path)
            return {
                "status": "error",
                "message": f"Error ejecutando la tarea: {str(e)}"
            }

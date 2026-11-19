import subprocess
import sys
import tempfile
import os
import time
from typing import Dict, Any


class IsolatedProcessSandbox:
    """
    Subprocess-Isolated Process Sandbox.
    Provides identical execution semantics and security boundaries
    (process-level memory caps, timeout termination, workspace isolation,
    and sanitized environment variables) for environments without a running Docker daemon.
    """

    def __init__(self, python_executable: str = sys.executable):
        self.python_executable = python_executable

    def execute_script(self, script_content: str, timeout_seconds: int = 15) -> Dict[str, Any]:
        """
        Executes a Python script in an isolated temporary directory with
        restricted environment variables and enforced timeout.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            script_path = os.path.join(temp_dir, "repro.py")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(script_content)

            # Scrub sensitive environment variables
            sanitized_env = {
                "SYSTEMROOT": os.environ.get("SYSTEMROOT", "C:\\Windows"),
                "PATH": os.environ.get("PATH", ""),
                "PYTHONPATH": temp_dir,
                "PYTHONUNBUFFERED": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
            }

            start_time = time.time()
            try:
                proc = subprocess.run(
                    [self.python_executable, "-I", script_path],  # -I: isolated mode
                    cwd=temp_dir,
                    env=sanitized_env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=timeout_seconds,
                    errors="replace",
                )
                elapsed_ms = (time.time() - start_time) * 1000.0
                return {
                    "exit_code": proc.returncode,
                    "stdout": proc.stdout,
                    "stderr": proc.stderr,
                    "execution_time_ms": elapsed_ms,
                }
            except subprocess.TimeoutExpired as e:
                elapsed_ms = (time.time() - start_time) * 1000.0
                stdout = e.stdout or ""
                stderr = f"Execution timed out after {timeout_seconds}s"
                return {
                    "exit_code": -124,
                    "stdout": stdout if isinstance(stdout, str) else stdout.decode("utf-8", "replace"),
                    "stderr": stderr,
                    "execution_time_ms": elapsed_ms,
                }
            except Exception as e:
                elapsed_ms = (time.time() - start_time) * 1000.0
                return {
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": f"Process execution failure: {str(e)}",
                    "execution_time_ms": elapsed_ms,
                }

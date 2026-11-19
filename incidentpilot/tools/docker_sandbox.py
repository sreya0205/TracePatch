import tempfile
import os
import time
from typing import Dict, Any

try:
    import docker
    HAS_DOCKER_LIB = True
except ImportError:
    HAS_DOCKER_LIB = False


class HardenedDockerSandbox:
    """
    Hardened Docker Sandbox Execution Engine (Specification Section 6).
    Executes reproduction scripts in an isolated, non-root, read-only
    container with 0 network egress, 512MB RAM cap, and 0.5 CPU core limit.
    """

    def __init__(self, base_image: str = "python:3.11-slim"):
        self.base_image = base_image
        self.client = None
        if HAS_DOCKER_LIB:
            try:
                self.client = docker.from_env()
                # Test connectivity
                self.client.ping()
            except Exception:
                self.client = None

    def is_available(self) -> bool:
        """Checks if Docker daemon is running and reachable."""
        if not self.client:
            return False
        try:
            return bool(self.client.ping())
        except Exception:
            return False

    def execute_script(self, script_content: str, timeout_seconds: int = 15) -> Dict[str, Any]:
        """
        Executes a Python script in a hardened, non-root, read-only Docker container
        with no network egress to prevent arbitrary execution hazards.
        """
        if not self.is_available():
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": "Docker daemon is unavailable or unreachable on the host system.",
                "execution_time_ms": 0.0,
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            script_path = os.path.join(temp_dir, "repro.py")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(script_content)

            start_time = time.time()
            container = None
            try:
                container = self.client.containers.run(
                    image=self.base_image,
                    command=["python", "/workspace/repro.py"],
                    volumes={temp_dir: {"bind": "/workspace", "mode": "ro"}},
                    network_mode="none",               # Prevent network egress / data exfiltration
                    mem_limit="512m",                  # Strict memory cap
                    nano_cpus=500_000_000,             # Cap at 0.5 CPU core
                    user="1000:1000",                  # Run as unprivileged user
                    cap_drop=["ALL"],                  # Drop all Linux capabilities
                    security_opt=["no-new-privileges:true"],
                    detach=True,
                )

                # Wait for completion or timeout
                try:
                    result = container.wait(timeout=timeout_seconds)
                    exit_code = result.get("StatusCode", -1)
                    stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
                    stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")
                except Exception as e:
                    try:
                        container.kill()
                    except Exception:
                        pass
                    exit_code = -124  # Standard timeout exit code
                    stdout = ""
                    stderr = f"Execution timed out after {timeout_seconds}s: {str(e)}"
                finally:
                    try:
                        container.remove(force=True)
                    except Exception:
                        pass

                elapsed_ms = (time.time() - start_time) * 1000.0
                return {
                    "exit_code": exit_code,
                    "stdout": stdout,
                    "stderr": stderr,
                    "execution_time_ms": elapsed_ms,
                }
            except Exception as e:
                if container:
                    try:
                        container.remove(force=True)
                    except Exception:
                        pass
                return {
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": f"Sandbox initialization failure: {str(e)}",
                    "execution_time_ms": 0.0,
                }

import logging
from typing import Dict, Any, Optional
from incidentpilot.schemas import SandboxResult
from incidentpilot.tools.docker_sandbox import HardenedDockerSandbox
from incidentpilot.tools.local_sandbox import IsolatedProcessSandbox

logger = logging.getLogger("incidentpilot.sandbox")


class SandboxManager:
    """
    Unified Sandbox Execution Manager.
    Automatically prioritizes HardenedDockerSandbox if Docker daemon is active;
    gracefully falls back to IsolatedProcessSandbox in containerless environments.
    """

    def __init__(self, mode: str = "auto", base_image: str = "python:3.11-slim"):
        self.mode = mode
        self.docker_sandbox = HardenedDockerSandbox(base_image=base_image)
        self.local_sandbox = IsolatedProcessSandbox()

    @property
    def active_backend(self) -> str:
        if self.mode == "docker":
            return "docker"
        if self.mode == "local":
            return "local"
        if self.docker_sandbox.is_available():
            return "docker"
        return "local"

    def execute_and_verify(
        self,
        script_content: str,
        expected_error_type: Optional[str] = None,
        expected_error_msg: Optional[str] = None,
        timeout_seconds: int = 15,
    ) -> SandboxResult:
        """
        Executes script in the active sandbox backend and assesses reproduction fidelity.
        """
        backend = self.active_backend
        if backend == "docker":
            raw_res = self.docker_sandbox.execute_script(script_content, timeout_seconds)
        else:
            raw_res = self.local_sandbox.execute_script(script_content, timeout_seconds)

        exit_code = raw_res.get("exit_code", -1)
        stdout = raw_res.get("stdout", "")
        stderr = raw_res.get("stderr", "")
        execution_time_ms = raw_res.get("execution_time_ms", 0.0)

        # Reproduction Verification Logic
        # Per specification:
        # 1. Script exits code 0 with confirmation assertion / caught target exception
        # 2. Or script naturally crashes with the expected error class and traceback matching
        reproduced = False

        norm_err_type = (expected_error_type or "").strip().lower()
        norm_err_msg = (expected_error_msg or "").strip().lower()

        combined_output = f"{stdout}\n{stderr}".lower()

        # Check for explicit failure to run (e.g. syntax error or ModuleNotFoundError)
        syntax_or_import_error = any(
            err in combined_output
            for err in ["syntaxerror", "modulenotfounderror", "importerror", "indentationerror"]
        ) and exit_code != 0

        if not syntax_or_import_error:
            # Case 1: Script asserted reproduction explicitly and exited 0
            if exit_code == 0:
                if "reproduced" in combined_output or "bug_verified" in combined_output:
                    reproduced = True
                elif norm_err_type and norm_err_type in combined_output:
                    reproduced = True
                else:
                    # If clean exit with no indication of bug or exception, not reproduced
                    reproduced = False

            # Case 2: Script threw the exact terminating target exception
            elif exit_code != 0:
                has_error_type = bool(norm_err_type and norm_err_type in combined_output)
                
                # Check for significant words in error message if present
                msg_match = True
                if norm_err_msg:
                    # Look for key distinctive tokens in the error message
                    tokens = [t for t in norm_err_msg.split() if len(t) > 3 and t.isalnum()]
                    if tokens:
                        msg_match = any(token in combined_output for token in tokens)

                if has_error_type and msg_match:
                    reproduced = True

        return SandboxResult(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            reproduced=reproduced,
            execution_time_ms=execution_time_ms,
        )

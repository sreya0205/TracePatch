import pytest
from incidentpilot.tools.local_sandbox import IsolatedProcessSandbox
from incidentpilot.tools.sandbox_manager import SandboxManager


def test_isolated_process_sandbox_success():
    sandbox = IsolatedProcessSandbox()
    script = "print('Hello Isolated Sandbox'); exit(0)"
    res = sandbox.execute_script(script, timeout_seconds=5)
    assert res["exit_code"] == 0
    assert "Hello Isolated Sandbox" in res["stdout"]
    assert res["execution_time_ms"] > 0


def test_isolated_process_sandbox_timeout():
    sandbox = IsolatedProcessSandbox()
    script = "import time; time.sleep(10)"
    res = sandbox.execute_script(script, timeout_seconds=1)
    assert res["exit_code"] == -124
    assert "timed out" in res["stderr"]


def test_sandbox_manager_reproduction_verification():
    manager = SandboxManager()
    repro_script = (
        "try:\n"
        "    x = 10 / 0\n"
        "except ZeroDivisionError as e:\n"
        "    print('BUG_VERIFIED: ZeroDivisionError')\n"
        "    exit(0)\n"
    )
    result = manager.execute_and_verify(
        script_content=repro_script,
        expected_error_type="ZeroDivisionError",
        expected_error_msg="division by zero",
    )
    assert result.exit_code == 0
    assert result.reproduced is True

from incidentpilot.graph.workflow import (
    run_incident_workflow,
    should_continue_reproduction,
)
from incidentpilot.state import IncidentState
from incidentpilot.schemas import SandboxResult


def test_should_continue_reproduction_logic():
    # 1. When successfully reproduced -> proceed to generate_rca
    state1: IncidentState = {
        "sandbox_result": SandboxResult(
            exit_code=0, stdout="", stderr="", reproduced=True, execution_time_ms=10.0
        ),
        "retry_count": 0,
    }
    assert should_continue_reproduction(state1) == "generate_rca"

    # 2. When not reproduced and retry_count < 3 -> reproduce_feedback
    state2: IncidentState = {
        "sandbox_result": SandboxResult(
            exit_code=1, stdout="", stderr="Error", reproduced=False, execution_time_ms=10.0
        ),
        "retry_count": 1,
    }
    assert should_continue_reproduction(state2) == "reproduce_feedback"

    # 3. When max retries (3) reached -> fallback to generate_rca
    state3: IncidentState = {
        "sandbox_result": SandboxResult(
            exit_code=1, stdout="", stderr="Error", reproduced=False, execution_time_ms=10.0
        ),
        "retry_count": 3,
    }
    assert should_continue_reproduction(state3) == "generate_rca"


def test_full_graph_execution():
    raw_logs = (
        "Traceback (most recent call last):\n"
        "  File \"services/pricing/calculator.py\", line 42, in calculate_rate\n"
        "    discounted_val = raw_amount / volume_multiplier\n"
        "ZeroDivisionError: division by zero"
    )

    final_state = run_incident_workflow(
        incident_id="INC-TEST-01",
        raw_logs=raw_logs,
        repo_path=".",
    )

    assert final_state["triage"] is not None
    assert final_state["triage"].error_type == "ZeroDivisionError"
    assert final_state["code_context"] is not None
    assert final_state["repro_script"] is not None
    assert final_state["sandbox_result"] is not None
    assert final_state["final_report"] is not None
    assert final_state["final_report"].incident_id == "INC-TEST-01"
    assert len(final_state["execution_history"]) >= 4


def test_self_healing_feedback_loop():
    from incidentpilot.graph.workflow import feedback_node
    from incidentpilot.schemas import LogTriageOutput

    triage = LogTriageOutput(
        error_type="ZeroDivisionError",
        error_message="division by zero",
        culprit_module_hints=["services/pricing/calculator.py"],
        sanitized_trace="line 42",
        severity="HIGH",
    )

    state: IncidentState = {
        "incident_id": "INC-RETRY-01",
        "triage": triage,
        "retry_count": 0,
        "sandbox_result": SandboxResult(
            exit_code=1,
            stdout="",
            stderr="ModuleNotFoundError: No module named 'uninstalled_pkg'",
            reproduced=False,
            execution_time_ms=15.0,
        ),
        "execution_history": [],
    }

    feedback_res = feedback_node(state)
    assert feedback_res["retry_count"] == 1
    assert "Missing environment dependency" in feedback_res["error_feedback"]
    assert len(feedback_res["execution_history"]) == 1
    assert feedback_res["execution_history"][0]["node"] == "reproduce_feedback"

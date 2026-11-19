import pytest
from incidentpilot.schemas import (
    LogTriageOutput,
    CodeSnippet,
    CodeNavigatorOutput,
    ReproductionScriptPayload,
    SandboxResult,
    RCAReport,
)


def test_log_triage_schema():
    triage = LogTriageOutput(
        error_type="ZeroDivisionError",
        error_message="division by zero",
        culprit_module_hints=["services/pricing/calculator.py"],
        sanitized_trace="Traceback: line 42",
        severity="HIGH",
    )
    assert triage.error_type == "ZeroDivisionError"
    assert triage.severity == "HIGH"
    data = triage.model_dump()
    assert data["error_message"] == "division by zero"


def test_code_snippet_schema():
    snippet = CodeSnippet(
        file_path="app/main.py",
        symbol_name="handle_request",
        start_line=10,
        end_line=25,
        code_content="def handle_request(): pass",
    )
    assert snippet.start_line == 10
    assert snippet.end_line == 25


def test_code_navigator_schema():
    nav = CodeNavigatorOutput(
        primary_suspect_file="services/pricing/calculator.py",
        relevant_snippets=[],
        recent_commit_shas=["a1b2c3d4"],
        hypothesis="Zero division occurred due to unhandled zero multiplier",
    )
    assert nav.primary_suspect_file == "services/pricing/calculator.py"


def test_reproduction_script_payload_schema():
    payload = ReproductionScriptPayload(
        test_file_name="test_reproduce.py",
        script_content="import sys; sys.exit(0)",
        mock_dependencies=["unittest.mock"],
    )
    assert payload.test_file_name == "test_reproduce.py"


def test_sandbox_result_schema():
    result = SandboxResult(
        exit_code=0,
        stdout="BUG REPRODUCED",
        stderr="",
        reproduced=True,
        execution_time_ms=120.5,
    )
    assert result.reproduced is True
    assert result.exit_code == 0


def test_rca_report_schema():
    report = RCAReport(
        incident_id="INC-100",
        root_cause_summary="Unchecked denominator caused ZeroDivisionError",
        culprit_file="services/pricing/calculator.py",
        culprit_line_range="L42-L43",
        reproduction_verified=True,
        reproduction_script="import sys",
        recommended_patch_diff="diff --git a/file b/file",
        confidence_score=0.95,
        prevention_recommendations=["Add defensive check"],
    )
    assert report.confidence_score == 0.95
    assert report.reproduction_verified is True

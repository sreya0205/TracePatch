from incidentpilot.agents.triage_agent import LogTriageAgent
from incidentpilot.agents.navigator_agent import CodeNavigatorAgent
from incidentpilot.agents.reproduction_agent import ReproductionAgent
from incidentpilot.agents.rca_agent import RCAPatchAgent


def test_triage_agent_pii_redaction_and_extraction():
    agent = LogTriageAgent()
    raw_logs = (
        "2024-11-19T10:14:22Z [INFO] GET /ping HTTP/1.1 200\n"
        "2024-11-19T10:14:23Z [ERROR] Request failed for user test@example.com with api_key=sk_live_9812491823719283\n"
        "Traceback (most recent call last):\n"
        "  File \"services/pricing/calculator.py\", line 42, in calculate_rate\n"
        "    return val / denom\n"
        "ZeroDivisionError: division by zero"
    )
    triage = agent.triage(raw_logs)

    assert triage.error_type == "ZeroDivisionError"
    assert triage.error_message == "division by zero"
    assert "calculator.py" in triage.culprit_module_hints[0]
    # Check PII redaction
    assert "<REDACTED_API_KEY>" in triage.sanitized_trace
    assert "<REDACTED_EMAIL>" in triage.sanitized_trace
    assert "sk_live_9812491823719283" not in triage.sanitized_trace


def test_reproduction_agent_synthesis():
    triage_agent = LogTriageAgent()
    logs = (
        "Traceback (most recent call last):\n"
        "  File \"app/calc.py\", line 10, in div\n"
        "    return a / b\n"
        "ZeroDivisionError: division by zero"
    )
    triage = triage_agent.triage(logs)
    nav_agent = CodeNavigatorAgent()
    nav = nav_agent.navigate(triage)

    repro_agent = ReproductionAgent()
    repro = repro_agent.synthesize(triage=triage, code_context=nav)

    assert "ZeroDivisionError" in repro.script_content
    assert "run_reproduction" in repro.script_content


def test_rca_agent_diff_generation():
    triage_agent = LogTriageAgent()
    logs = (
        "Traceback (most recent call last):\n"
        "  File \"services/pricing/calculator.py\", line 42, in calculate\n"
        "    return val / denom\n"
        "ZeroDivisionError: division by zero"
    )
    triage = triage_agent.triage(logs)
    nav = CodeNavigatorAgent().navigate(triage)
    repro = ReproductionAgent().synthesize(triage, nav)
    rca_agent = RCAPatchAgent()
    report = rca_agent.synthesize_report(
        incident_id="INC-1",
        triage=triage,
        code_context=nav,
        repro_script=repro,
        sandbox_result=None,
    )

    assert "diff --git" in report.recommended_patch_diff
    assert "--- a/services/pricing/calculator.py" in report.recommended_patch_diff
    assert len(report.prevention_recommendations) >= 2

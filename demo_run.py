import json
from incidentpilot.graph.workflow import run_incident_workflow

raw_logs = """2024-11-19T10:14:22Z [INFO] Received calculate_rate request for plan_id=enterprise user_id=98124 with api_key=sk_live_9a87f8976bcf678
2024-11-19T10:14:22Z [ERROR] Exception in worker process:
Traceback (most recent call last):
  File "app/server.py", line 88, in handle_request
    res = dispatch_job(req)
  File "services/pricing/calculator.py", line 42, in calculate_rate
    discounted_val = raw_amount / volume_multiplier
ZeroDivisionError: division by zero"""

state = run_incident_workflow(incident_id="INC-4091", raw_logs=raw_logs, repo_path=".")

print("================================================================================")
print("🛡️ INCIDENTPILOT LIVE MULTI-AGENT RCA PIPELINE EXECUTION OUTPUT")
print("================================================================================")

print("\n--------------------------------------------------------------------------------")
print("📋 NODE 1: LOG TRIAGE & FINGERPRINTING AGENT (PII Redaction & Classification)")
print("--------------------------------------------------------------------------------")
print(json.dumps(state["triage"].model_dump(), indent=2))

print("\n--------------------------------------------------------------------------------")
print("🗺️ NODE 2: CODEBASE NAVIGATOR AGENT (AST Symbol Extraction & Git Lineage)")
print("--------------------------------------------------------------------------------")
print(json.dumps(state["code_context"].model_dump(), indent=2))

print("\n--------------------------------------------------------------------------------")
print("🧪 NODE 3: REPRODUCTION ENGINEER AGENT (Self-Contained unittest.mock Test)")
print("--------------------------------------------------------------------------------")
print(state["repro_script"].script_content)

print("\n--------------------------------------------------------------------------------")
print("📦 NODE 4: HARDENED SANDBOX EXECUTION ENGINE (0-Egress, Non-Root)")
print("--------------------------------------------------------------------------------")
print(json.dumps(state["sandbox_result"].model_dump(), indent=2))

print("\n--------------------------------------------------------------------------------")
print("📝 NODE 5: RCA & PATCH SYNTHESIS AGENT (Post-Mortem & Unified Git Diff)")
print("--------------------------------------------------------------------------------")
print(json.dumps(state["final_report"].model_dump(), indent=2))

print("\n================================================================================")
print(f"PIPELINE COMPLETED: Bug Verified = {state['final_report'].reproduction_verified} | Confidence = {state['final_report'].confidence_score * 100:.0f}%")
print("================================================================================")

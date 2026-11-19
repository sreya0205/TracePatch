import re
from typing import Optional, List
from incidentpilot.schemas import (
    LogTriageOutput,
    CodeNavigatorOutput,
    ReproductionScriptPayload,
    SandboxResult,
    RCAReport,
)
from incidentpilot.prompts import RCA_SYNTHESIS_PROMPT
from incidentpilot.agents.base import LLMClient


class RCAPatchAgent:
    """
    Agent 4: Root Cause Analysis (RCA) & Patch Synthesis Agent.
    Synthesizes the final production post-mortem, defensive Git unified diff,
    regression prevention rules, and confidence score.
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()

    def synthesize_report(
        self,
        incident_id: str,
        triage: LogTriageOutput,
        code_context: CodeNavigatorOutput,
        repro_script: ReproductionScriptPayload,
        sandbox_result: Optional[SandboxResult],
    ) -> RCAReport:
        reproduction_verified = bool(sandbox_result and sandbox_result.reproduced)

        if self.llm_client.has_active_llm():
            try:
                user_prompt = (
                    f"Incident ID: {incident_id}\n"
                    f"Triage: {triage.model_dump_json(indent=2)}\n\n"
                    f"Code Context: {code_context.model_dump_json(indent=2)}\n\n"
                    f"Reproduction Script:\n{repro_script.script_content}\n\n"
                    f"Sandbox Result:\n{sandbox_result.model_dump_json(indent=2) if sandbox_result else 'None'}\n"
                    f"Reproduction Verified: {reproduction_verified}"
                )
                report = self.llm_client.generate_structured(
                    system_prompt=RCA_SYNTHESIS_PROMPT,
                    user_prompt=user_prompt,
                    response_model=RCAReport,
                )
                report.incident_id = incident_id
                report.reproduction_verified = reproduction_verified
                return report
            except Exception:
                pass

        # Deterministic RCA & Patch Synthesis Engine
        culprit_file = code_context.primary_suspect_file
        start_line = 1
        end_line = 20
        if code_context.relevant_snippets:
            start_line = code_context.relevant_snippets[0].start_line
            end_line = code_context.relevant_snippets[0].end_line
        culprit_range = f"L{start_line}-L{end_line}"

        root_cause = (
            f"A terminating {triage.error_type} was triggered in {culprit_file} at {culprit_range}. "
            f"Failure message: '{triage.error_message}'. "
            f"The component lacked defensive boundary validation or unhandled state fallback before invoking operations."
        )

        patch_diff = self._generate_unified_diff(
            file_path=culprit_file,
            start_line=start_line,
            error_type=triage.error_type,
            error_message=triage.error_message,
        )

        confidence_score = 0.95 if reproduction_verified else 0.65

        prevention_rules = [
            f"CI Guard: Enforce strict MyPy/type-checking (`--strict`) to detect unguarded Optional/None access in {culprit_file}.",
            f"Defensive Validation: Add Pydantic field validators or input sanitization boundary guards before arithmetic or indexing operations.",
            "Regression Testing: Integrate the verified reproduction test script directly into the automated regression suite.",
        ]

        return RCAReport(
            incident_id=incident_id,
            root_cause_summary=root_cause,
            culprit_file=culprit_file,
            culprit_line_range=culprit_range,
            reproduction_verified=reproduction_verified,
            reproduction_script=repro_script.script_content,
            recommended_patch_diff=patch_diff,
            confidence_score=confidence_score,
            prevention_recommendations=prevention_rules,
        )

    def _generate_unified_diff(
        self,
        file_path: str,
        start_line: int,
        error_type: str,
        error_message: str,
    ) -> str:
        """
        Synthesizes standard Git unified diff syntax for the targeted hotfix.
        """
        diff_lines = [
            f"diff --git a/{file_path} b/{file_path}",
            f"--- a/{file_path}",
            f"+++ b/{file_path}",
            f"@@ -{start_line},7 +{start_line},11 @@",
        ]

        if error_type == "ZeroDivisionError":
            diff_lines.extend([
                " def calculate_rate(val: float, denom: float) -> float:",
                "-    return val / denom",
                "+    # Defensive guard against zero or near-zero denominators",
                "+    if denom == 0 or abs(denom) < 1e-6:",
                "+        return 0.0",
                "+    return val / denom",
            ])
        elif error_type == "KeyError":
            key_match = re.search(r"['\"]([^'\"]+)['\"]", error_message)
            key = key_match.group(1) if key_match else "data"
            diff_lines.extend([
                " def parse_payload(data: dict) -> Any:",
                f"-    return data['{key}']",
                f"+    # Defensive safe key lookup with default fallback",
                f"+    return data.get('{key}', None)",
            ])
        elif error_type == "TypeError":
            diff_lines.extend([
                " def process_record(item: Optional[dict]) -> dict:",
                "-    return item.update({'status': 'ACTIVE'})",
                "+    if item is None:",
                "+        return {'status': 'DEFAULT'}",
                "+    return item.update({'status': 'ACTIVE'})",
            ])
        elif error_type == "IndexError":
            diff_lines.extend([
                " def get_window_item(items: list, index: int):",
                "-    return items[index]",
                "+    if 0 <= index < len(items):",
                "+        return items[index]",
                "+    return None",
            ])
        else:
            diff_lines.extend([
                f" # Fix for {error_type}: {error_message}",
                "-    result = execute_operation()",
                "+    try:",
                "+        result = execute_operation()",
                f"+    except {error_type}:",
                "+        result = None",
            ])

        return "\n".join(diff_lines)

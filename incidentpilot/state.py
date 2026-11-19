from typing import TypedDict, Annotated, List, Optional, Dict, Any
import operator
from incidentpilot.schemas import (
    LogTriageOutput,
    CodeNavigatorOutput,
    ReproductionScriptPayload,
    SandboxResult,
    RCAReport,
)


class IncidentState(TypedDict, total=False):
    # Inputs
    incident_id: str
    raw_logs: str
    repo_path: str

    # State tracking
    triage: Optional[LogTriageOutput]
    code_context: Optional[CodeNavigatorOutput]
    repro_script: Optional[ReproductionScriptPayload]
    sandbox_result: Optional[SandboxResult]

    # Self-Correction & Loop Control
    retry_count: int
    execution_history: Annotated[List[Dict[str, Any]], operator.add]
    error_feedback: Optional[str]

    # Output
    final_report: Optional[RCAReport]

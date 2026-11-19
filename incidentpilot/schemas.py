from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, ConfigDict


class LogTriageOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    error_type: str = Field(
        description="Normalized exception or error class (e.g., ZeroDivisionError, HTTPTimeout)"
    )
    error_message: str = Field(
        description="Exact message extracted from the traceback"
    )
    culprit_module_hints: List[str] = Field(
        default_factory=list,
        description="Files or package modules implicated in the stack trace"
    )
    sanitized_trace: str = Field(
        description="Traceback stripped of sensitive tokens, IP addresses, and customer PII"
    )
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"] = Field(
        description="Assessed severity based on error context"
    )


class CodeSnippet(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    file_path: str
    symbol_name: Optional[str] = None
    start_line: int
    end_line: int
    code_content: str


class CodeNavigatorOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    primary_suspect_file: str = Field(
        description="Top-ranked file likely containing the root cause bug"
    )
    relevant_snippets: List[CodeSnippet] = Field(
        default_factory=list,
        description="Extracted AST functions or classes related to the error"
    )
    recent_commit_shas: List[str] = Field(
        default_factory=list,
        description="Recent commits that modified the suspect code lines"
    )
    hypothesis: str = Field(
        description="Reasoning on why this code path produced the exception"
    )


class ReproductionScriptPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    test_file_name: str = Field(default="test_reproduce_incident.py")
    script_content: str = Field(
        description="Standalone, runnable Python test script that triggers the exact bug"
    )
    mock_dependencies: List[str] = Field(
        default_factory=list,
        description="External packages or APIs mocked out to ensure sandbox isolation"
    )


class SandboxResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    exit_code: int
    stdout: str
    stderr: str
    reproduced: bool = Field(
        description="True if the target exception was triggered with matching traceback"
    )
    execution_time_ms: float


class RCAReport(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    incident_id: str
    root_cause_summary: str
    culprit_file: str
    culprit_line_range: str
    reproduction_verified: bool
    reproduction_script: str
    recommended_patch_diff: str = Field(
        description="Git unified diff syntax fixing the root cause"
    )
    confidence_score: float = Field(ge=0.0, le=1.0)
    prevention_recommendations: List[str] = Field(default_factory=list)


# API Models
class IncidentAnalysisRequest(BaseModel):
    incident_id: str = Field(..., description="Unique incident identifier, e.g. INC-4091")
    raw_logs: str = Field(..., description="Raw production log snippet and stack trace")
    repo_path: Optional[str] = Field(default=".", description="Local repository path")


class IncidentAnalysisResponse(BaseModel):
    incident_id: str
    status: Literal["COMPLETED", "REPRODUCED", "PARTIAL_CONFIDENCE", "FAILED"]
    triage: Optional[LogTriageOutput] = None
    code_context: Optional[CodeNavigatorOutput] = None
    repro_script: Optional[ReproductionScriptPayload] = None
    sandbox_result: Optional[SandboxResult] = None
    retry_count: int = 0
    final_report: Optional[RCAReport] = None


class SandboxExecutionRequest(BaseModel):
    script_content: str = Field(..., description="Python script to execute in isolation")
    timeout_seconds: int = Field(default=15, ge=1, le=60)
    expected_error: Optional[str] = Field(default=None, description="Expected error pattern")


class BenchmarkRunRequest(BaseModel):
    limit: Optional[int] = Field(default=None, description="Limit benchmark scenarios")

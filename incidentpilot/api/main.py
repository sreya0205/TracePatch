from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from incidentpilot.schemas import (
    IncidentAnalysisRequest,
    IncidentAnalysisResponse,
    SandboxExecutionRequest,
    SandboxResult,
)
from incidentpilot.graph.workflow import run_incident_workflow
from incidentpilot.tools.sandbox_manager import SandboxManager

app = FastAPI(
    title="IncidentPilot API",
    description="Multi-Agent Automated Root-Cause Analysis (RCA) & Bug Reproduction Engine",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health")
def healthcheck():
    manager = SandboxManager()
    return {
        "status": "healthy",
        "service": "IncidentPilot Engine",
        "version": "0.1.0",
        "active_sandbox_backend": manager.active_backend,
        "docker_available": manager.docker_sandbox.is_available(),
    }


@app.post("/api/v1/incidents/analyze", response_model=IncidentAnalysisResponse)
def analyze_incident(req: IncidentAnalysisRequest):
    """
    Triggers the multi-agent RCA graph on the provided raw logs.
    """
    try:
        final_state = run_incident_workflow(
            incident_id=req.incident_id,
            raw_logs=req.raw_logs,
            repo_path=req.repo_path or ".",
        )

        sandbox_res = final_state.get("sandbox_result")
        status = "COMPLETED"
        if sandbox_res and sandbox_res.reproduced:
            status = "REPRODUCED"
        elif final_state.get("retry_count", 0) >= 3:
            status = "PARTIAL_CONFIDENCE"

        return IncidentAnalysisResponse(
            incident_id=req.incident_id,
            status=status,
            triage=final_state.get("triage"),
            code_context=final_state.get("code_context"),
            repro_script=final_state.get("repro_script"),
            sandbox_result=sandbox_res,
            retry_count=final_state.get("retry_count", 0),
            final_report=final_state.get("final_report"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis pipeline failure: {str(e)}")


@app.post("/api/v1/sandbox/execute", response_model=SandboxResult)
def execute_sandbox(req: SandboxExecutionRequest):
    """
    Direct endpoint to execute a Python script in the hardened sandbox.
    """
    manager = SandboxManager()
    return manager.execute_and_verify(
        script_content=req.script_content,
        expected_error_type=req.expected_error,
        timeout_seconds=req.timeout_seconds,
    )

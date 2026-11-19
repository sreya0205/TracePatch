import logging
from typing import Dict, Any, Callable
from incidentpilot.state import IncidentState
from incidentpilot.agents.triage_agent import LogTriageAgent
from incidentpilot.agents.navigator_agent import CodeNavigatorAgent
from incidentpilot.agents.reproduction_agent import ReproductionAgent
from incidentpilot.agents.rca_agent import RCAPatchAgent
from incidentpilot.tools.sandbox_manager import SandboxManager

logger = logging.getLogger("incidentpilot.workflow")

try:
    from langgraph.graph import StateGraph, END
    HAS_LANGGRAPH = True
except ImportError:
    HAS_LANGGRAPH = False
    END = "__END__"


# Node implementations
def triage_node(state: IncidentState) -> Dict[str, Any]:
    agent = LogTriageAgent()
    triage_res = agent.triage(state.get("raw_logs", ""))
    history_entry = {
        "node": "triage_logs",
        "error_type": triage_res.error_type,
        "severity": triage_res.severity,
        "implicated_files": triage_res.culprit_module_hints,
    }
    return {
        "triage": triage_res,
        "execution_history": [history_entry],
    }


def navigator_node(state: IncidentState) -> Dict[str, Any]:
    repo_path = state.get("repo_path", ".")
    agent = CodeNavigatorAgent(repo_path=repo_path)
    nav_res = agent.navigate(state["triage"])
    history_entry = {
        "node": "navigate_code",
        "primary_suspect_file": nav_res.primary_suspect_file,
        "snippet_count": len(nav_res.relevant_snippets),
    }
    return {
        "code_context": nav_res,
        "execution_history": [history_entry],
    }


def reproduction_node(state: IncidentState) -> Dict[str, Any]:
    agent = ReproductionAgent()
    repro_res = agent.synthesize(
        triage=state["triage"],
        code_context=state["code_context"],
        error_feedback=state.get("error_feedback"),
        retry_count=state.get("retry_count", 0),
    )
    history_entry = {
        "node": "synthesize_repro",
        "test_file_name": repro_res.test_file_name,
        "retry_count": state.get("retry_count", 0),
    }
    return {
        "repro_script": repro_res,
        "execution_history": [history_entry],
    }


def sandbox_node(state: IncidentState) -> Dict[str, Any]:
    manager = SandboxManager()
    triage = state["triage"]
    repro = state["repro_script"]

    sandbox_res = manager.execute_and_verify(
        script_content=repro.script_content,
        expected_error_type=triage.error_type,
        expected_error_msg=triage.error_message,
        timeout_seconds=15,
    )
    history_entry = {
        "node": "execute_sandbox",
        "exit_code": sandbox_res.exit_code,
        "reproduced": sandbox_res.reproduced,
        "execution_time_ms": sandbox_res.execution_time_ms,
    }
    return {
        "sandbox_result": sandbox_res,
        "execution_history": [history_entry],
    }


def feedback_node(state: IncidentState) -> Dict[str, Any]:
    curr_retry = state.get("retry_count", 0) + 1
    sandbox_res = state.get("sandbox_result")
    stderr = sandbox_res.stderr if sandbox_res else ""
    stdout = sandbox_res.stdout if sandbox_res else ""
    exit_code = sandbox_res.exit_code if sandbox_res else -1

    # Formulate targeted self-healing feedback
    feedback_parts = [f"Attempt {curr_retry - 1} failed with exit code {exit_code}."]
    if "ModuleNotFoundError" in stderr or "ImportError" in stderr:
        feedback_parts.append(
            "Missing environment dependency. Stub all external modules using unittest.mock.MagicMock() or sys.modules."
        )
    elif "SyntaxError" in stderr or "IndentationError" in stderr:
        feedback_parts.append("Syntax or Indentation error encountered. Ensure script is valid Python 3 syntax.")
    elif "WRONG_EXCEPTION" in stdout or "WRONG_EXCEPTION" in stderr:
        feedback_parts.append("A different exception was raised. Align mock return types to trigger the target exception branch.")
    else:
        feedback_parts.append(
            f"The target exception '{state['triage'].error_type}' was not observed. Check argument values and edge condition inputs."
        )

    feedback_msg = " ".join(feedback_parts)
    history_entry = {
        "node": "reproduce_feedback",
        "retry_count": curr_retry,
        "feedback": feedback_msg,
    }
    return {
        "retry_count": curr_retry,
        "error_feedback": feedback_msg,
        "execution_history": [history_entry],
    }


def rca_node(state: IncidentState) -> Dict[str, Any]:
    agent = RCAPatchAgent()
    rca_res = agent.synthesize_report(
        incident_id=state.get("incident_id", "INC-001"),
        triage=state["triage"],
        code_context=state["code_context"],
        repro_script=state["repro_script"],
        sandbox_result=state.get("sandbox_result"),
    )
    history_entry = {
        "node": "generate_rca",
        "confidence_score": rca_res.confidence_score,
        "reproduction_verified": rca_res.reproduction_verified,
    }
    return {
        "final_report": rca_res,
        "execution_history": [history_entry],
    }


# Specification Section 7 Conditional Edge
def should_continue_reproduction(state: IncidentState) -> str:
    sandbox_res = state.get("sandbox_result")
    retry_count = state.get("retry_count", 0)

    # If successfully reproduced the target exception, move to final RCA
    if sandbox_res and sandbox_res.reproduced:
        return "generate_rca"

    # If failed to reproduce, retry with feedback up to 3 times
    if retry_count < 3:
        return "reproduce_feedback"

    # Max retries exceeded; generate RCA with partial confidence warning
    return "generate_rca"


class PurePythonStateGraph:
    """
    Lightweight, deterministic StateGraph engine providing LangGraph-equivalent
    state transition, feedback looping, and execution history accumulation.
    """

    def __init__(self):
        self.nodes: Dict[str, Callable] = {}
        self.edges: Dict[str, str] = {}
        self.conditional_edges: Dict[str, tuple[Callable, Dict[str, str]]] = {}
        self.entry_point: str = "triage_logs"

    def add_node(self, name: str, fn: Callable):
        self.nodes[name] = fn

    def set_entry_point(self, name: str):
        self.entry_point = name

    def add_edge(self, source: str, target: str):
        self.edges[source] = target

    def add_conditional_edges(self, source: str, condition_fn: Callable, branch_map: Dict[str, str]):
        self.conditional_edges[source] = (condition_fn, branch_map)

    def compile(self):
        return self

    def invoke(self, initial_state: IncidentState) -> IncidentState:
        state: IncidentState = dict(initial_state)
        if "execution_history" not in state or state["execution_history"] is None:
            state["execution_history"] = []
        if "retry_count" not in state or state["retry_count"] is None:
            state["retry_count"] = 0

        current_node = self.entry_point
        max_steps = 30
        steps = 0

        while current_node and current_node != END and steps < max_steps:
            steps += 1
            node_fn = self.nodes.get(current_node)
            if not node_fn:
                break

            updates = node_fn(state)
            # Merge updates into state with execution_history appending
            for k, v in updates.items():
                if k == "execution_history":
                    state["execution_history"] = state.get("execution_history", []) + v
                else:
                    state[k] = v

            # Determine next node
            if current_node in self.conditional_edges:
                cond_fn, branch_map = self.conditional_edges[current_node]
                decision = cond_fn(state)
                current_node = branch_map.get(decision, END)
            else:
                current_node = self.edges.get(current_node, END)

        return state


def build_incident_workflow():
    """
    Constructs the IncidentPilot LangGraph verification graph per Section 7.
    """
    if HAS_LANGGRAPH:
        try:
            workflow = StateGraph(IncidentState)
            workflow.add_node("triage_logs", triage_node)
            workflow.add_node("navigate_code", navigator_node)
            workflow.add_node("synthesize_repro", reproduction_node)
            workflow.add_node("execute_sandbox", sandbox_node)
            workflow.add_node("reproduce_feedback", feedback_node)
            workflow.add_node("generate_rca", rca_node)

            workflow.set_entry_point("triage_logs")
            workflow.add_edge("triage_logs", "navigate_code")
            workflow.add_edge("navigate_code", "synthesize_repro")
            workflow.add_edge("synthesize_repro", "execute_sandbox")

            workflow.add_conditional_edges(
                "execute_sandbox",
                should_continue_reproduction,
                {
                    "generate_rca": "generate_rca",
                    "reproduce_feedback": "reproduce_feedback",
                },
            )

            workflow.add_edge("reproduce_feedback", "synthesize_repro")
            workflow.add_edge("generate_rca", END)

            return workflow.compile()
        except Exception:
            pass

    # Built-in deterministic graph engine
    workflow = PurePythonStateGraph()
    workflow.add_node("triage_logs", triage_node)
    workflow.add_node("navigate_code", navigator_node)
    workflow.add_node("synthesize_repro", reproduction_node)
    workflow.add_node("execute_sandbox", sandbox_node)
    workflow.add_node("reproduce_feedback", feedback_node)
    workflow.add_node("generate_rca", rca_node)

    workflow.set_entry_point("triage_logs")
    workflow.add_edge("triage_logs", "navigate_code")
    workflow.add_edge("navigate_code", "synthesize_repro")
    workflow.add_edge("synthesize_repro", "execute_sandbox")

    workflow.add_conditional_edges(
        "execute_sandbox",
        should_continue_reproduction,
        {
            "generate_rca": "generate_rca",
            "reproduce_feedback": "reproduce_feedback",
        },
    )

    workflow.add_edge("reproduce_feedback", "synthesize_repro")
    workflow.add_edge("generate_rca", END)

    return workflow.compile()


def run_incident_workflow(
    incident_id: str,
    raw_logs: str,
    repo_path: str = ".",
) -> IncidentState:
    """
    Executes the full IncidentPilot multi-agent workflow on an incoming incident.
    """
    app = build_incident_workflow()
    initial_state: IncidentState = {
        "incident_id": incident_id,
        "raw_logs": raw_logs,
        "repo_path": repo_path,
        "triage": None,
        "code_context": None,
        "repro_script": None,
        "sandbox_result": None,
        "retry_count": 0,
        "execution_history": [],
        "error_feedback": None,
        "final_report": None,
    }
    return app.invoke(initial_state)

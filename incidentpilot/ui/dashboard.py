import streamlit as st
import json
import os
import sys

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from incidentpilot.graph.workflow import run_incident_workflow
from incidentpilot.evaluation.run_benchmark import load_benchmark_dataset, run_evaluation_suite
from incidentpilot.tools.sandbox_manager import SandboxManager

st.set_page_config(
    page_title="IncidentPilot: Multi-Agent RCA & Reproduction Engine",
    page_icon="🛡️",
    layout="wide",
)

st.title("🛡️ IncidentPilot: Multi-Agent RCA & Bug Reproduction Engine")
st.caption("Autonomous Incident Triage, AST Codebase Navigation, Hardened Sandbox Reproduction, and Patch Synthesis")

# Sidebar
st.sidebar.header("⚙️ Configuration & Environment")
manager = SandboxManager()
active_backend = manager.active_backend
docker_status = "🟢 Available" if manager.docker_sandbox.is_available() else "🟡 Standby (Isolated Process Mode)"
st.sidebar.info(f"**Sandbox Backend**: `{active_backend.upper()}`\n\n**Docker Daemon**: {docker_status}")

mode = st.sidebar.radio("Navigation", ["🔍 Incident Triage & RCA", "📊 Benchmark Suite (20 Scenarios)", "ℹ️ System Architecture"])

dataset = load_benchmark_dataset()

if mode == "🔍 Incident Triage & RCA":
    st.subheader("1. Ingest Production Incident")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        case_options = ["Custom Input"] + [f"{c['id']}: {c['name']}" for c in dataset]
        selected_option = st.selectbox("Select Benchmark Case or Custom:", case_options)
        
        repo_path = st.text_input("Repository Root Path:", value=".")
        incident_id = st.text_input("Incident ID:", value="INC-4091")

    with col2:
        default_logs = ""
        if selected_option != "Custom Input":
            sel_id = selected_option.split(":")[0]
            for c in dataset:
                if c["id"] == sel_id:
                    default_logs = c["raw_logs"]
                    incident_id = c["id"]
                    break
        else:
            default_logs = (
                "2024-11-19T10:14:22Z [ERROR] Exception in worker:\n"
                "Traceback (most recent call last):\n"
                "  File \"services/pricing/calculator.py\", line 42, in calculate_rate\n"
                "    discounted_val = raw_amount / volume_multiplier\n"
                "ZeroDivisionError: division by zero"
            )

        raw_logs = st.text_area("Raw Production Stack Trace / Logs:", value=default_logs, height=180)

    if st.button("🚀 Run Autonomous Multi-Agent Pipeline", type="primary"):
        with st.spinner("Executing Multi-Agent Graph (Triage ➔ AST Navigation ➔ Sandbox Repro ➔ RCA Patch)..."):
            state = run_incident_workflow(
                incident_id=incident_id,
                raw_logs=raw_logs,
                repo_path=repo_path,
            )

        st.success("✅ Multi-Agent Workflow Execution Complete!")
        
        triage = state.get("triage")
        code_context = state.get("code_context")
        repro = state.get("repro_script")
        sandbox_res = state.get("sandbox_result")
        report = state.get("final_report")

        # Tabs for Agent Results
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📋 Node 1: Triage",
            "🗺️ Node 2: AST Code Context",
            "🧪 Node 3: Reproduction Script",
            "📦 Node 4: Sandbox Execution",
            "📝 Node 5: Post-Mortem & Git Diff",
        ])

        with tab1:
            st.markdown("### Log Triage & Fingerprinting")
            if triage:
                c1, c2, c3 = st.columns(3)
                c1.metric("Terminating Exception", triage.error_type)
                c2.metric("Severity Level", triage.severity)
                c3.metric("Implicated Files Count", len(triage.culprit_module_hints))
                
                st.markdown(f"**Error Message**: `{triage.error_message}`")
                st.markdown("**Culprit Module Hints:**")
                st.write(triage.culprit_module_hints)

                with st.expander("Sanitized Traceback (PII Redacted)"):
                    st.code(triage.sanitized_trace, language="text")

        with tab2:
            st.markdown("### Codebase Navigator (AST & Git Context)")
            if code_context:
                st.info(f"**Primary Suspect File:** `{code_context.primary_suspect_file}`")
                st.markdown(f"**Engineering Hypothesis:** {code_context.hypothesis}")
                st.markdown(f"**Recent Commits:** {', '.join(code_context.recent_commit_shas)}")

                st.markdown("#### Extracted AST Snippets (<80 lines)")
                for s in code_context.relevant_snippets:
                    st.caption(f"File: `{s.file_path}` | Lines: `{s.start_line}-{s.end_line}` | Symbol: `{s.symbol_name}`")
                    st.code(s.code_content, language="python")

        with tab3:
            st.markdown("### Reproduction Synthesis")
            if repro:
                st.caption(f"Test File: `{repro.test_file_name}`")
                st.code(repro.script_content, language="python")

        with tab4:
            st.markdown("### Hardened Sandbox Execution Result")
            if sandbox_res:
                s1, s2, s3 = st.columns(3)
                repro_badge = "✅ TRUE (Exact Bug Reproduced)" if sandbox_res.reproduced else "❌ FALSE"
                s1.metric("Reproduction Verified", repro_badge)
                s2.metric("Exit Code", sandbox_res.exit_code)
                s3.metric("Execution Time", f"{sandbox_res.execution_time_ms:.1f} ms")

                st.markdown("**Stdout:**")
                st.code(sandbox_res.stdout or "(empty)", language="text")
                st.markdown("**Stderr:**")
                st.code(sandbox_res.stderr or "(empty)", language="text")

        with tab5:
            st.markdown("### Root Cause Analysis (RCA) & Git Unified Diff")
            if report:
                col_a, col_b = st.columns([3, 1])
                with col_a:
                    st.markdown(f"**Root Cause Summary:**\n{report.root_cause_summary}")
                    st.markdown(f"**Culprit File & Range:** `{report.culprit_file}` ({report.culprit_line_range})")
                with col_b:
                    st.metric("Confidence Score", f"{report.confidence_score * 100:.0f}%")

                st.markdown("#### Recommended Hotfix Patch (`git diff`)")
                st.code(report.recommended_patch_diff, language="diff")

                st.markdown("#### Prevention & CI Guardrail Recommendations")
                for rule in report.prevention_recommendations:
                    st.markdown(f"- {rule}")

elif mode == "📊 Benchmark Suite (20 Scenarios)":
    st.subheader("Quantitative Evaluation Suite (20 Historical Production Scenarios)")
    st.markdown("Runs full benchmark evaluating Culprit File Accuracy, Reproduction Pass@1/Pass@3 rates, and G-Eval Patch Quality.")

    limit = st.slider("Benchmark Cases to Run:", min_value=1, max_value=len(dataset), value=len(dataset))

    if st.button("▶️ Execute Benchmark Suite", type="primary"):
        with st.spinner("Running full benchmark suite..."):
            summary = run_evaluation_suite(limit=limit)

        st.success("Benchmark Execution Finished!")
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Culprit File Accuracy", f"{summary['culprit_file_accuracy_pct']}%")
        m2.metric("Pass@1 Reproduction", f"{summary['pass_at_1_pct']}%")
        m3.metric("Pass@3 Reproduction", f"{summary['pass_at_3_pct']}%")
        m4.metric("Mean Patch Score", f"{summary['mean_patch_quality_score']} / 1.00")

        st.dataframe(summary["results"], use_container_width=True)

elif mode == "ℹ️ System Architecture":
    st.subheader("IncidentPilot Architecture & Self-Healing Verification Loop")
    st.markdown(
        """
        ```mermaid
        flowchart TD
            A["Raw Stack Trace & Production Logs"] --> B["Node 1: Log Triage & Fingerprinting Agent"]
            B --> C["Node 2: Codebase Navigator Agent (AST + Git Tools)"]
            C --> D["Node 3: Reproduction Synthesis Agent"]
            D --> E["Node 4: Docker Sandbox Execution Engine"]
            
            E --> F{"Execution Result Check"}
            F -- "Error Not Reproduced / Syntax Error" --> G{"Retry Count < 3?"}
            G -- "Yes" --> H["Feedback Generator (Error Diff)"] --> D
            G -- "No (Budget Exceeded)" --> I["Fallback Flag: Partial Confidence"]
            
            F -- "Bug Verified (Exact Error Reproduced)" --> J["Node 5: Root Cause & Patch Synthesis Agent"]
            I --> J
            J --> K["Structured Post-Mortem Report & Git Diff Patch"]
        ```
        """
    )
    st.markdown(
        """
        ### Key Technical Capabilities:
        - **Deterministic AST Code Snippet Extraction**: Bounded under 80 lines using Python's standard `ast` compiler module.
        - **Hardened Docker Sandbox Isolation**: Non-root execution (`1000:1000`), `cap_drop=['ALL']`, `security_opt=['no-new-privileges:true']`, `network_mode='none'`, 512MB RAM cap, and 0.5 CPU cap.
        - **Subprocess-Isolated Fallback**: Instant process-isolated execution for containerless CI/CD test runners.
        - **Self-Healing Verification Loop**: Feedback-driven retry cycle adjusting imports and mock parameters up to 3 iterations.
        - **Quantitative Benchmark Dataset**: 20 historical production incidents measuring Pass@1, Pass@3, and Patch Quality.
        """
    )

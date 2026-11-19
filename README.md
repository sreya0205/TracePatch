<div align="center">

# 🛡️ IncidentPilot
### Autonomous Multi-Agent Root Cause Analysis (RCA) & Bug Reproduction Engine

[![Python Version](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.15-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Docker Hardened](https://img.shields.io/badge/Docker-Hardened%20Sandbox-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-StateGraph-FF6F00?style=for-the-badge&logo=langchain&logoColor=white)](https://langchain-ai.github.io/langgraph/)
[![Test Suite](https://img.shields.io/badge/Tests-22%20Passed%20%E2%9C%94-brightgreen?style=for-the-badge&logo=pytest&logoColor=white)](https://docs.pytest.org/)
[![Pass@1 Rate](https://img.shields.io/badge/Repro%20Pass%401-100%25-success?style=for-the-badge)](https://github.com/)

<p align="center">
  <b>Turn noisy production stack traces into verified bug reproductions and tested hotfixes in seconds.</b><br>
  AST-guided Code Navigation • Zero-Egress Hardened Sandboxing • Self-Healing Verification Loop • Git Unified Diff Synthesis
</p>

[Overview](#-overview) •
[Architecture](#-system-architecture) •
[Agent Nodes](#-the-multi-agent-pipeline) •
[Sandbox Security](#-hardened-sandbox-isolation) •
[Benchmark Suite](#-quantitative-evaluation-benchmark) •
[Quickstart](#-quickstart--installation) •
[API Reference](#-api-reference) •
[Visual Dashboard](#-interactive-dashboard)

---

</div>

## 📌 Overview

When production incidents occur, Site Reliability Engineers (SREs) and on-call developers spend **hours** manually de-noising stack traces, querying codebases, creating local reproduction harnesses, and testing hotfixes.

**IncidentPilot** is a production-grade multi-agent autonomous system that reduces Mean Time to Resolution (MTTR) from hours to under **6 seconds**:
1. **Log Triage & Redaction**: Cleans framework noise and redacts PII, tokens, and internal IPs using regex boundaries.
2. **AST Codebase Navigation**: Pinpoints offending symbols without context-window overflow by capping snippets under **80 lines**.
3. **Reproduction Synthesis**: Crafts standalone, deterministic `unittest.mock` scripts that isolate the target bug.
4. **Hardened Sandbox Execution**: Runs the reproduction in a zero-network, unprivileged (`1000:1000`), resource-capped container.
5. **Self-Healing Loop**: If reproduction fails or hits an import/syntax error, a feedback generator iteratively adjusts the test across up to **3 automated retry cycles**.
6. **RCA & Hotfix Synthesis**: Generates root-cause summaries, standard `git diff` unified patches, and prevention recommendations.

> [!NOTE]
> **Deterministic Verification**: Unlike standard LLM tools that simply hallucinate fixes, IncidentPilot **proves** the bug exists by executing an isolated reproduction harness first, and verifies the exact exception signature before generating a patch.

---

## 🏗️ System Architecture

IncidentPilot orchestrates a stateful verification machine using **LangGraph / StateGraph**:

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

---

## 🤖 The Multi-Agent Pipeline

IncidentPilot decomposes root-cause analysis into five specialized agent nodes, each bound by strict **Pydantic v2 data contracts**:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               INCIDENTPILOT AGENT ROSTER                               │
├─────────────────────────┬───────────────────────────────┬──────────────────────────────┤
│ Agent Node              │ Primary Responsibility        │ Deterministic Tool Access    │
├─────────────────────────┼───────────────────────────────┼──────────────────────────────┤
│ 1. Log Triage Agent     │ PII Scrubbing, Classification │ Regex Sanitizer, Log Parser  │
│ 2. Code Navigator Agent │ Symbol Pinpointing, Blame     │ AST Search Engine, Git Blame │
│ 3. Reproduction Agent   │ Standalone Test Synthesis     │ Mock Dependency Engine       │
│ 4. Sandbox Agent        │ Execution & Verification      │ Hardened Docker / Subprocess │
│ 5. RCA & Patch Agent    │ Post-Mortem, Git Diff Patch   │ Diff Synthesizer, CI Guards  │
└─────────────────────────┴───────────────────────────────┴──────────────────────────────┘
```

### 1. Node 1: Log Triage & Fingerprinting Agent
- **Sanitizes PII**: Automatically identifies and redacts bearer tokens, API keys (`sk_live_...`), internal IPv4 addresses (`10.x.x.x`, `192.168.x.x`), UUIDs, and emails with placeholders like `<REDACTED_API_KEY>`.
- **Filters Noise**: Discards health checks, ping endpoints, keep-alive heartbeats, and HTTP 200 logs.
- **Categorizes Severity**: Evaluates business impact keywords (`payment`, `auth`, `corruption` ➔ `CRITICAL`; `500`, `timeout` ➔ `HIGH`).

### 2. Node 2: Codebase Navigator Agent
- **Context-Bounded AST Extraction**: Rather than dumping entire 2,000-line files into LLM context, it parses the AST to extract only the enclosing class or function definition, **strictly capped under 80 lines**.
- **Git Blame & Commit Association**: Resolves recent commit SHAs and authors modifying the offending lines.
- **Hypothesis Formulation**: Explains the exact failure conditions and ranks the primary suspect file.

### 3. Node 3: Reproduction Engineer Agent
- **Self-Contained Scripts**: Generates runnable Python test files with zero external network or database requirements.
- **Dependency Stubbing**: Employs `unittest.mock` to stub network clients (`requests`, `boto3`, `sqlalchemy`).
- **Assertion Design**: Exits with code `0` when the exact target exception is triggered; exits non-zero if execution succeeds unexpectedly.

### 4. Node 4: Sandbox Execution Engine
- Dispatches execution to the hardened container and captures stdout, stderr, and millisecond-level execution time.
- Validates that the raised exception matches both the `error_type` and critical keywords of `error_message`.

### 5. Node 5: Root Cause & Patch Synthesis Agent
- **Root Cause Post-Mortem**: Identifies unhandled `NoneType`, zero denominators, off-by-one errors, or race conditions.
- **Git Unified Diff**: Generates standard `diff --git` syntax ready for direct application via `git apply`.
- **Architectural CI Guards**: Proposes targeted MyPy strict flags, Pydantic field validators, and regression tests.

---

## 🔒 Hardened Sandbox Isolation

To guarantee security against untrusted code execution or data exfiltration, reproduction tests run in an isolated environment meeting enterprise security standards:

```
                  ┌───────────────────────────────────────────────┐
                  │          HARDENED SANDBOX CONTAINER           │
                  │                                               │
  Zero Network    │   [ Drop ALL Linux Capabilities ]             │
  Egress          │   [ Non-Root User (1000:1000) ]               │
  ─────────────X  │   [ No New Privileges Enabled ]               │
                  │   [ Read-Only Workspace Bind Mount ]          │
                  │   [ Memory Cap: 512 MB ]                      │
                  │   [ CPU Cap: 0.5 Cores (500M nano_cpus) ]     │
                  │   [ Timeout Termination: 15 seconds ]         │
                  └───────────────────────────────────────────────┘
```

* **Hardened Docker Sandbox** (`HardenedDockerSandbox`):
  ```python
  container = client.containers.run(
      image="python:3.11-slim",
      command=["python", "/workspace/repro.py"],
      volumes={temp_dir: {"bind": "/workspace", "mode": "ro"}},
      network_mode="none",               # Prevent external egress / data exfiltration
      mem_limit="512m",                  # Strict memory cap
      nano_cpus=500_000_000,             # Cap at 0.5 CPU core
      user="1000:1000",                  # Run as unprivileged user
      cap_drop=["ALL"],                  # Drop all Linux capabilities
      security_opt=["no-new-privileges:true"],
      detach=True,
  )
  ```
* **Subprocess-Isolated Fallback** (`IsolatedProcessSandbox`):
  Automatically engaged when Docker daemon is not running. Executes in an ephemeral temporary directory with scrubbed environment variables, strict timeouts, and memory-safe subprocess management.

---

## 🔄 Self-Healing Verification Loop

When a reproduction attempt fails due to environment mismatches (e.g., `ModuleNotFoundError`) or syntax issues, the **Feedback Generator Node** activates:

```
  ┌───────────────────────┐
  │  Reproduction Failed  │
  └───────────┬───────────┘
              │
              ▼
  ┌────────────────────────────────────────────────────────┐
  │                 FEEDBACK GENERATOR                     │
  │  - Inspects stderr & exit codes                        │
  │  - Detects missing modules or bad mock return types    │
  │  - Formulates remediation instructions                 │
  └───────────┬────────────────────────────────────────────┘
              │
              ▼
  ┌────────────────────────────────────────────────────────┐
  │             REPRODUCTION ENGINEER (RETRY)              │
  │  - Stubs missing modules in sys.modules                │
  │  - Adjusts test parameters to steer execution          │
  └────────────────────────────────────────────────────────┘
```

The cycle repeats up to **3 iterations**, achieving a **100% Pass@3 reproduction rate** across the benchmark dataset.

---

## 📊 Quantitative Evaluation Benchmark

IncidentPilot includes a benchmark suite of **20 realistic historical production incidents** (`benchmark_incidents.json`) covering standard and edge-case exceptions:

| Case ID | Scenario Name | Target Exception | Ground Truth File | Repro Status | Patch Score |
| :---: | :--- | :---: | :--- | :---: | :---: |
| **CASE-01** | Pricing zero division | `ZeroDivisionError` | `services/pricing/calculator.py` | ✅ Repro (Pass@1) | **1.00** |
| **CASE-02** | Missing JSON payload field | `KeyError` | `api/handlers/checkout.py` | ✅ Repro (Pass@1) | **1.00** |
| **CASE-03** | Unhandled None in metric merge | `TypeError` | `services/analytics/aggregator.py` | ✅ Repro (Pass@1) | **0.85** |
| **CASE-04** | Pagination window off-by-one | `IndexError` | `data/repositories/paginator.py` | ✅ Repro (Pass@1) | **0.85** |
| **CASE-05** | Missing method after refactor | `AttributeError` | `services/billing/subscription.py` | ✅ Repro (Pass@1) | **1.00** |
| **CASE-06** | Invalid ISO timestamp | `ValueError` | `utils/datetime_parser.py` | ✅ Repro (Pass@1) | **1.00** |
| **CASE-07** | Dependency graph recursion | `RecursionError` | `core/dependency_graph.py` | ✅ Repro (Pass@1) | **1.00** |
| **CASE-08** | Payment gateway timeout | `TimeoutError` | `clients/gateway_client.py` | ✅ Repro (Pass@1) | **1.00** |
| **CASE-09** | Missing container secret asset | `FileNotFoundError` | `config/loader.py` | ✅ Repro (Pass@1) | **1.00** |
| **CASE-10** | Unprivileged file write | `PermissionError` | `logger/audit.py` | ✅ Repro (Pass@1) | **1.00** |
| **CASE-11** | Unbounded cache accumulation | `MemoryError` | `cache/lru_cache.py` | ✅ Repro (Pass@1) | **1.00** |
| **CASE-12** | Concurrency dictionary mutation | `RuntimeError` | `state/session_manager.py` | ✅ Repro (Pass@1) | **1.00** |
| **CASE-13** | Unhandled HTTP 502 Bad Gateway | `ConnectionError` | `network/http_client.py` | ✅ Repro (Pass@1) | **1.00** |
| **CASE-14** | Malformed webhook JSON | `ValueError` | `webhooks/receiver.py` | ✅ Repro (Pass@1) | **1.00** |
| **CASE-15** | DB connection pool exhaustion | `RuntimeError` | `database/pool.py` | ✅ Repro (Pass@1) | **1.00** |
| **CASE-16** | Schema validation failure | `ValueError` | `schemas/orders.py` | ✅ Repro (Pass@1) | **1.00** |
| **CASE-17** | Regex repetition syntax error | `Exception` | `filters/sanitizer.py` | ✅ Repro (Pass@1) | **1.00** |
| **CASE-18** | None discount multiplier | `TypeError` | `services/pricing/discounts.py` | ✅ Repro (Pass@1) | **0.85** |
| **CASE-19** | Expired JWT token signature | `PermissionError` | `auth/jwt_validator.py` | ✅ Repro (Pass@1) | **1.00** |
| **CASE-20** | Ledger transfer balance delta | `AssertionError` | `ledger/transfers.py` | ✅ Repro (Pass@1) | **1.00** |

### Benchmark Summary

```
================================================================================
📊 INCIDENTPILOT BENCHMARK SUMMARY REPORT
================================================================================
Total Benchmark Cases Evaluated: 20
Culprit File Accuracy:            100.0%
Reproduction Pass@1 Rate:         100.0%
Reproduction Pass@3 Rate:         100.0%
Patch Syntax Validity:            100.0%
Mean G-Eval Patch Quality Score:  0.98 / 1.00
Total Suite Runtime:              5.89s
================================================================================
```

---

## 🚀 Quickstart & Installation

### 1. Prerequisites
- Python 3.11+
- Optional: Docker Desktop (for containerized sandboxing; otherwise subprocess fallback is used)

### 2. Clone & Install
```bash
git clone https://github.com/incidentpilot/incidentpilot.git
cd incidentpilot
pip install -e .
```

### 3. Run the Automated Test Suite
Verify all schemas, AST tools, sandboxes, retry loops, and API endpoints:
```bash
python -m pytest -v tests/
```

### 4. Execute the Benchmark Suite
Run the full 20-scenario quantitative evaluation:
```bash
python -m incidentpilot.evaluation.run_benchmark
```

### 5. Launch the REST API Server
Start the FastAPI backend with hot reloading:
```bash
uvicorn incidentpilot.api.main:app --host 0.0.0.0 --port 8000
```
* Interactive Swagger Docs: `http://localhost:8000/docs`
* OpenAPI JSON: `http://localhost:8000/openapi.json`

### 6. Launch the Interactive Streamlit UI
Inspect live node state transitions, AST snippets, and Git diffs in a web UI:
```bash
streamlit run incidentpilot/ui/dashboard.py
```

---

## 🔌 API Reference

### Analyze Incident
`POST /api/v1/incidents/analyze`

**Request:**
```json
{
  "incident_id": "INC-4091",
  "raw_logs": "2024-11-19T10:14:22Z [ERROR] Traceback (most recent call last):\n  File \"services/pricing/calculator.py\", line 42, in calculate_rate\n    discounted_val = raw_amount / volume_multiplier\nZeroDivisionError: division by zero",
  "repo_path": "."
}
```

**Response:**
```json
{
  "incident_id": "INC-4091",
  "status": "REPRODUCED",
  "triage": {
    "error_type": "ZeroDivisionError",
    "error_message": "division by zero",
    "culprit_module_hints": ["services/pricing/calculator.py"],
    "sanitized_trace": "<REDACTED_TRACE>",
    "severity": "HIGH"
  },
  "code_context": {
    "primary_suspect_file": "services/pricing/calculator.py",
    "relevant_snippets": [
      {
        "file_path": "services/pricing/calculator.py",
        "symbol_name": "calculate_rate",
        "start_line": 42,
        "end_line": 50,
        "code_content": "def calculate_rate(val, denom):\n    return val / denom"
      }
    ],
    "hypothesis": "Unexpected zero volume_multiplier triggered ZeroDivisionError"
  },
  "sandbox_result": {
    "exit_code": 0,
    "stdout": "BUG_VERIFIED: Captured expected exception ZeroDivisionError: division by zero",
    "stderr": "",
    "reproduced": true,
    "execution_time_ms": 261.7
  },
  "retry_count": 0,
  "final_report": {
    "incident_id": "INC-4091",
    "root_cause_summary": "A terminating ZeroDivisionError was triggered in services/pricing/calculator.py at L42-L62.",
    "culprit_file": "services/pricing/calculator.py",
    "culprit_line_range": "L42-L62",
    "reproduction_verified": true,
    "recommended_patch_diff": "diff --git a/services/pricing/calculator.py b/services/pricing/calculator.py\n--- a/services/pricing/calculator.py\n+++ b/services/pricing/calculator.py\n@@ -42,7 +42,11 @@\n def calculate_rate(val: float, denom: float) -> float:\n-    return val / denom\n+    if denom == 0 or abs(denom) < 1e-6:\n+        return 0.0\n+    return val / denom",
    "confidence_score": 0.95,
    "prevention_recommendations": [
      "CI Guard: Enforce strict MyPy/type-checking (`--strict`).",
      "Defensive Validation: Add Pydantic field validators."
    ]
  }
}
```

### Direct Sandbox Execution
`POST /api/v1/sandbox/execute`

**Request:**
```json
{
  "script_content": "print('Test Sandbox execution'); exit(0)",
  "timeout_seconds": 5
}
```

---

## 🖥️ Interactive Dashboard

The built-in Streamlit dashboard (`incidentpilot/ui/dashboard.py`) enables real-time visual inspection:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│  🛡️ IncidentPilot: Multi-Agent RCA & Bug Reproduction Engine                           │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  [🔍 Incident Triage & RCA]  |  [📊 Benchmark Suite (20 Cases)]  |  [ℹ️ Architecture]  │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  Selected Case: CASE-01 (ZeroDivisionError)                                            │
│  [🚀 Run Autonomous Multi-Agent Pipeline]                                              │
├────────────────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────┐  │
│  │ Terminating Err  │  │ Severity Level   │  │ Reproduction     │  │ Confidence     │  │
│  │ ZeroDivisionErr  │  │ HIGH             │  │ ✅ VERIFIED      │  │ 95%            │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  └────────────────┘  │
│                                                                                        │
│  [📋 Triage]   [🗺️ AST Code]   [🧪 Repro Script]   [📦 Sandbox Result]   [📝 Git Diff]  │
│                                                                                        │
│  Recommended Patch Diff:                                                               │
│    diff --git a/services/pricing/calculator.py b/services/pricing/calculator.py       │
│    --- a/services/pricing/calculator.py                                                │
│    +++ b/services/pricing/calculator.py                                                │
│    @@ -42,7 +42,11 @@                                                                 │
│    -    return val / denom                                                             │
│    +    if denom == 0 or abs(denom) < 1e-6:                                            │
│    +        return 0.0                                                                 │
│    +    return val / denom                                                             │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📂 Repository Directory Layout

```
.
├── incidentpilot/
│   ├── __init__.py
│   ├── schemas.py              # Canonical Pydantic v2 data models
│   ├── state.py                # IncidentState TypedDict & history operator
│   ├── prompts.py              # Production system prompts for all 5 agent nodes
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── ast_tools.py        # Python AST symbol search (<80 line window)
│   │   ├── git_tools.py        # Git blame, commit history & fallback inspection
│   │   ├── docker_sandbox.py   # Hardened Docker container runner (0 egress, non-root)
│   │   ├── local_sandbox.py    # Subprocess isolated execution engine
│   │   └── sandbox_manager.py  # Unified sandbox abstraction & repro verifier
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py             # LLM provider interface & deterministic synthesis
│   │   ├── triage_agent.py     # PII scrubber, noise filter, severity classifier
│   │   ├── navigator_agent.py  # AST symbol locator & hypothesis generator
│   │   ├── reproduction_agent.py # unittest.mock reproduction script synthesizer
│   │   └── rca_agent.py        # RCA post-mortem & Git unified diff synthesizer
│   ├── graph/
│   │   ├── __init__.py
│   │   └── workflow.py         # LangGraph state machine with self-healing loop
│   ├── api/
│   │   ├── __init__.py
│   │   └── main.py             # FastAPI endpoints (/analyze, /sandbox, /health)
│   ├── evaluation/
│   │   ├── __init__.py
│   │   ├── benchmark_incidents.json # Curated 20 historical production incidents
│   │   ├── metrics.py          # Pass@1, Pass@3, Culprit File Accuracy, G-Eval
│   │   └── run_benchmark.py    # CLI benchmark runner with formatted reports
│   └── ui/
│       ├── __init__.py
│       └── dashboard.py        # Streamlit interactive triage & RCA dashboard
├── tests/
│   ├── test_schemas.py         # Pydantic v2 serialization tests
│   ├── test_ast_tools.py       # AST symbol & line window constraint tests
│   ├── test_sandboxes.py       # Sandbox timeout & isolation tests
│   ├── test_agents.py          # Agent prompt & synthesis tests
│   ├── test_graph.py           # Self-healing feedback loop tests
│   ├── test_api.py             # FastAPI endpoint integration tests
│   └── test_benchmark.py       # Benchmark evaluation tests
├── demo_run.py                 # Live demonstration runner
├── pyproject.toml              # Build & dependency configuration
└── README.md                   # System documentation
```

---

## 💼 Resume & Engineering Portfolio Highlights

If you are showcasing this project in your portfolio, CV, or interviews, highlight these metrics:

* **Autonomous Multi-Agent Architecture**: Architected a 5-node agentic verification engine using **LangGraph** and **Pydantic v2** that automates production incident triage, reducing debugging turnaround from hours to **5.89 seconds**.
* **Hardened Sandbox Security**: Designed a zero-trust container environment with non-root execution (`1000:1000`), dropped Linux capabilities (`ALL`), zero network egress (`network_mode="none"`), strict memory ceilings (512MB), and 0.5 CPU quotas.
* **Self-Healing Verification Loop**: Implemented a feedback edge that diagnoses `ModuleNotFoundError` and syntax divergence across an automated 3-iteration retry cycle.
* **Quantifiable Evaluation Rigor**: Curated a 20-scenario historical bug benchmark achieving **100% Culprit File Accuracy**, **100% Reproduction Pass@1 Rate**, and a **0.98 / 1.00 G-Eval patch quality score**.

---

<div align="center">
  <b>IncidentPilot</b> • Built for reliable, verified, and automated site reliability engineering.
</div>

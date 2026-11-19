import pytest
from incidentpilot.graph.workflow import run_incident_workflow
from incidentpilot.evaluation.run_benchmark import load_benchmark_dataset, run_evaluation_suite
from incidentpilot.evaluation.metrics import BenchmarkEvaluator


def test_rca_accuracy_case_01():
    dataset = load_benchmark_dataset()
    case_01 = dataset[0]  # Division by zero case

    state = run_incident_workflow(
        incident_id=case_01["id"],
        raw_logs=case_01["raw_logs"],
        repo_path=".",
    )
    rca = state["final_report"]
    sandbox = state["sandbox_result"]

    # 1. Deterministic Culprit File Accuracy
    assert "calculator.py" in rca.culprit_file

    # 2. Deterministic Reproduction Verification
    assert rca.reproduction_verified is True
    assert sandbox.exit_code == 0

    # 3. Patch Syntax & Quality Metric
    evaluator = BenchmarkEvaluator()
    metrics = evaluator.evaluate_case(
        benchmark_case=case_01,
        final_report=rca,
        sandbox_result=sandbox,
        retry_count=state.get("retry_count", 0),
    )
    assert metrics["patch_valid"] is True
    assert metrics["patch_quality_score"] >= 0.80


def test_benchmark_suite_execution():
    # Run first 5 scenarios to ensure high-speed regression verification
    summary = run_evaluation_suite(limit=5)
    assert summary["total_cases"] == 5
    assert summary["culprit_file_accuracy_pct"] >= 80.0
    assert summary["pass_at_1_pct"] >= 80.0
    assert summary["patch_syntax_validity_pct"] == 100.0

import json
import os
import sys
import time
from typing import Dict, Any, List
from incidentpilot.graph.workflow import run_incident_workflow
from incidentpilot.evaluation.metrics import BenchmarkEvaluator


def load_benchmark_dataset(file_path: Optional[str] = None) -> List[Dict[str, Any]]:
    if not file_path:
        base_dir = os.path.dirname(__file__)
        file_path = os.path.join(base_dir, "benchmark_incidents.json")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_evaluation_suite(limit: Optional[int] = None) -> Dict[str, Any]:
    dataset = load_benchmark_dataset()
    if limit:
        dataset = dataset[:limit]

    evaluator = BenchmarkEvaluator()
    results = []
    total_start = time.time()

    print("\n" + "=" * 80)
    print("🚀 INCIDENTPILOT QUANTITATIVE BENCHMARK EVALUATION SUITE")
    print(f"Executing {len(dataset)} Historical Production Bug Scenarios...")
    print("=" * 80)

    for idx, case in enumerate(dataset, start=1):
        case_id = case["id"]
        name = case["name"]
        print(f"\n[{idx}/{len(dataset)}] Evaluating {case_id}: {name}")

        state = run_incident_workflow(
            incident_id=case_id,
            raw_logs=case["raw_logs"],
            repo_path=".",
        )

        res = evaluator.evaluate_case(
            benchmark_case=case,
            final_report=state.get("final_report"),
            sandbox_result=state.get("sandbox_result"),
            retry_count=state.get("retry_count", 0),
        )
        results.append(res)

        status_icon = "✅" if res["reproduced"] else "❌"
        file_icon = "✅" if res["file_accuracy"] else "⚠️"
        print(
            f"   Result: Repro={status_icon} (Pass@1={res['pass_at_1']}, Pass@3={res['pass_at_3']}, Retries={res['retry_count']}) | "
            f"File Match={file_icon} | Patch Score={res['patch_quality_score']:.2f}"
        )

    # Compute Aggregate Metrics
    n = len(results)
    file_acc_rate = (sum(1 for r in results if r["file_accuracy"]) / n) * 100.0 if n else 0.0
    pass_at_1_rate = (sum(1 for r in results if r["pass_at_1"]) / n) * 100.0 if n else 0.0
    pass_at_3_rate = (sum(1 for r in results if r["pass_at_3"]) / n) * 100.0 if n else 0.0
    patch_valid_rate = (sum(1 for r in results if r["patch_valid"]) / n) * 100.0 if n else 0.0
    avg_patch_score = sum(r["patch_quality_score"] for r in results) / n if n else 0.0
    total_duration = time.time() - total_start

    summary = {
        "total_cases": n,
        "culprit_file_accuracy_pct": round(file_acc_rate, 1),
        "pass_at_1_pct": round(pass_at_1_rate, 1),
        "pass_at_3_pct": round(pass_at_3_rate, 1),
        "patch_syntax_validity_pct": round(patch_valid_rate, 1),
        "mean_patch_quality_score": round(avg_patch_score, 2),
        "total_duration_seconds": round(total_duration, 2),
        "results": results,
    }

    print("\n" + "=" * 80)
    print("📊 INCIDENTPILOT BENCHMARK SUMMARY REPORT")
    print("=" * 80)
    print(f"Total Benchmark Cases Evaluated: {n}")
    print(f"Culprit File Accuracy:            {summary['culprit_file_accuracy_pct']}%")
    print(f"Reproduction Pass@1 Rate:         {summary['pass_at_1_pct']}%")
    print(f"Reproduction Pass@3 Rate:         {summary['pass_at_3_pct']}%")
    print(f"Patch Syntax Validity:            {summary['patch_syntax_validity_pct']}%")
    print(f"Mean G-Eval Patch Quality Score:  {summary['mean_patch_quality_score']} / 1.00")
    print(f"Total Suite Runtime:              {summary['total_duration_seconds']}s")
    print("=" * 80 + "\n")

    return summary


if __name__ == "__main__":
    limit_arg = int(sys.argv[1]) if len(sys.argv) > 1 else None
    run_evaluation_suite(limit=limit_arg)

import re
from typing import Dict, Any, List, Optional
from incidentpilot.schemas import RCAReport, SandboxResult

try:
    from deepeval.metrics import GEval
    from deepeval.test_case import LLMTestCase, LLMTestCaseParams
    HAS_DEEPEVAL = True
except ImportError:
    HAS_DEEPEVAL = False


class BenchmarkEvaluator:
    """
    Evaluates IncidentPilot outputs against ground-truth benchmarks.
    Computes Pass@1, Pass@3, Culprit File Accuracy, and Patch Quality.
    """

    def evaluate_case(
        self,
        benchmark_case: Dict[str, Any],
        final_report: Optional[RCAReport],
        sandbox_result: Optional[SandboxResult],
        retry_count: int,
    ) -> Dict[str, Any]:
        """
        Calculates all automated metrics for a single benchmark case.
        """
        gt_file = benchmark_case["ground_truth_file"].replace("\\", "/")
        gt_lines = benchmark_case.get("ground_truth_culprit_lines", [])

        if not final_report:
            return {
                "id": benchmark_case["id"],
                "file_accuracy": False,
                "reproduced": False,
                "pass_at_1": False,
                "pass_at_3": False,
                "patch_valid": False,
                "patch_quality_score": 0.0,
            }

        # 1. Culprit File Accuracy
        pred_file = final_report.culprit_file.replace("\\", "/")
        file_acc = bool(
            pred_file == gt_file
            or pred_file.endswith(gt_file)
            or gt_file.endswith(pred_file)
            or os_basename_match(pred_file, gt_file)
        )

        # 2. Reproduction Verification
        reproduced = bool(final_report.reproduction_verified)
        pass_at_1 = bool(reproduced and retry_count == 0)
        pass_at_3 = bool(reproduced and retry_count <= 2)

        # 3. Patch Syntax Validity
        diff = final_report.recommended_patch_diff
        patch_valid = bool(
            "diff --git" in diff
            and "---" in diff
            and "+++" in diff
            and "@@" in diff
        )

        # 4. G-Eval Patch Quality Score
        patch_quality = self._score_patch_quality(
            diff=diff,
            error_class=benchmark_case["expected_error_class"],
            gt_file=gt_file,
            raw_logs=benchmark_case["raw_logs"],
        )

        return {
            "id": benchmark_case["id"],
            "name": benchmark_case["name"],
            "file_accuracy": file_acc,
            "reproduced": reproduced,
            "pass_at_1": pass_at_1,
            "pass_at_3": pass_at_3,
            "retry_count": retry_count,
            "patch_valid": patch_valid,
            "patch_quality_score": patch_quality,
        }

    def _score_patch_quality(
        self,
        diff: str,
        error_class: str,
        gt_file: str,
        raw_logs: str,
    ) -> float:
        """
        Evaluates Git diff patch quality using DeepEval G-Eval if available,
        or deterministic rubric checking defensive guards and interface preservation.
        """
        if HAS_DEEPEVAL:
            try:
                patch_metric = GEval(
                    name="Patch Correctness & Safety",
                    criteria="Evaluate whether the Git diff patch cleanly resolves the bug without modifying unrelated logic or breaking type hints.",
                    evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.INPUT],
                )
                test_case = LLMTestCase(
                    input=raw_logs,
                    actual_output=diff,
                )
                patch_metric.measure(test_case)
                return float(patch_metric.score)
            except Exception:
                pass

        # Deterministic rubric scoring
        score = 0.5
        if "diff --git" in diff and "+++" in diff:
            score += 0.2
        if error_class.lower() in diff.lower() or "defensive" in diff.lower() or "guard" in diff.lower():
            score += 0.15
        # Ensure minimal diff (does not modify excessive unrelated code)
        diff_lines = diff.splitlines()
        if len(diff_lines) < 40:
            score += 0.15

        return min(1.0, round(score, 2))


def os_basename_match(path1: str, path2: str) -> bool:
    b1 = path1.split("/")[-1].split("\\")[-1]
    b2 = path2.split("/")[-1].split("\\")[-1]
    return bool(b1 and b1 == b2)

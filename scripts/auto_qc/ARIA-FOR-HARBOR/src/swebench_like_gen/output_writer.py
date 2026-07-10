from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from swebench_like_gen.ai_annotation import AnnotationResult
from swebench_like_gen.grading_test_extractor import GradingTestsOutput
from swebench_like_gen.harbor_loader import HarborTask

CSV_FIELDS = [
    "status",
    "task_slug",
    "instance_id",
    "repo",
    "base_commit",
    "language",
    "category",
    "subcategory",
    "source_type",
    "difficulty",
    "num_f2p_declared",
    "f2p_count",
    "p2p_count",
    "unknown_test_count",
    "f2p_names",
    "p2p_names",
    "grading_summary",
    "verdict",
    "score",
    "fairness_verdict",
    "issue_clarity_score",
    "gold_patch_clarity_score",
    "gold_patch_to_issue_alignment_score",
    "test_clarity_score",
    "test_to_issue_alignment_score",
    "fairness_score",
    "instruction_leakage_score",
    "test_robustness_score",
    "is_hint_needed",
    "hint_value",
    "rejection_reasons",
    "json_path",
    "error",
]


def write_task_outputs(
    task: HarborTask,
    grading: GradingTestsOutput,
    result: AnnotationResult,
    output_dir: Path,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_dir = output_dir / "json"
    markdown_dir = output_dir / "markdown"
    json_dir.mkdir(parents=True, exist_ok=True)
    markdown_dir.mkdir(parents=True, exist_ok=True)

    payload = result_payload(task, grading, result)
    json_path = json_dir / f"{task.task_slug}.json"
    markdown_path = markdown_dir / f"{task.task_slug}.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    markdown_path.write_text(result.summary_markdown + "\n")

    row = csv_row(
        task, grading, result, json_path=json_path, status="success", error=""
    )
    single_csv_path = output_dir / f"{task.task_slug}.csv"
    write_csv(single_csv_path, [row])
    return payload


def write_error_output(
    task_dir: Path, output_dir: Path, error: Exception
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_dir = output_dir / "json"
    json_dir.mkdir(parents=True, exist_ok=True)
    slug = task_dir.name
    payload = {
        "status": "failed",
        "task_slug": slug,
        "error": f"{type(error).__name__}: {error}",
    }
    json_path = json_dir / f"{slug}.error.json"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    return payload


def result_payload(
    task: HarborTask, grading: GradingTestsOutput, result: AnnotationResult
) -> dict[str, Any]:
    annotation = result.annotation
    return {
        "status": "success",
        "task_slug": task.task_slug,
        "instance_id": task.instance_id,
        "repo": task.repo,
        "base_commit": task.base_commit,
        "language": task.language,
        "category": task.category,
        "subcategory": task.subcategory,
        "source_type": task.source_type,
        "difficulty": task.difficulty,
        "num_f2p_declared": task.num_f2p_tests,
        "inputs": {
            "task_dir": str(task.task_dir),
            "instruction_path": "instruction.md (or environment/problem_statement.md)",
            "test_patch_source": "tests/test_patch.diff or embedded heredoc in tests/test.sh",
            "test_script_path": "tests/test.sh",
            "gold_patch_path": "solution/golden.patch (or solution/gold_patch.diff)",
        },
        "grading_tests": model_dump(grading),
        "annotation": {
            "verdict": result.verdict,
            "score": result.score,
            "rejection_reasons": result.rejection_reasons,
            "fairness_verdict": result.fairness.overall_verdict,
            "fairness_summary": result.fairness.summary,
            "rubrics": {
                "issue_clarity": model_dump(annotation.issue_clarity),
                "gold_patch_clarity": model_dump(annotation.gold_patch_clarity),
                "gold_patch_to_issue_alignment": model_dump(
                    annotation.gold_patch_to_issue_alignment
                ),
                "test_clarity": model_dump(annotation.test_clarity),
                "test_to_issue_alignment": model_dump(
                    annotation.test_to_issue_alignment
                ),
                "fairness": model_dump(annotation.fairness),
                "instruction_leakage": model_dump(annotation.instruction_leakage),
                "test_robustness": model_dump(annotation.test_robustness),
            },
            "hint": {
                "is_hint_needed": annotation.is_hint_needed,
                "hint_reasoning": annotation.hint_reasoning,
                "hint_value": annotation.hint_value,
            },
        },
        "raw_response": {
            "grading_tests": model_dump(grading),
            "fairness": model_dump(result.fairness),
            "annotation": model_dump(result.annotation),
        },
        "summary_markdown": result.summary_markdown,
    }


def csv_row(
    task: HarborTask,
    grading: GradingTestsOutput,
    result: AnnotationResult,
    *,
    json_path: Path,
    status: str,
    error: str,
) -> dict[str, Any]:
    annotation = result.annotation
    return {
        "status": status,
        "task_slug": task.task_slug,
        "instance_id": task.instance_id,
        "repo": task.repo,
        "base_commit": task.base_commit,
        "language": task.language,
        "category": task.category,
        "subcategory": task.subcategory,
        "source_type": task.source_type,
        "difficulty": task.difficulty,
        "num_f2p_declared": task.num_f2p_tests,
        "f2p_count": len(grading.fail_to_pass),
        "p2p_count": len(grading.pass_to_pass),
        "unknown_test_count": len(grading.unknown),
        "f2p_names": join_names(grading.fail_to_pass),
        "p2p_names": join_names(grading.pass_to_pass),
        "grading_summary": grading.summary,
        "verdict": result.verdict,
        "score": result.score,
        "fairness_verdict": result.fairness.overall_verdict,
        "issue_clarity_score": annotation.issue_clarity.score,
        "gold_patch_clarity_score": annotation.gold_patch_clarity.score,
        "gold_patch_to_issue_alignment_score": annotation.gold_patch_to_issue_alignment.score,
        "test_clarity_score": annotation.test_clarity.score,
        "test_to_issue_alignment_score": annotation.test_to_issue_alignment.score,
        "fairness_score": annotation.fairness.score,
        "instruction_leakage_score": annotation.instruction_leakage.score,
        "test_robustness_score": annotation.test_robustness.score,
        "is_hint_needed": annotation.is_hint_needed,
        "hint_value": annotation.hint_value,
        "rejection_reasons": " | ".join(result.rejection_reasons),
        "json_path": str(json_path),
        "error": error,
    }


def error_csv_row(task_dir: Path, json_path: Path, error: Exception) -> dict[str, Any]:
    row = {field: "" for field in CSV_FIELDS}
    row.update(
        {
            "status": "failed",
            "task_slug": task_dir.name,
            "json_path": str(json_path),
            "error": f"{type(error).__name__}: {error}",
        }
    )
    return row


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as file:
        file.write(json.dumps(payload, ensure_ascii=False) + "\n")


def model_dump(value: BaseModel) -> dict[str, Any]:
    return value.model_dump(mode="json")


def join_names(tests: list) -> str:
    return " | ".join(test.name for test in tests)

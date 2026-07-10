from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated

import typer
from dotenv import load_dotenv

from swebench_like_gen.ai_annotation import AiAnnotationService
from swebench_like_gen.google_sheets import GoogleSheetsClient, SheetsConfig
from swebench_like_gen.grading_test_extractor import GradingTestExtractor
from swebench_like_gen.harbor_loader import iter_harbor_tasks, load_harbor_task
from swebench_like_gen.output_writer import (
    append_jsonl,
    csv_row,
    error_csv_row,
    write_csv,
    write_error_output,
    write_task_outputs,
)

_ = load_dotenv()

app = typer.Typer(no_args_is_help=True)

DEFAULT_MODEL = os.getenv("ANNOTATION_MODEL", "anthropic:claude-sonnet-5")
DEFAULT_EXTRACTOR_MODEL = os.getenv("EXTRACTOR_MODEL")
DEFAULT_OUTPUT_DIR = Path(os.getenv("ANNOTATION_OUTPUT_DIR", "output/ai_annotation"))
EXTRACTOR_MODEL_HELP = "Optional separate PydanticAI model string for F2P/P2P extraction. Defaults to EXTRACTOR_MODEL, then --model."
GOOGLE_SHEETS_CREDENTIALS_PATH = "credentials/drive.json"
SHEETS_CONFIG = SheetsConfig(
    file_id=os.getenv("QUALITY_FILE_ID", ""),
    quality_sheet_name=os.getenv("QUALITY_SHEETS_NAME", ""),
    list_sheet_name=os.getenv("QUALITY_LIST_SHEET_NAME", ""),
    credentials_path=GOOGLE_SHEETS_CREDENTIALS_PATH,
)


@app.command()
def annotate_one(
    task_dir: Annotated[
        Path, typer.Argument(help="Path to one Harbor task directory.")
    ],
    model: Annotated[
        str, typer.Option(help="PydanticAI model string for annotation.")
    ] = DEFAULT_MODEL,
    extractor_model: Annotated[
        str | None, typer.Option(help=EXTRACTOR_MODEL_HELP)
    ] = DEFAULT_EXTRACTOR_MODEL,
    output_dir: Annotated[
        Path, typer.Option(help="Directory for JSON/CSV/Markdown outputs.")
    ] = DEFAULT_OUTPUT_DIR,
) -> None:
    task = load_harbor_task(task_dir)
    typer.echo(f"Extracting grading tests for {task.task_slug}...")
    grading = GradingTestExtractor(extractor_model or model).run(task)
    test_count_message = (
        f"Found {len(grading.fail_to_pass)} F2P, {len(grading.pass_to_pass)} P2P, "
        f"{len(grading.unknown)} unknown tests/selectors."
    )
    typer.echo(test_count_message)

    typer.echo(f"Annotating {task.task_slug}...")
    result = AiAnnotationService(model).run(task, grading)
    payload = write_task_outputs(task, grading, result, output_dir)
    json_path = output_dir / "json" / f"{task.task_slug}.json"
    row = csv_row(
        task, grading, result, json_path=json_path, status="success", error=""
    )
    sync_sheets(with_summary(row, result.summary_markdown), task.task_slug, result.verdict)
    typer.echo(
        json.dumps(
            {
                "status": "success",
                "task_slug": task.task_slug,
                "verdict": result.verdict,
                "score": result.score,
            },
            indent=2,
        )
    )
    typer.echo(f"Wrote {output_dir / 'json' / f'{task.task_slug}.json'}")
    if payload.get("status") != "success":
        raise typer.Exit(code=1)


@app.command()
def annotate_dataset(
    dataset_dir: Annotated[
        Path,
        typer.Argument(help="Path to Harbor dataset directory containing task dirs."),
    ],
    model: Annotated[
        str, typer.Option(help="PydanticAI model string for annotation.")
    ] = DEFAULT_MODEL,
    extractor_model: Annotated[
        str | None, typer.Option(help=EXTRACTOR_MODEL_HELP)
    ] = DEFAULT_EXTRACTOR_MODEL,
    output_dir: Annotated[
        Path, typer.Option(help="Directory for JSON/CSV/JSONL/Markdown outputs.")
    ] = DEFAULT_OUTPUT_DIR,
    limit: Annotated[
        int | None, typer.Option(help="Optional maximum number of tasks to process.")
    ] = None,
    skip_existing: Annotated[
        bool, typer.Option(help="Skip tasks whose JSON output already exists.")
    ] = False,
    fail_fast: Annotated[bool, typer.Option(help="Stop on first failed task.")] = False,
) -> None:
    task_dirs = iter_harbor_tasks(dataset_dir)
    if limit is not None:
        task_dirs = task_dirs[:limit]

    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    jsonl_path = output_dir / "annotations.jsonl"
    extractor = GradingTestExtractor(extractor_model or model)
    annotator = AiAnnotationService(model)

    for index, task_dir in enumerate(task_dirs, start=1):
        slug = task_dir.name
        json_path = output_dir / "json" / f"{slug}.json"
        if skip_existing and json_path.exists():
            typer.echo(f"[{index}/{len(task_dirs)}] Skipping {slug}: output exists")
            continue

        typer.echo(f"[{index}/{len(task_dirs)}] Processing {slug}")
        try:
            task = load_harbor_task(task_dir)
            grading = extractor.run(task)
            result = annotator.run(task, grading)
            payload = write_task_outputs(task, grading, result, output_dir)
            append_jsonl(jsonl_path, payload)
            row = csv_row(
                task, grading, result, json_path=json_path, status="success", error=""
            )
            rows.append(row)
            sync_sheets(with_summary(row, result.summary_markdown), task.task_slug, result.verdict)
            typer.echo(f"  -> {result.verdict} score={result.score}")
        except Exception as exc:
            typer.echo(f"  -> failed: {type(exc).__name__}: {exc}", err=True)
            payload = write_error_output(task_dir, output_dir, exc)
            append_jsonl(jsonl_path, payload)
            error_path = output_dir / "json" / f"{slug}.error.json"
            rows.append(error_csv_row(task_dir, error_path, exc))
            if fail_fast:
                write_csv(output_dir / "annotations.csv", rows)
                raise typer.Exit(code=1) from exc

    write_csv(output_dir / "annotations.csv", rows)
    typer.echo(f"Wrote aggregate CSV: {output_dir / 'annotations.csv'}")
    typer.echo(f"Wrote JSONL: {jsonl_path}")


def with_summary(row: dict[str, object], summary_markdown: str) -> dict[str, object]:
    return {**row, "summary_markdown": summary_markdown}


def sync_sheets(row: dict[str, object], task_slug: str, verdict: str) -> None:
    if not SHEETS_CONFIG.enabled:
        return
    client = GoogleSheetsClient(SHEETS_CONFIG)
    client.upsert_quality_result(row)
    client.update_quality_list_acceptance(task_slug, verdict)


def annotate_one_entry() -> None:
    typer.run(annotate_one)


def annotate_dataset_entry() -> None:
    typer.run(annotate_dataset)


def main() -> None:
    app()

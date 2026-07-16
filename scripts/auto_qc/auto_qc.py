#!/usr/bin/env python3
"""Auto-QC orchestrator for Harbor-format tasks.

Given one Harbor task directory (or a directory of task directories), this tool:

  1. Runs the ARIA-for-Harbor annotation pipeline (the vendored copy under
     ``auto_qc/ARIA-FOR-HARBOR``) with **two independent LLM judges** — by
     default Opus 4.8 (``anthropic:claude-opus-4-8``) and Kimi K2.7 Code
     (``openrouter:moonshotai/kimi-k2.7-code``) — each scoring the task on the
     eight task-quality rubrics (issue clarity, gold-patch clarity,
     gold-patch<->issue alignment, test clarity, test<->issue alignment,
     fairness, instruction leakage, and test robustness) and producing its own
     ``accept``/``reject`` verdict. The two judges are merged into one quality
     verdict (default: both must accept — reject if *either* judge rejects).
  2. Optionally reads a *cheap-model pre-filter* result (e.g. Sonnet5 pass@1
     eval results / trajectory) for each task and derives a difficulty signal.
     A task the cheap model already solves at pass@1 is unlikely to be Hard.
  3. Combines the merged quality verdict with the difficulty signal into a
     single final ``accept``/``reject`` decision with reasons and flags, and
     writes per-task + aggregate output (with per-judge rubric breakdowns).

The ARIA pipeline needs Python 3.13 + uv (deps declared in its pyproject.toml)
and provider API keys configured in the ARIA .env or inherited from the
environment: ``ANTHROPIC_API_KEY`` for the Opus judge and ``OPENROUTER_API_KEY``
for the Kimi (OpenRouter) judge. This orchestrator itself only shells out to
``uv run`` and reads JSON, so it runs on stock Python 3.9+.

Usage:
  python auto_qc.py <task-or-dataset-dir> [--prefilter PATH] [options]

Examples:
  # Two-judge QC of a single task (Opus 4.8 + Kimi K2.7 Code by default):
  python auto_qc.py ../../batch_1/human_authored_tasks/cameroncooke__XcodeBuildMCP-feat_6506

  # QC a whole batch, folding in Sonnet5 pass@1 pre-filter results:
  python auto_qc.py ../../batch_1/human_authored_tasks \
      --prefilter ../../batch_1/prefilter_sonnet5.jsonl --output-dir out/auto_qc

  # Reject anything the cheap model already solves at pass@1 (strict difficulty gate):
  python auto_qc.py <dataset> --prefilter results/ --strict-difficulty

  # Custom judges / merge policy (accept if either judge accepts):
  python auto_qc.py <dataset> --judge-agreement any \
      --judges "opus=anthropic:claude-opus-4-8,kimi=openrouter:moonshotai/kimi-k2.7-code"
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_ARIA_DIR = SCRIPT_DIR / "ARIA-FOR-HARBOR"
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "output"

# Two LLM judges run the rubrics independently. Each entry is
# (name, PydanticAI model string, leakage_max). Opus 4.8 goes through the
# Anthropic API (ANTHROPIC_API_KEY); Kimi K2.7 Code goes through OpenRouter
# (OPENROUTER_API_KEY).
#
# leakage_max is the per-judge instruction_leakage tolerance: the stricter judge
# (Opus) tends to over-flag, so a *minor* leak (score 1) is tolerated
# (leakage_max=1); the lenient judge (Kimi) must see none (leakage_max=0) — if
# even it detects leakage, it's real. A significant leak (score >= 2) rejects for
# either judge.
DEFAULT_JUDGES = [
    ("opus", "anthropic:claude-opus-4-8", 1),
    ("kimi", "openrouter:moonshotai/kimi-k2.7-code", 0),
]

# Rubric keys, in the order ARIA scores them (all 0 = best, 3 = worst).
RUBRIC_KEYS = [
    "issue_clarity",
    "gold_patch_clarity",
    "gold_patch_to_issue_alignment",
    "test_clarity",
    "test_to_issue_alignment",
    "fairness",
    "instruction_leakage",
    "test_false_negatives",
    "test_false_positives",
]

# Keys we look for in a pre-filter record to decide whether the cheap model
# solved the task (pass@1). First match wins.
_SOLVED_BOOL_KEYS = ("resolved", "solved", "passed", "success", "is_resolved")
_SOLVED_NUM_KEYS = ("pass_at_1", "pass@1", "pass_at_k", "reward", "score", "pass_rate")
_STATUS_SOLVED_VALUES = {"resolved", "passed", "pass", "success", "solved", "completed"}


# ---------------------------------------------------------------------------
# Task discovery
# ---------------------------------------------------------------------------
def is_task_dir(path: Path) -> bool:
    return path.is_dir() and (path / "task.toml").is_file()


def discover_task_dirs(root: Path) -> List[Path]:
    root = root.expanduser().resolve()
    if not root.exists():
        raise SystemExit(f"error: path does not exist: {root}")
    if is_task_dir(root):
        return [root]
    if not root.is_dir():
        raise SystemExit(f"error: not a directory: {root}")
    tasks = sorted(p for p in root.iterdir() if is_task_dir(p))
    if not tasks:
        raise SystemExit(
            f"error: no Harbor tasks found under {root} "
            "(expected a task.toml here or in immediate subdirectories)"
        )
    return tasks


# ---------------------------------------------------------------------------
# ARIA quality pass
# ---------------------------------------------------------------------------
def run_aria(
    task_dir: Path,
    aria_dir: Path,
    aria_out: Path,
    model: Optional[str],
    extractor_model: Optional[str],
    reuse_existing: bool,
    leakage_max: int = 0,
) -> Dict[str, Any]:
    """Run ARIA annotate-one on one task and return its parsed JSON payload."""
    slug = task_dir.name
    json_path = aria_out / "json" / f"{slug}.json"
    error_path = aria_out / "json" / f"{slug}.error.json"

    if reuse_existing and json_path.is_file():
        return _read_json(json_path)

    cmd = [
        "uv", "run", "annotate-one", str(task_dir),
        "--output-dir", str(aria_out),
        "--leakage-max", str(leakage_max),
    ]
    if model:
        cmd += ["--model", model]
    if extractor_model:
        cmd += ["--extractor-model", extractor_model]

    proc = subprocess.run(
        cmd, cwd=str(aria_dir), env=os.environ.copy(),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    if json_path.is_file():
        return _read_json(json_path)
    if error_path.is_file():
        payload = _read_json(error_path)
        payload.setdefault("status", "failed")
        return payload
    # No output file: surface the subprocess log so the failure is debuggable.
    return {
        "status": "failed",
        "task_slug": slug,
        "error": (
            f"ARIA did not produce output (exit {proc.returncode}). "
            f"Last output:\n{(proc.stdout or '').strip()[-2000:]}"
        ),
    }


def parse_aria(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Normalise an ARIA JSON payload into the quality block we care about."""
    if payload.get("status") != "success" or "annotation" not in payload:
        return {
            "status": payload.get("status", "failed"),
            "aria_verdict": None,
            "aria_score": None,
            "fairness_verdict": None,
            "rubric_scores": {},
            "rejection_reasons": [],
            "error": payload.get("error", "ARIA annotation did not succeed"),
        }
    ann = payload["annotation"]
    rubrics = ann.get("rubrics", {})
    scores = {
        key: _safe_int(rubrics.get(key, {}).get("score"))
        for key in RUBRIC_KEYS
    }
    return {
        "status": "success",
        "aria_verdict": ann.get("verdict"),
        "aria_score": ann.get("score"),
        "fairness_verdict": ann.get("fairness_verdict"),
        "rubric_scores": scores,
        "rejection_reasons": ann.get("rejection_reasons", []),
        "is_hint_needed": ann.get("hint", {}).get("is_hint_needed"),
        "error": None,
    }


def merge_judge_qualities(
    judges: Dict[str, Dict[str, Any]], agreement: str
) -> Dict[str, Any]:
    """Merge per-judge quality blocks into a single quality verdict.

    ``judges`` maps judge name -> the ``parse_aria`` result for that judge.
    Each judge's "effective verdict" is its ARIA verdict when it succeeded, or
    ``"error"`` when its pipeline failed. The merge policy:

    - ``all``  (default): accept iff **every** judge accepts (any reject/error
      -> reject). This is the conservative, stricter two-judge gate.
    - ``any``: accept iff **at least one** judge accepts.

    Merged rubric scores are the worst (max, since 0 = best / 3 = worst) across
    the succeeding judges, and the merged 0-5 quality score is the worst (min).
    """
    names = list(judges)
    ok = [n for n in names if judges[n].get("status") == "success"]

    # Per-judge effective verdict.
    effective = {
        n: (judges[n].get("aria_verdict") if judges[n].get("status") == "success"
            else "error")
        for n in names
    }

    # Aggregate reasons (prefixed by judge name) for anything not accepting.
    reasons: List[str] = []
    for n in names:
        if effective[n] == "reject":
            reasons.append(f"[{n}] rejected on the quality rubrics.")
            reasons += [f"[{n}] {r}" for r in judges[n].get("rejection_reasons", []) or []]
        elif effective[n] == "error":
            reasons.append(f"[{n}] judge error: {judges[n].get('error')}")

    # If no judge produced a usable annotation, surface a hard pipeline error.
    if not ok:
        return {
            "status": "failed",
            "aria_verdict": None,
            "aria_score": None,
            "fairness_verdict": None,
            "rubric_scores": {},
            "rejection_reasons": reasons,
            "judge_agreement": agreement,
            "judge_verdicts": effective,
            "error": "all judges failed: " + "; ".join(reasons),
        }

    # Worst-case rubric scores across succeeding judges.
    merged_scores: Dict[str, Optional[int]] = {}
    for key in RUBRIC_KEYS:
        vals = [judges[n]["rubric_scores"].get(key) for n in ok]
        vals = [v for v in vals if v is not None]
        merged_scores[key] = max(vals) if vals else None

    score_vals = [
        judges[n].get("aria_score") for n in ok
        if isinstance(judges[n].get("aria_score"), (int, float))
    ]
    merged_score = min(score_vals) if score_vals else None

    fairness_vals = [judges[n].get("fairness_verdict") for n in ok]
    merged_fairness = ("Unfair" if any(fv == "Unfair" for fv in fairness_vals)
                       else ("Fair" if fairness_vals else None))

    if agreement == "any":
        final = "accept" if any(effective[n] == "accept" for n in names) else "reject"
    else:  # "all": every judge must accept
        final = "accept" if all(effective[n] == "accept" for n in names) else "reject"

    return {
        "status": "success",
        "aria_verdict": final,
        "aria_score": merged_score,
        "fairness_verdict": merged_fairness,
        "rubric_scores": merged_scores,
        "rejection_reasons": reasons,
        "judge_agreement": agreement,
        "judge_verdicts": effective,
        "error": None,
    }


# ---------------------------------------------------------------------------
# Cheap-model difficulty pre-filter
# ---------------------------------------------------------------------------
def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def load_prefilter_index(prefilter: Optional[Path]) -> Dict[str, Dict[str, Any]]:
    """Build a normalised {task-key -> record} index from a pre-filter input.

    Accepts a .jsonl file (one record per line), a .json file (a mapping keyed
    by task id, or a list of records, or a single record), or a directory of
    per-task JSON files (``<slug>.json`` or ``<slug>/*.json``).
    """
    if prefilter is None:
        return {}
    prefilter = prefilter.expanduser().resolve()
    if not prefilter.exists():
        raise SystemExit(f"error: --prefilter path does not exist: {prefilter}")

    records: List[Dict[str, Any]] = []
    if prefilter.is_dir():
        for path in sorted(prefilter.rglob("*.json")):
            rec = _read_json_safe(path)
            if isinstance(rec, dict):
                rec.setdefault("_task_key", path.parent.name if path.stem in
                               ("result", "results", "eval", "report") else path.stem)
                records.append(rec)
    elif prefilter.suffix == ".jsonl":
        for line in prefilter.read_text().splitlines():
            line = line.strip()
            if line:
                rec = json.loads(line)
                if isinstance(rec, dict):
                    records.append(rec)
    else:
        data = _read_json(prefilter)
        if isinstance(data, list):
            records = [r for r in data if isinstance(r, dict)]
        elif isinstance(data, dict):
            # A mapping {task_id: record} or a single record.
            looks_like_map = all(isinstance(v, dict) for v in data.values()) and data
            if looks_like_map:
                for key, rec in data.items():
                    rec = dict(rec)
                    rec.setdefault("_task_key", key)
                    records.append(rec)
            else:
                records = [data]

    index: Dict[str, Dict[str, Any]] = {}
    for rec in records:
        for key in _record_keys(rec):
            index.setdefault(_norm(key), rec)
    return index


def _record_keys(rec: Dict[str, Any]) -> List[str]:
    keys = []
    for field in ("_task_key", "task_slug", "slug", "instance_id",
                  "task_id", "id", "name", "task"):
        val = rec.get(field)
        if isinstance(val, str) and val.strip():
            keys.append(val)
    return keys


def match_prefilter(
    index: Dict[str, Dict[str, Any]], slug: str, instance_id: str
) -> Optional[Dict[str, Any]]:
    if not index:
        return None
    for candidate in (slug, instance_id):
        if candidate:
            rec = index.get(_norm(candidate))
            if rec is not None:
                return rec
    return None


def interpret_prefilter(rec: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Turn a pre-filter record into a difficulty signal."""
    if rec is None:
        return {
            "available": False,
            "solved_pass_at_1": None,
            "pass_rate": None,
            "signal": "unknown",
            "model": None,
            "trajectory_path": None,
        }

    solved: Optional[bool] = None
    pass_rate: Optional[float] = None

    for key in _SOLVED_BOOL_KEYS:
        if key in rec and isinstance(rec[key], bool):
            solved = rec[key]
            break
    if solved is None:
        status = rec.get("status") or rec.get("verdict")
        if isinstance(status, str) and _norm(status) in {
            _norm(v) for v in _STATUS_SOLVED_VALUES
        }:
            solved = True
        elif isinstance(status, str) and status.strip():
            solved = False
    for key in _SOLVED_NUM_KEYS:
        if key in rec and isinstance(rec[key], (int, float)) and not isinstance(rec[key], bool):
            pass_rate = float(rec[key])
            if solved is None:
                solved = pass_rate >= 1.0 if key in ("pass_at_1", "pass@1") else pass_rate > 0.0
            break

    if solved is True:
        signal = "too_easy_candidate"
    elif solved is False:
        signal = "plausibly_hard"
    else:
        signal = "unknown"

    return {
        "available": True,
        "solved_pass_at_1": solved,
        "pass_rate": pass_rate,
        "signal": signal,
        "model": rec.get("model") or rec.get("cheap_model") or "cheap-model",
        "trajectory_path": rec.get("trajectory") or rec.get("trajectory_path"),
    }


# ---------------------------------------------------------------------------
# Combined verdict
# ---------------------------------------------------------------------------
def combine_verdict(
    quality: Dict[str, Any], difficulty: Dict[str, Any], strict_difficulty: bool
) -> Dict[str, Any]:
    reasons: List[str] = []
    flags: List[str] = []

    if quality["status"] != "success":
        return {
            "final_verdict": "reject",
            "reasons": [f"quality: ARIA pipeline error — {quality.get('error')}"],
            "flags": ["aria_error"],
        }

    if quality["aria_verdict"] == "reject":
        reasons.append("quality: ARIA rejected the task on the quality rubrics.")
        reasons += [f"quality gate: {r}" for r in quality.get("rejection_reasons", [])]
        return {"final_verdict": "reject", "reasons": reasons, "flags": flags}

    # Quality passed; now weigh the difficulty pre-filter.
    if difficulty["signal"] == "too_easy_candidate":
        note = (
            f"difficulty: cheap model ({difficulty.get('model')}) solved the task at "
            "pass@1 — unlikely to be Hard; verify the difficulty band before shipping."
        )
        if strict_difficulty:
            reasons.append(note + " Rejected under --strict-difficulty.")
            return {"final_verdict": "reject", "reasons": reasons, "flags": flags}
        flags.append("difficulty_concern: " + note)
    elif difficulty["signal"] == "unknown":
        flags.append(
            "no_prefilter: no cheap-model pass@1 result available; difficulty not screened."
        )

    reasons.append("quality: ARIA accepted the task on all quality rubrics.")
    return {"final_verdict": "accept", "reasons": reasons, "flags": flags}


# ---------------------------------------------------------------------------
# IO helpers
# ---------------------------------------------------------------------------
def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text())


def _read_json_safe(path: Path) -> Any:
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def task_metadata(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "instance_id": payload.get("instance_id", ""),
        "repo": payload.get("repo", ""),
        "language": payload.get("language", ""),
        "category": payload.get("category", ""),
        "subcategory": payload.get("subcategory", ""),
        "source_type": payload.get("source_type", ""),
        "difficulty": payload.get("difficulty", ""),
        "num_f2p_declared": payload.get("num_f2p_declared", 0),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Auto-QC: run ARIA quality rubrics + cheap-model difficulty "
        "pre-filter over Harbor tasks and emit accept/reject verdicts.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("tasks", type=Path,
                   help="A Harbor task directory OR a directory of task directories.")
    p.add_argument("--prefilter", type=Path, default=None,
                   help="Cheap-model (e.g. Sonnet5 pass@1) eval results: a .jsonl, "
                        ".json (map/list/record), or a directory of per-task JSON.")
    p.add_argument("--aria-dir", type=Path, default=DEFAULT_ARIA_DIR,
                   help="Path to the ARIA-for-Harbor project (default: vendored copy).")
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR,
                   help="Where to write auto-QC + ARIA outputs.")
    p.add_argument("--judges", default=None,
                   help="Comma-separated 'name=model[#leakage_max]' judge specs "
                        "(PydanticAI model strings; optional '#N' sets the per-judge "
                        "instruction_leakage tolerance, default 0). Default: two judges — "
                        "opus=anthropic:claude-opus-4-8#1 (tolerates a minor leak), "
                        "kimi=openrouter:moonshotai/kimi-k2.7-code#0 (must be leak-free).")
    p.add_argument("--judge-agreement", choices=("all", "any"), default="all",
                   help="How to merge the two judges: 'all' = accept only if every "
                        "judge accepts (default, stricter); 'any' = accept if any does.")
    p.add_argument("--model", default=None,
                   help="Shortcut for a single-judge run (overrides --judges): the "
                        "ARIA annotation model as a PydanticAI model string.")
    p.add_argument("--extractor-model", default=None,
                   help="Override ARIA F2P/P2P extractor model (shared by all judges).")
    p.add_argument("--strict-difficulty", action="store_true",
                   help="Reject tasks the cheap model solves at pass@1 (too-easy gate).")
    p.add_argument("--reuse-existing", action="store_true",
                   help="Reuse an existing ARIA JSON for a task instead of re-running it.")
    p.add_argument("--limit", type=int, default=None,
                   help="Only process the first N tasks.")
    return p


def parse_judges(args: argparse.Namespace) -> List[tuple]:
    """Resolve the (name, model, leakage_max) judge list from CLI args.

    ``--model`` (single-judge shortcut) wins over ``--judges``; if neither is
    given we fall back to the two default judges (Opus 4.8 + Kimi K2.7 Code) with
    their built-in per-judge leakage tolerances. Custom judges default to the
    strict leakage gate (leakage_max=0); append ``#N`` to a spec to override,
    e.g. ``opus=anthropic:claude-opus-4-8#1``.
    """
    if args.model:
        return [("model", args.model, 0)]
    if args.judges:
        judges: List[tuple] = []
        for spec in args.judges.split(","):
            spec = spec.strip()
            if not spec:
                continue
            leakage_max = 0
            if "#" in spec:
                spec, _, leak = spec.rpartition("#")
                try:
                    leakage_max = int(leak)
                except ValueError:
                    raise SystemExit(
                        f"error: --judges leakage suffix '#{leak}' must be an integer."
                    )
            if "=" not in spec:
                raise SystemExit(
                    f"error: --judges entry '{spec}' must be 'name=model' (opt '#N')."
                )
            name, model = spec.split("=", 1)
            name, model = name.strip(), model.strip()
            if not name or not model:
                raise SystemExit(
                    f"error: --judges entry '{spec}' must be 'name=model' (opt '#N')."
                )
            judges.append((name, model, leakage_max))
        if not judges:
            raise SystemExit("error: --judges produced no valid judge specs.")
        return judges
    return list(DEFAULT_JUDGES)


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)

    aria_dir = args.aria_dir.expanduser().resolve()
    if not (aria_dir / "pyproject.toml").is_file():
        raise SystemExit(f"error: ARIA project not found at {aria_dir}")

    judge_specs = parse_judges(args)

    task_dirs = discover_task_dirs(args.tasks)
    if args.limit is not None:
        task_dirs = task_dirs[: args.limit]

    output_dir = args.output_dir.expanduser().resolve()
    aria_out = output_dir / "aria"
    autoqc_dir = output_dir / "autoqc"
    autoqc_dir.mkdir(parents=True, exist_ok=True)

    prefilter_index = load_prefilter_index(args.prefilter)
    if args.prefilter is not None:
        print(f"Loaded {len(prefilter_index)} pre-filter key(s) from {args.prefilter}")

    judge_desc = ", ".join(
        f"{name}={model} (leak<= {leak})" for name, model, leak in judge_specs
    )
    print(f"Judges ({args.judge_agreement} must accept): {judge_desc}")

    results: List[Dict[str, Any]] = []
    for idx, task_dir in enumerate(task_dirs, start=1):
        slug = task_dir.name
        print(f"[{idx}/{len(task_dirs)}] {slug}: running ARIA quality pass "
              f"({len(judge_specs)} judge(s))...")

        # Each judge runs the full ARIA pipeline with its own model, writing to
        # a per-judge output dir so the two annotations don't collide.
        judges_quality: Dict[str, Any] = {}
        judge_paths: Dict[str, str] = {}
        meta: Dict[str, Any] = {}
        for name, model, leakage_max in judge_specs:
            judge_out = aria_out / name
            payload = run_aria(
                task_dir, aria_dir, judge_out,
                model, args.extractor_model, args.reuse_existing,
                leakage_max=leakage_max,
            )
            judges_quality[name] = parse_aria(payload)
            judge_paths[name] = str(judge_out / "json" / f"{slug}.json")
            # Prefer metadata from a judge whose ARIA run actually produced it.
            if not meta.get("instance_id"):
                meta = task_metadata(payload)
            jq = judges_quality[name]
            print(f"      · {name} ({model}): verdict={jq.get('aria_verdict')} "
                  f"score={jq.get('aria_score')} status={jq.get('status')}")

        quality = merge_judge_qualities(judges_quality, args.judge_agreement)
        prefilter_rec = match_prefilter(
            prefilter_index, slug, meta.get("instance_id", "")
        )
        difficulty = interpret_prefilter(prefilter_rec)
        combined = combine_verdict(quality, difficulty, args.strict_difficulty)

        record = {
            "task_slug": slug,
            "task_dir": str(task_dir),
            "final_verdict": combined["final_verdict"],
            "reasons": combined["reasons"],
            "flags": combined["flags"],
            "metadata": meta,
            "quality": {
                **quality,
                "judges": judges_quality,
                "judge_json_paths": judge_paths,
            },
            "difficulty_prefilter": difficulty,
        }
        results.append(record)

        out_path = autoqc_dir / f"{slug}.autoqc.json"
        out_path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n")

        verdict = combined["final_verdict"].upper()
        score = quality.get("aria_score")
        print(f"    -> {verdict} (merged quality={quality.get('aria_verdict')} "
              f"score={score} | difficulty={difficulty['signal']})")

    write_summary(results, output_dir)
    accepts = sum(1 for r in results if r["final_verdict"] == "accept")
    print(f"\nAuto-QC complete: {accepts}/{len(results)} accepted.")
    print(f"Per-task JSON:  {autoqc_dir}")
    print(f"Summary:        {output_dir / 'auto_qc_summary.json'}")
    print(f"                {output_dir / 'auto_qc_summary.csv'}")
    return 0


def write_summary(results: List[Dict[str, Any]], output_dir: Path) -> None:
    (output_dir / "auto_qc_summary.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n"
    )

    # Judge names present across the run (union, stable order of first sight).
    judge_names: List[str] = []
    for r in results:
        for name in r["quality"].get("judges", {}):
            if name not in judge_names:
                judge_names.append(name)

    per_judge_fields: List[str] = []
    for name in judge_names:
        per_judge_fields += [f"{name}_verdict", f"{name}_score", f"{name}_fairness"]
        per_judge_fields += [f"{name}_rubric_{k}" for k in RUBRIC_KEYS]

    fields = [
        "task_slug", "final_verdict", "aria_verdict", "judge_agreement",
        "aria_score", "fairness_verdict",
        *[f"rubric_{k}" for k in RUBRIC_KEYS],
        *per_judge_fields,
        "difficulty_signal", "cheap_model_solved",
        "language", "category", "subcategory", "source_type",
        "flags", "reasons",
    ]
    with (output_dir / "auto_qc_summary.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            q = r["quality"]
            d = r["difficulty_prefilter"]
            row = {
                "task_slug": r["task_slug"],
                "final_verdict": r["final_verdict"],
                "aria_verdict": q.get("aria_verdict"),
                "judge_agreement": q.get("judge_agreement"),
                "aria_score": q.get("aria_score"),
                "fairness_verdict": q.get("fairness_verdict"),
                "difficulty_signal": d.get("signal"),
                "cheap_model_solved": d.get("solved_pass_at_1"),
                "language": r["metadata"].get("language"),
                "category": r["metadata"].get("category"),
                "subcategory": r["metadata"].get("subcategory"),
                "source_type": r["metadata"].get("source_type"),
                "flags": " | ".join(r["flags"]),
                "reasons": " | ".join(r["reasons"]),
            }
            for k in RUBRIC_KEYS:
                row[f"rubric_{k}"] = q.get("rubric_scores", {}).get(k)
            judges = q.get("judges", {})
            for name in judge_names:
                jq = judges.get(name, {})
                row[f"{name}_verdict"] = jq.get("aria_verdict") or jq.get("status")
                row[f"{name}_score"] = jq.get("aria_score")
                row[f"{name}_fairness"] = jq.get("fairness_verdict")
                jscores = jq.get("rubric_scores", {})
                for k in RUBRIC_KEYS:
                    row[f"{name}_rubric_{k}"] = jscores.get(k)
            writer.writerow(row)


if __name__ == "__main__":
    sys.exit(main())

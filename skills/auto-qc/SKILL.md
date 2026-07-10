---
name: auto-qc
description: >-
  Auto-QC a Harbor-format task (or a set of tasks) before shipping: run the
  ARIA-for-Harbor annotation pipeline to score the task on the eight task-quality
  rubrics (issue clarity, gold-patch clarity, gold-patch<->issue alignment, test
  clarity, test<->issue alignment, fairness, instruction leakage, test robustness),
  optionally fold in a cheap-model pre-filter (e.g. Sonnet5 pass@1 eval results /
  trajectory) as a difficulty signal, and emit a single accept/reject verdict with
  rubric scores, reasons, and flags per task. Use when asked to auto-QC, quality-gate,
  vet, screen, or accept/reject Harbor tasks with ARIA, or to combine ARIA quality
  scores with a cheap-model difficulty pre-filter.
---

# Auto-QC (ARIA quality + cheap-model difficulty pre-filter)

Take a Harbor-format task (or a directory of tasks) and decide **accept** or
**reject** by combining two signals:

1. **Quality** — the ARIA-for-Harbor pipeline scores the task on eight quality
   rubrics and returns its own `accept`/`reject` verdict (this is the primary gate).
2. **Difficulty** — an optional cheap-model pre-filter (e.g. Sonnet5 pass@1 eval
   results/trajectory). A task the cheap model already solves at pass@1 is unlikely
   to be Hard, per the requirements spec, so it is flagged (or rejected under a
   strict gate).

The orchestrator and the (vendored, already-modified) ARIA pipeline live under:

```
scripts/auto_qc/
  auto_qc.py                 # the orchestrator (runs on stock Python 3.9+)
  README.md
  ARIA-FOR-HARBOR/           # the ARIA pipeline it drives (Python 3.13 + uv)
```

## When to use

- After a task is authored in Harbor format (see `task_spec_to_harbor_task`) and
  ideally after a cheap-model pre-filter eval has run, to gate it before delivery.
- To QC a whole batch and get an accept/reject table + rubric scores.

## Inputs

- **Required**: a path to ONE Harbor task dir (contains `task.toml`) OR a directory
  whose immediate subdirectories are task dirs. The shipped format is expected:
  `task.toml`, `instruction.md`, `environment/{Dockerfile,problem_statement.md}`,
  `solution/{golden.patch,solve.sh}`, `tests/test.sh` (the hidden fail2pass test
  patch is embedded inline in `test.sh`).
- **Optional**: `--prefilter PATH` — cheap-model pass@1 results. Accepts:
  - a `.jsonl` (one record per line),
  - a `.json` (a `{task_id: record}` map, a list of records, or a single record),
  - a directory of per-task JSON files (`<slug>.json` or `<slug>/*.json`).
  Records are matched to tasks by any of `task_slug` / `instance_id` / `task_id` /
  `id` / `name` (fuzzy, case/separator-insensitive). "Solved" is read from any of
  `resolved`/`solved`/`passed`/`success` (bool), a `status`/`verdict` string, or a
  numeric `pass_at_1`/`reward`/`score`/`pass_rate`. If no record matches a task, its
  difficulty signal is `unknown` (quality gate still applies).

## Prerequisites (one-time)

- `uv` installed, and the ARIA env synced: `cd scripts/auto_qc/ARIA-FOR-HARBOR && uv sync`.
- A provider key for ARIA's annotation model. Either export `ANTHROPIC_API_KEY`
  (inherited by the subprocess) or create `scripts/auto_qc/ARIA-FOR-HARBOR/.env`
  from `.env.example`. Default model is `anthropic:claude-sonnet-5`; override with
  `--model` / `--extractor-model`.

## Workflow

1. **Confirm the task path(s)** and whether a cheap-model pre-filter exists. If it
   does, locate the results file/dir and pass it via `--prefilter`.
2. **Run the orchestrator** from `scripts/auto_qc/`:

```bash
# single task
python auto_qc.py <path-to-task> --output-dir out

# a batch, with a Sonnet5 pass@1 pre-filter
python auto_qc.py <path-to-dataset> --prefilter <sonnet5_pass1.jsonl> --output-dir out

# strict difficulty gate: reject anything the cheap model solves at pass@1
python auto_qc.py <path-to-dataset> --prefilter <results/> --strict-difficulty
```

   Per task it runs `uv run annotate-one` inside `ARIA-FOR-HARBOR`, reads the ARIA
   JSON, matches the pre-filter record, and computes the combined verdict.
   Use `--reuse-existing` to reuse an already-written ARIA JSON instead of re-running
   (saves API cost when iterating), and `--limit N` to sample a batch.
3. **Read the outputs** under `--output-dir`:
   - `autoqc/<slug>.autoqc.json` — full per-task record (final verdict, reasons,
     flags, all 8 rubric scores, fairness verdict, difficulty signal, metadata).
   - `auto_qc_summary.json` / `auto_qc_summary.csv` — one row per task.
   - `aria/json/<slug>.json` + `aria/markdown/<slug>.md` — raw ARIA annotation.
4. **Interpret the verdict** (see below) and report the accept/reject decision per
   task, quoting the rubric scores and the reasons/flags for any rejection.

## Verdict logic

- **Quality is the primary gate.** If ARIA rejects (any rubric ≥ 2, two or more
  rubrics ≥ 1, gold-patch↔issue alignment ≥ 1, test clarity ≥ 2, test↔issue
  alignment ≥ 2, fairness `Unfair`, instruction leakage ≥ 2, or test robustness ≥ 2)
  → **final = reject** with the failing gates listed.
- **Difficulty modulates an otherwise-accepted task.** If ARIA accepts:
  - cheap model solved at pass@1 → default: **accept** with a `difficulty_concern`
    flag (verify the band); with `--strict-difficulty`: **reject**.
  - cheap model failed → **accept** (consistent with Medium/Hard).
  - no pre-filter → **accept** with a `no_prefilter` flag (difficulty not screened).
- ARIA pipeline error for a task → **reject** with an `aria_error` flag (inspect the
  ARIA log / re-run that task).

## The eight quality rubrics (0 = best, 3 = worst)

`issue_clarity`, `gold_patch_clarity`, `gold_patch_to_issue_alignment`,
`test_clarity`, `test_to_issue_alignment`, `fairness`, `instruction_leakage`,
`test_robustness`. The last two encode the spec's emphases:

- **instruction_leakage** — the statement must describe the problem, not the fix;
  no "Where to look: [files]", no root cause / intended fix / algorithm, and no
  hidden-test details — unless that info was in the original upstream issue.
- **test_robustness** — a comprehensive (~10–20 F2P), behaviour-based, regression-
  backed suite that resists reward hacking: no structural/diff/keyword assertions,
  no coupling to the reference solution.

## Modifying the rubrics

The rubrics and gates live in
`scripts/auto_qc/ARIA-FOR-HARBOR/src/swebench_like_gen/ai_annotation.py`
(prompts, `AnnotationOutput`, `rubric_scores`, `annotation_decision`, `GATE_LINES`).
If you add/adjust a rubric, also update `output_writer.py` (payload + CSV) and the
`RUBRIC_KEYS` list in `auto_qc.py`. Keep the top-level
`reflection_task_gen/ARIA-FOR-HARBOR` copy in sync if you change the vendored one.

## Notes / constraints

- Auto-QC never modifies task directories; it only reads them.
- ARIA does not execute the task's Docker verifier — it is an LLM annotation of the
  instruction/patch/tests. Deterministic build+apply+test validation is a separate
  step (see `task_spec_to_harbor_task/scripts/verify.sh`).
- Auto-QC is a screen, not a replacement for human QA on borderline/accepted tasks.

# Auto-QC

Quality-gate Harbor-format tasks by combining the **ARIA-for-Harbor** annotation
pipeline (task-quality rubrics) with an optional **cheap-model difficulty
pre-filter** (e.g. Sonnet5 pass@1) into a single `accept` / `reject` verdict.

```
auto_qc.py            # orchestrator (stock Python 3.9+)
ARIA-FOR-HARBOR/      # the ARIA pipeline it drives (Python 3.13 + uv)
output/               # default output dir (created on run)
```

## Setup

```bash
cd ARIA-FOR-HARBOR && uv sync            # one-time: install ARIA deps
# provide a provider key (inherited by the subprocess) OR create ARIA-FOR-HARBOR/.env
export ANTHROPIC_API_KEY=sk-ant-...
```

## Run

```bash
# single task
python auto_qc.py <path-to-task-dir> --output-dir out

# a batch of tasks + a Sonnet5 pass@1 pre-filter
python auto_qc.py <path-to-dataset-dir> --prefilter <sonnet5_pass1.jsonl> --output-dir out

# reject anything the cheap model already solves at pass@1
python auto_qc.py <dataset> --prefilter <results/> --strict-difficulty
```

Key options: `--model` / `--extractor-model` (override ARIA models),
`--reuse-existing` (reuse an already-written ARIA JSON instead of re-running),
`--limit N`, `--aria-dir PATH`.

## Inputs

- **tasks**: a Harbor task dir (has `task.toml`) or a dir of such task dirs. The
  loader reads the shipped format — `solution/golden.patch`, the fail2pass test
  patch embedded in `tests/test.sh`, and `instruction.md` /
  `environment/problem_statement.md`.
- **--prefilter** (optional): cheap-model pass@1 results as `.jsonl`, `.json`
  (map / list / single record), or a directory of per-task JSON. Matched to tasks
  by `task_slug` / `instance_id` / `task_id` / `id` / `name`. "Solved" is read from
  `resolved`/`solved`/`passed`/`success` (bool), a `status`/`verdict` string, or a
  numeric `pass_at_1`/`reward`/`score`/`pass_rate`.

## Outputs (under `--output-dir`)

- `autoqc/<slug>.autoqc.json` — final verdict, reasons, flags, all 8 rubric scores,
  fairness verdict, difficulty signal, task metadata.
- `auto_qc_summary.json` / `auto_qc_summary.csv` — one row per task.
- `aria/json/<slug>.json`, `aria/markdown/<slug>.md` — raw ARIA annotation.

## Verdict

Quality is the primary gate: if ARIA rejects, the task is rejected. If ARIA accepts,
the difficulty pre-filter modulates it — a task solved by the cheap model at pass@1
is flagged (`difficulty_concern`) or, with `--strict-difficulty`, rejected. No
pre-filter → accepted with a `no_prefilter` flag. See the `auto-qc` skill for the
full logic and the eight quality rubrics.

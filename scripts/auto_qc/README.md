# Auto-QC

Quality-gate Harbor-format tasks by combining the **ARIA-for-Harbor** annotation
pipeline — run by **two independent LLM judges** (Opus 4.8 via the Anthropic API and
Kimi K2.7 Code via OpenRouter) on the task-quality rubrics — with an optional
**cheap-model difficulty pre-filter** (e.g. Sonnet5 pass@1) into a single
`accept` / `reject` verdict.

```
auto_qc.py            # orchestrator (stock Python 3.9+)
ARIA-FOR-HARBOR/      # the ARIA pipeline it drives (Python 3.13 + uv)
output/               # default output dir (created on run)
```

## Setup

```bash
cd ARIA-FOR-HARBOR && uv sync            # one-time: install ARIA deps
# provide BOTH judge keys (inherited by the subprocess) OR create ARIA-FOR-HARBOR/.env
export ANTHROPIC_API_KEY=sk-ant-...       # opus judge  (anthropic:claude-opus-4-8)
export OPENROUTER_API_KEY=sk-or-...       # kimi judge  (openrouter:moonshotai/kimi-k2.7-code)
```

## Run

```bash
# single task (two default judges: opus + kimi)
python auto_qc.py <path-to-task-dir> --output-dir out

# a batch of tasks + a Sonnet5 pass@1 pre-filter
python auto_qc.py <path-to-dataset-dir> --prefilter <sonnet5_pass1.jsonl> --output-dir out

# reject anything the cheap model already solves at pass@1
python auto_qc.py <dataset> --prefilter <results/> --strict-difficulty

# accept if EITHER judge accepts (looser gate)
python auto_qc.py <dataset> --judge-agreement any

# custom judge set
python auto_qc.py <dataset> --judges "opus=anthropic:claude-opus-4-8,kimi=openrouter:moonshotai/kimi-k2.7-code"
```

Key options: `--judges "name=model[#leakage_max],..."` (set the judge panel; the
optional `#N` sets that judge's `instruction_leakage` tolerance — default two judges are
`opus=…#1`, `kimi=…#0`), `--judge-agreement all|any` (merge policy; default `all` = both
must accept), `--model` (single-judge shortcut), `--extractor-model` (shared F2P/P2P
extractor), `--reuse-existing` (reuse an already-written ARIA JSON instead of re-running),
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

- `autoqc/<slug>.autoqc.json` — final verdict, reasons, flags, merged (worst-case)
  rubric scores, difficulty signal, task metadata, and a `quality.judges` block with
  each judge's own verdict, score, fairness, and 9 rubric scores.
- `auto_qc_summary.json` / `auto_qc_summary.csv` — one row per task, with merged
  columns plus per-judge `<name>_verdict/_score/_fairness/_rubric_*` columns.
- `aria/<judge>/json/<slug>.json`, `aria/<judge>/markdown/<slug>.md` — each judge's
  raw ARIA annotation.

## Verdict

Quality is the primary gate, decided by two judges: with `--judge-agreement all`
(default) the task is rejected if **either** judge rejects (merged rubric scores are
the worst-case across judges); `any` accepts if either judge accepts. Each judge's
accept rule requires none of `issue_clarity`/`test_to_issue_alignment`/
`test_false_negatives`/`test_false_positives`/`fairness` ≥ 2, at most 2 of those four
test/fairness rubrics at 1, and `instruction_leakage` within the judge's tolerance
(**asymmetric**: opus ≤ 1, kimi = 0; ≥ 2 rejects either). If both judges'
pipelines error → rejected with `aria_error`. If the merged quality accepts, the
difficulty pre-filter modulates it — a task solved by the cheap model at pass@1 is
flagged (`difficulty_concern`) or, with `--strict-difficulty`, rejected. No
pre-filter → accepted with a `no_prefilter` flag. See the `auto-qc` skill for the
full logic and the nine quality rubrics.

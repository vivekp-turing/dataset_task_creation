---
name: auto-qc
description: >-
  Auto-QC a Harbor-format task (or a set of tasks) before shipping: run the
  ARIA-for-Harbor annotation pipeline with TWO independent LLM judges (Opus 4.8 via
  the Anthropic API and Kimi K2.7 Code via OpenRouter) to score the task on the nine
  task-quality rubrics (issue clarity, gold-patch clarity, gold-patch<->issue
  alignment, test clarity, test<->issue alignment, fairness, instruction leakage,
  test false negatives, test false positives), merge the two judges into one quality
  verdict, optionally fold in
  a cheap-model pre-filter (e.g. Sonnet5 pass@1 eval results / trajectory) as a
  difficulty signal, and emit a single accept/reject verdict with per-judge rubric
  scores, reasons, and flags per task. Use when asked to auto-QC, quality-gate, vet,
  screen, or accept/reject Harbor tasks with ARIA, or to combine ARIA quality scores
  with a cheap-model difficulty pre-filter.
---

# Auto-QC (two-judge ARIA quality + cheap-model difficulty pre-filter)

Take a Harbor-format task (or a directory of tasks) and decide **accept** or
**reject** by combining two signals:

1. **Quality** — the ARIA-for-Harbor pipeline is run by **two independent LLM
   judges**, each scoring the task on the nine quality rubrics and returning its
   own `accept`/`reject` verdict:
   - **opus** — `anthropic:claude-opus-4-8` (Opus 4.8 via the Anthropic API).
   - **kimi** — `openrouter:moonshotai/kimi-k2.7-code` (Kimi K2.7 Code via OpenRouter).

   The two judges are merged into one quality verdict. Default policy is **`all`**
   (accept only if *both* judges accept; reject if *either* rejects) — this is the
   primary gate. `--judge-agreement any` accepts if either judge accepts.
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
- Provider keys for **both** default judges. Either export them (inherited by the
  subprocess) or set them in `scripts/auto_qc/ARIA-FOR-HARBOR/.env` (from `.env.example`):
  - `ANTHROPIC_API_KEY` → the **opus** judge (`anthropic:claude-opus-4-8`).
  - `OPENROUTER_API_KEY` → the **kimi** judge (`openrouter:moonshotai/kimi-k2.7-code`).
  Override the judge set with `--judges "name=model,..."`, run a single judge with
  `--model`, and change the shared F2P/P2P extractor with `--extractor-model`.

## Workflow

1. **Confirm the task path(s)** and whether a cheap-model pre-filter exists. If it
   does, locate the results file/dir and pass it via `--prefilter`.
2. **Run the orchestrator** from `scripts/auto_qc/`:

```bash
# single task (two default judges: opus + kimi)
python auto_qc.py <path-to-task> --output-dir out

# a batch, with a Sonnet5 pass@1 pre-filter
python auto_qc.py <path-to-dataset> --prefilter <sonnet5_pass1.jsonl> --output-dir out

# strict difficulty gate: reject anything the cheap model solves at pass@1
python auto_qc.py <path-to-dataset> --prefilter <results/> --strict-difficulty

# looser quality gate: accept if EITHER judge accepts
python auto_qc.py <path-to-dataset> --judge-agreement any
```

   Per task, for **each judge** it runs `uv run annotate-one --model <judge-model>`
   inside `ARIA-FOR-HARBOR` (writing to a per-judge output dir), reads that judge's
   ARIA JSON, then merges the judges, matches the pre-filter record, and computes the
   combined verdict. Use `--reuse-existing` to reuse an already-written ARIA JSON
   instead of re-running (saves API cost when iterating), and `--limit N` to sample.
3. **Read the outputs** under `--output-dir`:
   - `autoqc/<slug>.autoqc.json` — full per-task record: final verdict, reasons,
     flags, merged (worst-case) rubric scores, and a `quality.judges` block with each
     judge's own verdict, score, fairness, and all 9 rubric scores.
   - `auto_qc_summary.json` / `auto_qc_summary.csv` — one row per task, with merged
     columns plus per-judge `<name>_verdict/_score/_fairness/_rubric_*` columns.
   - `aria/<judge>/json/<slug>.json` + `aria/<judge>/markdown/<slug>.md` — each
     judge's raw ARIA annotation.
4. **Interpret the verdict** (see below) and report the accept/reject decision per
   task, quoting the per-judge rubric scores and the reasons/flags for any rejection.

## Verdict logic

- **Quality is the primary gate, decided by two judges.** Each judge produces its own
  ARIA `accept`/`reject`. A single judge **accepts** iff all of the following hold:
  - none of `issue_clarity`, `test_to_issue_alignment`, `test_false_negatives`,
    `test_false_positives`, `fairness` scores ≥ 2;
  - at most **2** of {`test_to_issue_alignment`, `test_false_negatives`,
    `test_false_positives`, `fairness`} score exactly 1 (3+ ones → reject);
  - `instruction_leakage` is within that judge's tolerance (see below).

  **Per-judge `instruction_leakage` tolerance.** The gate is asymmetric across the two
  default judges: the stricter judge (**opus**) tends to over-flag, so a *minor* leak
  (`instruction_leakage = 1`) is tolerated (`leakage_max = 1`); the more lenient judge
  (**kimi**) must see **none** (`leakage_max = 0`) — if even it flags leakage, it's real.
  A **significant** leak (`instruction_leakage ≥ 2`) rejects for either judge. Custom
  `--judges` default to strict (`leakage_max = 0`); append `#N` to a spec to override
  (e.g. `opus=anthropic:claude-opus-4-8#1`).

  `gold_patch_clarity`, `gold_patch_to_issue_alignment`, and `test_clarity` are scored
  for information but do **not** gate; the binary fairness pipeline is likewise
  informational (the 0–3 `fairness` rubric is the gate). With the default
  `--judge-agreement all`, the merged quality verdict is **reject** if *either* judge
  rejects (or errors); `any` accepts if *either* judge accepts. Merged rubric scores
  are the worst-case (max) across judges and the merged 0–5 score is the worst (min).
  A merged quality `reject` → **final = reject** with each failing judge's gates listed.
- **Difficulty modulates an otherwise-accepted task.** If ARIA accepts:
  - cheap model solved at pass@1 → default: **accept** with a `difficulty_concern`
    flag (verify the band); with `--strict-difficulty`: **reject**.
  - cheap model failed → **accept** (consistent with Medium/Hard).
  - no pre-filter → **accept** with a `no_prefilter` flag (difficulty not screened).
- If a single judge's ARIA pipeline errors, it counts as a non-accept for that judge
  (so under `all` it forces a reject, with the error in the reasons). If **both**
  judges error, the task → **reject** with an `aria_error` flag (inspect the ARIA
  log / re-run that task).

## The nine quality rubrics (0 = best, 3 = worst)

`issue_clarity`, `gold_patch_clarity`, `gold_patch_to_issue_alignment`,
`test_clarity`, `test_to_issue_alignment`, `fairness`, `instruction_leakage`,
`test_false_negatives`, `test_false_positives`. The gating ones encode the spec's
emphases:

- **instruction_leakage** (gate: per-judge — opus ≤ 1, kimi = 0; ≥ 2 always rejects) —
  the statement must describe the problem, not the fix; no "Where to look: [files]",
  no root cause / intended fix / algorithm, and no hidden-test details — unless that
  info was in the original upstream issue.
- **test_false_negatives** (*inability to accept valid solutions*) — the tests must
  not over-specify or pin one implementation such that a valid, correct solution
  fails. High score = brittle / over-fit tests.
- **test_false_positives** (*ability to catch invalid solutions*) — a comprehensive,
  behaviour-based, regression-backed suite that resists reward hacking: no
  structural/diff/keyword assertions, no coupling to the reference solution. High
  score = thin / gameable tests a non-fix could pass.

(`test_false_positives` replaces the former single `test_robustness` rubric, which is
now split into the two false-negative / false-positive axes so the gate can score them
independently.)

## Modifying the rubrics

The rubrics and gates live in
`scripts/auto_qc/ARIA-FOR-HARBOR/src/swebench_like_gen/ai_annotation.py`
(prompts, `AnnotationOutput`, `rubric_scores`, `annotation_decision`, and the
`HARD_GATE_KEYS` / `ONES_GATE_KEYS` / `MAX_ONES` gate constants).
If you add/adjust a rubric, also update `output_writer.py` (payload + CSV) and the
`RUBRIC_KEYS` list in `auto_qc.py`. The per-judge `instruction_leakage` tolerance is
threaded via `annotate-one --leakage-max` (set per judge in `DEFAULT_JUDGES` in
`auto_qc.py`, consumed by `annotation_decision`). Keep the top-level
`reflection_task_gen/ARIA-FOR-HARBOR` copy in sync if you change the vendored one.

## Notes / constraints

- Auto-QC never modifies task directories; it only reads them.
- ARIA does not execute the task's Docker verifier — it is an LLM annotation of the
  instruction/patch/tests. Deterministic build+apply+test validation is a separate
  step (see `task_spec_to_harbor_task/scripts/verify.sh`).
- Auto-QC is a screen, not a replacement for human QA on borderline/accepted tasks.

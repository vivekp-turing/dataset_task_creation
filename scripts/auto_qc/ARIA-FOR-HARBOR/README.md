# SWE-bench-like Harbor Annotation

CLI tools for running AI quality annotation over Harbor-style SWE-bench-like tasks.

The pipeline is adapted from `sweloop`'s AI annotation flow while keeping the strict rubric/fairness prompts. The only major input difference is that Harbor tasks do not provide explicit `FAIL_TO_PASS` / `PASS_TO_PASS` lists, so this project first asks an LLM to extract those grading tests from the Harbor verifier files.

## Harbor task layout

A task directory is expected to look like the current shipped Harbor format:

```text
<task_slug>/
  task.toml
  instruction.md
  environment/Dockerfile
  environment/problem_statement.md
  solution/solve.sh
  solution/golden.patch
  tests/test.sh
```

The loader reads:

- `task.toml` for task id, repo, base commit, language, and taxonomy metadata
  (`category`, `subcategory`, `source_type`, `difficulty`, `num_f2p_tests`)
- `instruction.md` (or `environment/problem_statement.md` as fallback) as the public problem statement
- `tests/test.sh` as verifier context
- the hidden grading test patch — from `tests/test_patch.diff` if present, otherwise
  recovered from the diff embedded inline in `tests/test.sh` (the shipped format keeps
  the tests/ folder to ≤3 files, so the patch is usually a heredoc inside `test.sh`)
- `solution/golden.patch` (or legacy `solution/gold_patch.diff`) as the reference solution

Language is detected by scanning `task.toml` keywords/tags for a known language
(the leading `"code"`/`"swe"` keywords are ignored).

## Pipeline

For each task:

1. Load Harbor files from disk.
2. Run an LLM pre-step to extract:
   - `fail_to_pass`
   - `pass_to_pass`
   - `unknown` tests/selectors
3. Run the strict AI fairness pass.
4. Run the strict eight-rubric annotation pass.
5. Save local JSON/CSV/Markdown output.
6. Optionally sync successful results to Google Sheets.

### Quality rubrics

Each task is scored on nine rubrics (0 = best, 3 = worst), aligned with the dataset
task-quality bar:

1. `issue_clarity` — is the problem statement clear and unambiguous?
2. `gold_patch_clarity` — is the reference solution readable?
3. `gold_patch_to_issue_alignment` — does the patch address exactly the issue (no bundling/chaining)?
4. `test_clarity` — are the tests understandable and free of hidden assertions?
5. `test_to_issue_alignment` — do the F2P tests validate what the issue requires?
6. `fairness` — is the task solvable from public information alone?
7. `instruction_leakage` — does the instruction over-specify or leak the fix, files, algorithm,
   or hidden test details (unless present in the original upstream issue)?
8. `test_false_negatives` — do the tests wrongly REJECT valid solutions (over-strict / pin one
   implementation)?
9. `test_false_positives` — can a non-fix / gamed solution PASS (thin, structural, or
   solution-coupled tests)? (behaviour-based, regression-backed, reward-hacking-resistant = 0)

A task is accepted iff none of `issue_clarity` / `test_to_issue_alignment` /
`test_false_negatives` / `test_false_positives` / `fairness` scores ≥ 2, at most two of those
four test/fairness rubrics score 1, and `instruction_leakage` is within tolerance. The leakage
tolerance is set per invocation via `--leakage-max` (default 0 = must be leak-free; the Auto-QC
orchestrator passes `1` for the stricter Opus judge and `0` for the lenient Kimi judge; a score
≥ 2 always rejects). `gold_patch_clarity`, `gold_patch_to_issue_alignment`, and `test_clarity`
are scored for information but do not gate.

## Setup

Install dependencies with `uv`:

```bash
uv sync
```

Dependencies are managed in `pyproject.toml`. Add new dependencies with `uv add`, not by manually editing dependency lists.

## Environment configuration

Create a `.env` file from the example:

```bash
cp .env.example .env
```

Example:

```env
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
GOOGLE_API_KEY=
GEMINI_API_KEY=

ANNOTATION_MODEL=anthropic:claude-sonnet-5
EXTRACTOR_MODEL=anthropic:claude-sonnet-5
ANNOTATION_OUTPUT_DIR=output/ai_annotation

QUALITY_FILE_ID=
QUALITY_SHEETS_NAME=
QUALITY_LIST_SHEET_NAME=
```

### Model configuration

`ANNOTATION_MODEL` is used for the fairness and rubric annotation passes.

`EXTRACTOR_MODEL` is used for the F2P/P2P extraction pre-step. If unset, it falls back to `ANNOTATION_MODEL`.

You can also override both on the command line:

```bash
uv run annotate-one "data/harbor_tasks 2/click" \
  --model google:gemini-3-flash-preview \
  --extractor-model google:gemini-3-flash-preview
```

Provider keys are read from the environment by `pydantic-ai`. Use the key required by your selected model/provider.

## Commands

### Annotate one task

```bash
uv run annotate-one "data/harbor_tasks 2/click"
```

Options:

```bash
uv run annotate-one --help
```

Common overrides:

```bash
uv run annotate-one "data/harbor_tasks 2/click" --output-dir output/ai_annotation
uv run annotate-one "data/harbor_tasks 2/click" --model openai:gpt-4.1
uv run annotate-one "data/harbor_tasks 2/click" --extractor-model openai:gpt-4.1-mini
```

### Annotate a dataset

```bash
uv run annotate-dataset "data/harbor_tasks 2"
```

Useful options:

```bash
uv run annotate-dataset "data/harbor_tasks 2" --limit 5
uv run annotate-dataset "data/harbor_tasks 2" --skip-existing
uv run annotate-dataset "data/harbor_tasks 2" --fail-fast
```

## Local outputs

Default output directory:

```text
output/ai_annotation
```

For one task, outputs include:

```text
output/ai_annotation/json/<task_slug>.json
output/ai_annotation/markdown/<task_slug>.md
output/ai_annotation/<task_slug>.csv
```

For dataset runs, aggregate outputs include:

```text
output/ai_annotation/annotations.csv
output/ai_annotation/annotations.jsonl
```

Failed tasks write:

```text
output/ai_annotation/json/<task_slug>.error.json
```

## Google Sheets sync

Google Sheets sync is optional. It is enabled only when `QUALITY_FILE_ID` is set and at least one of these is set:

```env
QUALITY_SHEETS_NAME=
QUALITY_LIST_SHEET_NAME=
```

### Credentials

The Google Sheets service account credentials path is hardcoded in code, not read from `.env`.

Set this constant in `src/swebench_like_gen/cli.py`:

```python
GOOGLE_SHEETS_CREDENTIALS_PATH = ""
```

The service account must have access to the spreadsheet. If the spreadsheet is in a Shared Drive, share the file with the service account or add the service account to the Shared Drive.

### `QUALITY_SHEETS_NAME`

If set, successful annotation rows are upserted into that sheet by `task_slug`.

The Google Sheets schema is based on the local CSV fields, except:

- `json_path` is omitted
- `error` is omitted
- `summary_markdown` is added

### `QUALITY_LIST_SHEET_NAME`

If set, the tool searches that sheet for the task slug in column B.

It writes the acceptance result to column E:

- `TRUE` when final verdict is `accept`
- `FALSE` when final verdict is `reject`

Example task ids in column B:

```text
keras
promptfoo
click
```

## Data subsets

A passed subset can live at:

```text
data/harbor_passed
```

You can annotate that subset directly:

```bash
uv run annotate-dataset data/harbor_passed
```

## Notes

- The source Harbor dataset may be gitignored; commands read it from disk.
- The task directories are never modified by the annotation commands.
- Local output is written under `output/ai_annotation` unless overridden.
- Google Sheets sync only happens after successful local annotation output is produced.

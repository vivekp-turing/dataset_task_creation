# Task tagging — `tag_task.py`

Tag a SWE-Bench-style / Harbor-format task with a **category**, **subcategory**, and
**primary language**, using an LLM (Anthropic Claude) as a judge. The taxonomy is the
one from the Reflection task-requirements spec (the "Distribution requirements" section).

## What it does

Given a task, it builds a consolidated context (problem statement, golden patch, tests,
repo/metadata), sends it to Claude with the full taxonomy, and returns a JSON object:

- `categories` — a confidence score in `[0,1]` for **every** one of the 11 categories.
- `subcategories` — for **every** category, its **top-3** subcategories with scores.
- `languages` — confidence scores for the candidate languages.
- `objective_labels` / `artifact_labels` — the multi-label objective/artifact taxonomies
  (bonus metadata the spec also requires per task).
- `final_decision` — the three chosen values:
  - `category` = highest-scoring category,
  - `subcategory` = highest-scoring subcategory **within that chosen category**,
  - `language` = highest-scoring language.
- `rationale` — a short justification.

All category/subcategory/language names returned by the model are canonicalized against
the fixed taxonomy, so the output is always a valid label.

## Install

```bash
pip install -r requirements.txt
```

`ANTHROPIC_API_KEY` is read from the environment or the nearest `.env` file (the script
walks up from the task path, the script dir, and the cwd). You can also pass
`--env-file /path/to/.env`.

## Input formats

- **Harbor task folder** — a directory containing `instruction.md`,
  `environment/problem_statement.md`, `task.toml`, `solution/golden.patch`, `tests/…`.
- **SWE-Bench JSON file** — an object (or list of objects) with fields like
  `problem_statement`, `patch` / `golden_patch`, `test_patch`, `hints_text`, `repo`,
  `instance_id`.
- **Plain text / markdown file** — treated as a raw problem statement.

## Usage

```bash
# Harbor task folder -> stdout
python tag_task.py ../../batch_1/human_authored_tasks/cameroncooke__XcodeBuildMCP-feat_6506

# Write to a file, pick a model
python tag_task.py ./instance.json --output tagged.json --model claude-opus-4-8

# Inspect the exact prompt without calling the API
python tag_task.py ./task_dir --print-prompt
```

Default model is `claude-sonnet-5` (override with `--model` or the `TAG_TASK_MODEL`
env var). For the hardest judgments use `claude-opus-4-8`.

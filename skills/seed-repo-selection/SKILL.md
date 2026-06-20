---
name: seed-repo-selection
description: >-
  Select high-quality SEED REPOS (not tasks) from a Turing/SWE-Bench long-range
  metadata spreadsheet, filtered against the task requirements, and
  write a deduped candidate list to CSV for authoring ORIGINAL tasks. Use when
  asked to pick/narrow down seed repos from the SWE-Bench dataset sheet for
  the task spec, choose candidate repos per language, or build a high-quality repo
  shortlist by language coverage and task-creation criteria.
disable-model-invocation: true
---

# Seed-Repo Selection

Pick the best **repositories** (not the sheet's existing tasks) from a
Turing/SWE-Bench long-range metadata `.xlsx`, so a human can author **original**
tasks (per the task spec) from them. Output is a deduped CSV: one row per repo.

## Key intent (do not violate)

- Select **distinct repos**, NOT tasks. Dedupe by `repo`; never emit two rows
  from the same repository.
- The sheet's tasks are reference only. The CSV keeps `example_instance_id` /
  `example_pr_url` purely as evidence the repo yields suitable work — the user
  must build new tasks, not reuse those PRs.
- Counts and language coverage are **inputs**, never hardcoded.

## Quick start

```bash
python scripts/select_seed_repos.py \
  --xlsx "<path>/Turing SWEBench Public Dataset (...).xlsx" \
  --out  "<path>/seed_repos.csv" \
  --per-language 15 \
  --languages "JS/TS,Python,Java,C#"
```

This picks 15 repos per group across 4 groups (60 total). Change the number and
languages freely. For uneven counts use `--lang-counts`:

```bash
python scripts/select_seed_repos.py --xlsx "<sheet>.xlsx" --out seed.csv \
  --lang-counts "JS/TS=20,Python=15,Java=10,Go=5"
```

## Inputs

| Flag | Meaning |
|------|---------|
| `--per-language N` | repos per group (the "15" / "any number") |
| `--languages "A,B,C"` | language groups to cover (high-level coverage input) |
| `--lang-counts "A=10,B=5"` | per-group counts; overrides the two above |
| `--sheet` | sheet name; auto-detects the raw `instance_id` sheet if omitted |

Language groups map to raw sheet `language` values. `JS/TS` = JavaScript +
TypeScript; `C/C++` = C + C++. Any single sheet language works directly (Go,
Rust, Ruby, C#, PHP, etc.). Per the task spec, the top-4 by spec % are
`JS/TS, Python, Java, C#`.

## What the sheet columns mean

- `instance_loc` = LoC of **one task's gold patch** (per-task change size).
  The task spec targets ~100 LoC across multiple files; the filter band centers here.
- `loc` = **total repo size** in LoC. `999999` is a sentinel for unknown/huge
  repos — excluded by default to respect the <100 MB Git-image rule.
- `f2p_count` / `p2p_count` = fail2pass / pass2pass test counts.
- `difficulty_score` (1–3), `stars`, `code_type_primary`, `issue_type_primary`.

## Selection logic (maps to the task requirements)

Quality gate (all tunable via flags):
- `instance_loc` in `[60, 350]` — ~100-LoC multi-file patches.
- `f2p_count >= 3` — robust, end-to-end-validatable tests.
- `stars >= 250` — maturity/quality bar.
- drop `loc == 999999` sentinel and `loc > 2,000,000` — image-size safety.
- `code_type_primary` ∈ {feature, bug-fix, refactor} — feature impl + bug fixes.

Ranking score: closeness to the `instance_loc` sweet spot, higher difficulty,
popularity (capped), test coverage, plus a **bug-fix bonus** so the shortlist
keeps a feature/bug-fix mix. Then dedupe to one repo each.

## Tuning thresholds

Loosen if a group falls short (the script prints `SHORTFALL`):

```bash
--min-stars 150 --min-f2p 1 --max-instance-loc 450 --allow-loc-sentinel
```

Thin-language note: niche languages (e.g. C#, PHP, Ruby) have small pools; the
eligible count printed per group shows the headroom. If `picked < want`, loosen
filters rather than silently shipping fewer.

## Workflow

```
- [ ] 1. Confirm language groups + count(s) with the user (don't assume)
- [ ] 2. Run scripts/select_seed_repos.py with those inputs
- [ ] 3. Read the per-group summary; if any SHORTFALL, loosen filters and rerun
- [ ] 4. Report the picks grouped by language with quality signals
- [ ] 5. Flag thin languages and any low-f2p / sentinel-loc entries to re-validate
```

## Output CSV columns

`lang_group, repo, repo_full_name, language, instance_loc, repo_loc, stars,
f2p_count, p2p_count, difficulty_score, code_type_primary, issue_type_primary,
repo_type_primary, long_horizon_tag, example_instance_id, example_pr_url`

`example_*` are reference only — never reuse them as tasks.

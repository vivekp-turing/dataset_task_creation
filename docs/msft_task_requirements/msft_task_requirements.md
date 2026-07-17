# MSFT Batch — Task Requirements

This is the **batch task-requirements file** for the MSFT batch (the
`docs/<client>_task_requirements.md` referenced by the repo `README.md`). It is the
**single source of truth** for this batch and overrides the pipeline defaults.

## Core requirements (this batch)

1. **Source type — net-new only.** Every task in this batch must be **strictly net-new**:
   an original feature/capability or a real edge-case gap that is **genuinely absent at the
   pinned base SHA**. Tasks must **not** be derived from an existing PR, commit, or issue,
   and must **not** be a seeded regression. `source_type = net-new` for 100% of tasks in
   this batch.

2. **Gold-patch size — > 600 LoC.** The `solution/golden.patch` must contain a
   **source-only** diff of **more than 600 lines of code (LoC > 600)**. This is a **hard
   floor**, not an average:
   - Counted as **added + modified source lines** in `golden.patch` (net-new authored code).
   - **Test code is excluded** from the count — the F2P test patch and any test-only files
     do not contribute to the 600 LoC.
   - Generated/vendored/lockfile/binary churn does not count toward the floor.
   - The patch must remain **multi-file** (touch **≥ 3 non-test files**), so the 600+ LoC
     reflects genuine cross-module work rather than one bloated file.

## Baseline requirements

These are like the repo defaults:

- **Approved repos only** — author tasks solely from `docs/turing_approved_repos.txt`
  (hard gate). Prefer larger / multi-module repos that can plausibly support a 600+ LoC
  net-new gold patch.
- **F2P suite** — a comprehensive deterministic offline `fail2pass` suite with a hard
  floor of **> 5 F2P tests (min 5)**; the repo's existing suite is the `pass2pass`
  regression guard. Aim for ~10–20 F2P tests or more where feasible to prevent reward
  hacking.
- **Difficulty target — ~100% Hard**, measured as **pass@8** in the models'
  native harnesses (Codex + Claude Code):
  - **Medium** — GPT-5.5 or Opus 4.8 solves `≤ 4/8`.
  - **Hard** — GPT-5.5 or Opus 4.8 solves `≤ 2/8`.
- **Offline & image** — no internet at setup/eval/runtime; with an
  offline Docker build; `.git` present, `HEAD` == base commit, no future commits / reflog /
  remote.
- **Harbor submission format** — `instruction.md`, `task.toml` (with full `[metadata]`,
  including `source_type = "net-new"` and the `pass_at_k_*` fields), `environment/`,
  `solution/golden.patch` + `solve.sh`, and `tests/`.
- **No leakage / behavior-only instructions** — the problem statement describes behavior
  only: no file lists, test names, root-cause hints, or implementation steps.
- **Taxonomy & diversity** — assign category/subcategory + objective/artifact labels and
  respect the batch-level distribution and diversity caps.

## Quick summary

| Requirement            | This batch          |
|------------------------|---------------------|
| Source type            | net-new (100%)      |
| Gold-patch LoC (source)| **> 600** (hard floor) |
| Non-test files touched for golden patch | ≥ 3                 |
| F2P tests              | > 5 (min 5)         |
| Difficulty             | 100% Hard (pass@8) |

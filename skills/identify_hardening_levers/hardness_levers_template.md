# Hardness levers — `<task-slug>`

> The per-task diagnosis + prescription produced by the `identify_hardening_levers` skill,
> and the contract `implement_hardening_levers` treats against. The identify skill fills the
> Header → Candidate levers → Combined predicted impact. The implement skill fills the
> Rebuild + validation plan and the Iteration log as it doses the cure. Every claim in
> "Why it's easy" cites eval evidence (`step_id` / verifier hole); every lever is
> TASK-SPECIFIC, ROI-ranked, and carries its requirement + rubric-safety checks and a
> predicted pass@8 impact. Fill every field; delete the parenthetical guidance.

## Header

- **Task:** `<owner>/<repo>-<slug>` · path `<task_dir>`
- **Difficulty target:** `Hard (≤2/8)` | `Medium (≤4/8)`
- **Source type / base SHA:** `<PR|commit|issue-based | derivation | net-new>` @ `<BASE_SHA>`
- **Category / subcategory:** `<…>` (unchanged, or note the re-tag)
- **Before-signals (baseline to beat):**
  - Phase 5 — Sonnet 5 pass@1: `<solved | failed>` (trial: `<path>`)
  - Phase 7 — pass@8: Opus 4.8 (Claude Code) `x/8` · GPT-5.5 (Codex) `x/8`
- **Hardening severity:** `light | moderate | severe`  — (justify from the numbers above)

## Why it's easy (diagnosis — evidence-grounded)

(1–3 diagnosed causes from the catalog: A single-obvious-fix / B leaked-instruction /
C weak-verifier / D too-small-scope / E contamination / F copyable-analogue. For each, one
short paragraph citing the evidence — the passing trajectory `step_id`s + snippet showing
the short path to a pass, or the exact verifier hole / naive fix that scored.)

- **Cause `<X>` — `<name>`:** `<what the trajectories/verifier show; step_ids + snippet>`
- …

## Candidate levers (ROI-ranked)

(One block per lever, **ordered by ROI = difficulty added ÷ change+risk** — highest first.
This is a menu, not a mandate: `implement_hardening_levers` applies the smallest top-ROI
subset that closes the gap. Levers must be able to combine coherently — one motivated
engineering task, not stapled subtasks.)

### Lever 1 — ROI `<high|med|low>` · `<catalog id, e.g. A1>` · `<one-line name for THIS task>`
- **Concrete change (this task):** `<exact subsystem/files/edge-cases/tests to change;
  what the golden must now do; which NEW F2P cases to add and what they assert>`
- **What it touches:** `<instruction only | tests only | tests + golden | instruction +
  tests + golden>` (drives how invasive the cure is)
- **Why it's hard:** `<the specific reasoning it now forces — interaction / exact spec /
  non-local invariant / cross-module consistency / diagnosis-from-behavior>`
- **Requirements check:** golden avg ~350 LoC / multi-file `<ok?>`; NEW F2P count → `<n>`
  (target 10–20, no new pass2pass); deterministic + offline `<ok?>`; source-type still
  valid at base SHA `<ok?>`; `<100 MB` image `<ok?>`.
- **Rubric-safety check:** test↔issue alignment `<why aligned>`; coverage/robustness
  `<outcome-based, adversarial, not solution-coupled>`; fairness/realism `<plausible ask>`;
  not underspecified `<engineer can still find the surface>`; no over-strict/false-negative
  `<golden + other correct solutions still pass>`; no leakage `<no file/fix/test hints>`.
- **Predicted pass@8 impact:** `<+ / ++ / +++>` — `<one line: which model attempts this
  now breaks, and why>`

### Lever 2 — ROI `<…>` · …
(repeat, descending ROI)

## Combined predicted impact

- **Gap to close:** `<current worse-of pass@8 vs the target band; e.g. Hard target, Opus
  4/8 → must reach ≤2/8>`.
- **Recommended dose (advisory):** `<the top-ROI subset expected to close the gap; the
  implement skill confirms empirically>`.
- **Expected post-harden signals:** Sonnet 5 pass@1 `<fail (required for Hard)>`;
  Opus 4.8 `≈ x/8`; GPT-5.5 `≈ x/8` → lands in `<Hard | Medium>` band.
- **Rationale:** `<how the levers compound; which is the primary driver; residual risk
  it's still slightly easy or now slightly unfair>`

## Rebuild + validation plan (for `<task_dir>_v2`)

- **Build:** apply levers via `task_spec_to_harbor_task` conventions — rebuild
  `solution/golden.patch` (source-only), re-embed widened fail2pass patch inline in
  `tests/test.sh`, update `instruction.md` + `environment/problem_statement.md`, bump
  `task.toml [metadata].num_f2p_tests` + `difficulty_explanation`.
- **Solvability guard (no false negative):** golden/`solve.sh` → verifier reward `1`.
- **Naive-fails guard (lever bit):** reconstruct the eval agent's quick fix from the
  trajectory; the hardened verifier now rejects it. `<which fix, expected to fail on which
  new case>`
- **Format/leak guard:** `task_spec_to_harbor_task/scripts/verify.sh <slug>` clean.
- **Re-eval:** Phase 5 (Sonnet 5 pass@1) → Phase 6 (auto-qc must stay `accept`) → Phase 7
  (pass@8 Opus 4.8 + GPT-5.5 on Daytona; record `pass_at_k_*`). If out of band or unfair →
  `_v3` and adjust; loop.

## Iteration log (append per version)

| Version | Levers applied | Sonnet p@1 | Opus p@8 | GPT-5.5 p@8 | auto-qc | Notes |
|---|---|---|---|---|---|---|
| v1 (orig) | — | `<>` | `<>` | `<>` | `<>` | baseline / too easy |
| v2 | `<ids>` | `<>` | `<>` | `<>` | `<>` | `<in band? fair?>` |

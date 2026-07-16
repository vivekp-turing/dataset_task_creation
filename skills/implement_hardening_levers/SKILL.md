---
name: implement_hardening_levers
description: >-
  ADMINISTER the cure for an easy Harbor (SWE-Bench-style fail2pass) task — the
  implementation half of the hardening loop. Reads the hardness_levers.md prescription from
  identify_hardening_levers, diagnoses HOW MUCH difficulty the task actually needs (the gap
  between its current pass-rate and the Hard/Medium band), and applies the SMALLEST top-ROI
  subset of levers that closes that gap — not all of them. Acts as a task-hardness doctor:
  apply the minimal dose, re-measure, add the next-highest-ROI lever only if still too easy.
  When a lever changes the problem statement it cascades the required edits — modifying the
  fail2pass tests and/or the golden solution to stay consistent — while preserving every
  task requirement and quality/realism rubric (test↔issue alignment, coverage, fairness,
  not underspecified, no over-strict/false-negative tests, no leakage). Works on a NEW task
  version (never in place), validates both directions (golden still passes; the previously
  easy fix now fails), and re-runs Phase 5/6/7. Use when asked to harden/implement/apply
  hardness levers, make a task harder from its hardness_levers.md, or "cure" a task that a
  cheap or frontier model solved too easily.
---

# Implement hardening levers (the task-hardness doctor)

You're handed a task that's **too easy** plus its **`hardness_levers.md`** prescription
(from **[`identify_hardening_levers`](../identify_hardening_levers/)**). Your job is to
**cure the difficulty problem with the minimal effective dose**: apply the highest-ROI
levers needed to move the task into its target band, re-measure, and stop as soon as it's
in-band, fair, and still solvable. You are treating a patient, not rewriting the task —
change only what the diagnosis demands, and only as much as the eval evidence requires.

The task is a Harbor SWE-Bench-style task in this pipeline's format: `instruction.md`,
`task.toml`, `environment/{Dockerfile,problem_statement.md}`, `solution/{golden.patch,
solve.sh}`, `tests/test.sh` (fail2pass patch embedded inline). Build edits follow the
**[`task_spec_to_harbor_task`](../task_spec_to_harbor_task/)** conventions.

## The bar you're curing toward (from the batch task-requirements file)

The **batch task-requirements file** (e.g. `docs/<client>_task_requirements.md`) sets the
gate — target models, reward@k band, and reasoning effort. Cure toward *that* band; the
values below are **defaults** used only when no requirements file is supplied, and its
`hardness_levers.md` prescription already encodes the concrete target.

**Default gate:** difficulty is **pass@8** in the models' native harnesses, classified by
the worse (higher) solve rate: **Hard** = Opus 4.8 / GPT-5.5 ≤ 2/8; **Medium** = ≤ 4/8. A
**Hard**-target task must also make **Sonnet 5 fail pass@1** (Phase 5). If the batch gate
is **two-sided** (e.g. xAI: 1/8 ≤ Grok-4.5 reward@8 ≤ 6/8 at xhigh), move the pass-rate
*into* the band without dropping below its floor. The lower pass-rate must come from the
task being genuinely harder — reasoning/cross-module/subtlety/domain — while it stays
**fair, realistic, and solvable**, with the verifier aligned to the instruction and **no
false negatives**. You have NOT cured it until a re-run shows the pass-rate is in band.

## Core principle — minimal effective dose (ROI-first, gap-driven)

The prescription lists candidate levers ROI-ranked. **Do not apply them all.** Apply the
fewest, highest-ROI levers that plausibly close the *gap*, then measure. Dosing rule of
thumb (the identify spec's severity + gap set the starting dose):

| Gap to band | Starting dose |
|---|---|
| **Just over** (e.g. Hard target, 3–4/8; Medium, 5–6/8) | the **single** top-ROI lever (usually a verifier/edge or de-leak lever). Measure; add one more only if needed. |
| **Well over** (Hard target ≥5/8) | the top-ROI lever **+** one surface-deepening lever. |
| **Sonnet solves pass@1** (severe) | at least one surface-deepening lever **+** a verifier lever; verifier-only will not cure a fundamentally easy surface. |

Prefer low-blast-radius levers first (instruction/tests) before invasive ones (golden
scope growth), because every extra change is extra risk to solvability, realism, and the
rubrics. **Add levers one at a time and re-measure** so each pass-rate move is attributable.

## Inputs

- **Required** — the task at `<task_dir>/` and its prescription
  `tasks/<slug>/hardness_levers.md` (header, ROI-ranked levers, gap, what each lever
  touches, predicted impact).
- **Required** — the easiness signal the prescription is based on (Phase-5 Sonnet 5 pass@1
  and/or Phase-7 pass@8 run dirs) so you can reconstruct the agent's easy fix and confirm
  the cure blocks it.
- **Helpful** — the task's `auto-qc` output so you don't regress a quality rubric; the
  original `task_spec_*.md`; the repo clone at the base SHA for rebuilding patches.

If no `hardness_levers.md` exists, run `identify_hardening_levers` first — this skill treats
a diagnosis, it doesn't create one.

## Workflow

```
- [ ] 1. Read hardness_levers.md + confirm the target band, the GAP, and the ROI order.
- [ ] 2. Pick the DOSE: the smallest top-ROI lever subset for the gap (dosing table above).
- [ ] 3. Branch a new version: cp -r <task_dir> <task_dir>_v2 (never edit in place).
- [ ] 4. Apply the chosen levers in dependency order, cascading edits across the three
        artifacts (instruction → tests → golden) so they stay consistent.
- [ ] 5. Validate BOTH directions locally: golden still passes; the previously-easy fix +
        naive/partial now FAIL; requirements + separation + non-leak all hold.
- [ ] 6. Re-eval: Phase 5 (Sonnet 5 pass@1) → Phase 6 (auto-qc) → Phase 7 (pass@8).
- [ ] 7. If still out of band → add the NEXT-highest-ROI lever in <task_dir>_v3 and repeat.
        If now UNFAIR (false negative / ambiguity / leakage / flaky) → back off / fix.
        Stop when in-band + fair + solvable. Log each version in hardness_levers.md.
```

### Step 4 — apply levers + cascade edits across the three artifacts

This is the part that makes it a doctor and not a text editor: **a change to one artifact
usually forces changes to the others.** Keep them consistent every time.

- **If the instruction/problem statement changes** (de-leak B1, broaden objective B2,
  scope-growth D1): update BOTH `instruction.md` and `environment/problem_statement.md`
  identically. If the objective genuinely widened, the **tests must cover the new
  behavior** and the **golden must implement it** — do not widen the ask without widening
  both. If you only de-leaked (removed hints), tests/golden usually stay as-is.
- **If the verifier changes** (edge matrix A1, exact-spec A2/C2, invariant A3, regression
  C1, tamper-close C3): rebuild the **NEW fail2pass test patch** (edit tests in the clone →
  diff → reset clone → re-embed inline in `tests/test.sh`). Then confirm the **existing
  golden still satisfies the new tests**; if a new assertion exposes a real gap the golden
  didn't cover, the **golden must be extended** to handle it (never weaken the test to fit
  a thin golden). Bump `task.toml [metadata].num_f2p_tests`.
- **If scope grows** (D1 cross-module, D2 round-trip, E1 re-base, F1 adaptation): rebuild
  `solution/golden.patch` as **source-only** across the added files (keep it within the
  batch file's LoC band — default avg ~350 LoC, ≈150–800; e.g. xAI > 1000 LoC — multi-file,
  grow coherently, never staple unrelated changes), re-embed
  `solve.sh`, AND widen the tests to assert the new behavior. Re-verify `source_type`
  validity at the base SHA; for PR-based tasks keep matching the **canonical upstream fix**.
- **Always** update `task.toml [metadata].difficulty` / `difficulty_explanation` to reflect
  the new hardness, and keep the two patches cleanly separated (golden = source-only; test
  patch = tests-only, embedded in `test.sh`). Leave the clone clean.

Every applied lever must still pass its **rubric-safety check** from the prescription — you
are tightening the *bar*, never pinning an implementation or hiding the goal.

### Step 5 — validate both directions (local, before spending on eval)

- **Solvability guard (no false negative).** Apply `solution/golden.patch` (or run
  `solution/solve.sh`) and confirm the (widened) verifier writes reward `1`. If scope grew,
  the golden grew with it and still passes. If it doesn't pass, the cure is broken — fix
  the golden/tests, don't ship.
- **Cure-bit guard (no false positive).** Reconstruct the **exact quick fix the eval agent
  used** (from the trajectory the prescription cites) and any obvious naive/partial fix;
  confirm the hardened verifier now **rejects** them. This proves the lever actually bit.
- **Format / separation / leak checks.** Run
  `../task_spec_to_harbor_task/scripts/verify.sh <slug>`: golden applies at base SHA,
  test patch applies, golden is source-only, instruction non-leaking, clone clean.

### Step 6 — re-eval (the only proof the dose worked)

1. **Phase 5** — cheap-model pass@1 pre-filter (default Sonnet 5, Claude Code). For a
   Hard target it must now **fail**. (Skip if the batch gate has no cheap pre-filter.)
2. **Phase 6** — `auto-qc`: must stay **accept** (no quality rubric regressed by the cure).
3. **Phase 7** — reward@k with the batch file's **target models + k** (default: pass@8
   with Opus 4.8 (Claude Code) + GPT-5.5 (Codex); e.g. xAI: Grok-4.5 reward@8 at xhigh);
   record `pass_at_k_*` per model in `task.toml`. In the batch file's band? (default
   Hard ≤2/8, Medium ≤4/8.)

### Step 7 — titrate

- **Still too easy** → the dose was too small: add the **next-highest-ROI** lever from the
  prescription in `<task_dir>_v3` and re-measure. (If the whole prescription is exhausted
  and it's still easy, the surface may be wrong — send back to `identify_hardening_levers`
  for a re-diagnosis, or reconsider the seed surface.)
- **Now unfair** (Phase 7 fails for false-negative / ambiguity / leakage / flakiness, or
  auto-qc flipped to reject) → you over-dosed or mis-applied: back the offending change out
  or fix it, keeping only what's fair. Better a Medium fair task than a Hard broken one.
- **Overshot into "impossible"** (golden can't pass, or no legitimate solution could) →
  loosen the last tightening; correctness must remain reachable.
- **In band + fair + solvable** → done. Append the version row to `hardness_levers.md`'s
  iteration log and report.

## Output

- **`<task_dir>_v2/`** (…`_vN` — the cured version, pure Harbor format, nothing extra;
  earlier versions left untouched).
- **Updated `tasks/<slug>/hardness_levers.md`** — the iteration log filled in per version
  (levers applied, Sonnet pass@1, Opus/GPT pass@8, auto-qc verdict, notes).
- A short **report**: the gap before → after, exactly which levers were dosed (and which
  from the prescription were deliberately *not* applied and why), the solvability +
  cure-bit checks, the auto-qc verdict, and the final band.

## Anti-patterns (reject these)

- **Applying the whole prescription by default.** The prescription is a menu; over-hardening
  wastes effort and risks breaking fairness/solvability. Dose to the gap.
- **Curing by making the verifier unfair** — false negatives, ambiguous gates, leakage.
  A legitimate correct solution must always still pass.
- **Editing one artifact and not cascading** — a widened objective with unchanged
  tests/golden, or a new assertion the golden can't satisfy. Keep instruction ⇄ tests ⇄
  golden consistent.
- **Weakening the golden or a test to make them agree** instead of extending the golden to
  meet a fair new assertion.
- **Scope growth by stapling unrelated changes** — the cured task stays ONE coherent,
  realistic goal within the batch LoC band (multi-file; hard ≠ huge).
- **Writing new pass2pass tests** — the repo's existing suite is the pass2pass guard; only
  the batch file's F2P set (default ~10–20) is yours.
- **Editing in place / leaving scratch** (`analyzer/`, `__pycache__`, notes) in the task —
  branch to `_vN` and keep it pure Harbor format.
- **Declaring "cured" without re-measuring** — you haven't hardened it until Phase 5/7 show
  the pass-rate dropped into band.

## Related skills

- **[`identify_hardening_levers`](../identify_hardening_levers/)** — writes the
  `hardness_levers.md` prescription this skill treats against (and its
  `hardness_levers_catalog.md` explains each lever's difficulty rationale + guardrails).
- **[`task_spec_to_harbor_task`](../task_spec_to_harbor_task/)** — the Harbor build
  conventions + `scripts/verify.sh` used when rebuilding golden/tests/instruction.
- **[`auto-qc`](../auto-qc/)** — the Phase-6 quality gate that must stay `accept` after the
  cure.
- **[`eval-trajectory-failure-analysis`](../eval-trajectory-failure-analysis/)** — to
  reconstruct the agent's easy path when building the cure-bit guard.

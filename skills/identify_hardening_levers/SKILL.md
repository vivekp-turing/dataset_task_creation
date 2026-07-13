---
name: identify_hardening_levers
description: >-
  DIAGNOSE why an EASY Harbor (SWE-Bench-style fail2pass) task isn't hard enough, and
  PRESCRIBE the hardness levers to fix it — the diagnosis half of the hardening loop. A
  task is "easy" when it misses the Hard/Medium acceptance bar: the Phase-5 cheap-model
  filter (Sonnet 5 pass@1 solves it) or the Phase-7 pass@8 runs (Opus 4.8 / GPT-5.5 solve
  it more than the band allows: Hard >2/8, Medium >4/8). This skill reads the eval results
  + trajectories, diagnoses WHY the task is easy (single obvious fix, leaked/over-specified
  instruction, weak/holey verifier, too-small scope, contamination, copyable analogue),
  selects TASK-SPECIFIC candidate levers calibrated to how easy it was, and writes a
  per-task hardness_levers.md spec — each lever with its concrete change, why it's hard, a
  requirements-compliance + quality-rubric safety check (test↔issue alignment, coverage,
  fairness/realism, not underspecified, no over-strict/false-negative tests, no leakage), a
  predicted Phase-7 pass@8 impact, and an ROI rank. It does NOT modify the task — the
  sibling implement_hardening_levers skill administers the cure. Use when asked to
  diagnose/why-is-this-task-easy, identify/propose hardness levers, or write the
  hardness_levers.md hardening spec.
---

# Identify hardening levers (diagnose easiness → prescribe levers)

Take a Harbor SWE-Bench-style task (this pipeline's format: `instruction.md`, `task.toml`,
`environment/{Dockerfile,problem_statement.md}`, `solution/{golden.patch,solve.sh}`,
`tests/test.sh` with the fail2pass patch embedded inline) that came back **too easy**, work
out **why** — *empirically*, from where models actually breezed — and prescribe the levers
that would make it genuinely hard. The single deliverable is a per-task
**`hardness_levers.md`** spec (the "diagnosis + prescription").

This is the **diagnosis half of the hardening loop**. It does **not** touch the task; the
sibling **[`implement_hardening_levers`](../implement_hardening_levers/)** skill reads this
spec and administers the minimal cure. Together they are the concrete tool for what the
pipeline README calls "harden (back to Phase 3/4)": this skill runs after **Phase 5**
(cheap-model filter) or **Phase 7** (pass@8 benchmark) whenever a task misses its band.

## The bar you're hardening toward (from the requirements)

Difficulty is measured as **pass@8** in the models' native harnesses (Codex + Claude
Code), classified by the worse (higher) solve rate:

- **Hard** — Opus 4.8 / GPT-5.5 solve **≤ 2/8**.
- **Medium** — Opus 4.8 / GPT-5.5 solve **≤ 4/8**.
- **Cheap pre-filter** — a task **Sonnet 5 solves at pass@1** is not Hard; hardening a
  Hard-target task must make Sonnet 5 **fail** pass@1 as a floor.

Difficulty must be **justified**: it has to come from **reasoning complexity, cross-module
understanding, subtle behavioral differences, or deep domain knowledge** — NOT from
vagueness, artificial constraints, boilerplate, or chaining unrelated tasks. Every
hardened task stays **fair, realistic, and solvable** by an expert within limits, and the
verifier stays aligned to the instruction with **no false negatives**. You have NOT
hardened a task until a re-run shows the model pass-rate actually dropped into the band.

## Inputs

- **Required — the task** at `<task_dir>/` (has `task.toml`). Its `[metadata]` gives the
  current `difficulty` target, `source_type`, `category/subcategory`, `num_f2p_tests`, and
  any recorded `pass_at_k_*`.
- **Required — at least one easiness signal:**
  - **Phase-5 signal** — the Sonnet 5 pass@1 result for this task (auto-qc `--prefilter`
    record / `difficulty_concern` flag, or the raw harbor eval run dir), and ideally the
    trial trajectory.
  - **Phase-7 signal** — the pass@8 run dir(s) for Opus 4.8 (Claude Code) and/or GPT-5.5
    (Codex): the per-trial `result.json` / `verifier/reward.json` + `agent/trajectory.json`.
- **Helpful** — the auto-qc output (`autoqc/<slug>.autoqc.json`) so hardening doesn't
  reintroduce a rubric failure, and the task's `task_spec_*.md` if it still exists.

If you only have a pass/fail number and no trajectories, you can still harden from the
verifier + source, but say so — trajectory evidence is what makes the levers task-specific.

## Workflow

```
- [ ] 1. Read the task + confirm the target band (Hard/Medium) and the easiness signal(s).
- [ ] 2. Quantify how easy it is → set a HARDENING SEVERITY (light / moderate / severe)
        and the pass-rate GAP to close (how far above band it is).
- [ ] 3. Trajectory + failure analysis: find WHY it's easy (the breezed surfaces, the
        verifier holes, the leaked/over-specified hints). Diagnose, with evidence.
- [ ] 4. Select TASK-SPECIFIC candidate levers from hardness_levers_catalog.md, calibrated
        to the diagnosis + severity. Check each against requirements + the quality rubrics.
- [ ] 5. RANK the levers by ROI (difficulty added per unit of change/risk) and write
        tasks/<slug>/hardness_levers.md (use hardness_levers_template.md). Hand off to
        implement_hardening_levers — do NOT modify the task here.
```

The output is a **prescription**, deliberately possibly larger than what gets applied: list
every credible lever, ROI-ranked, so the implementation skill can administer the *smallest
dose that cures the difficulty gap*. You diagnose and prescribe; it doses and treats.

### Step 2 — quantify easiness → hardening severity

Read the signals and set severity; it scales how much you change.

| Signal observed | Severity | What it means |
|---|---|---|
| Sonnet 5 **solves** at pass@1 | **severe** | Surface is fundamentally too easy; a verifier tweak won't fix it — deepen the surface. Floor: Sonnet must fail after. |
| Frontier solve rate **far above** band (e.g. Hard target, Opus/GPT ≥ 5/8) | **severe→moderate** | Single obvious fix and/or weak verifier; needs real reasoning added. |
| Frontier solve rate **just above** band (e.g. Hard target, 3–4/8; Medium, 5–6/8) | **light→moderate** | Close — a targeted edge/verifier tightening + mild underspecify usually lands it. |
| In band already | — | Don't harden. (If asked to push Medium→Hard, treat as moderate.) |

Record the before-numbers: Sonnet 5 pass@1, and Opus/GPT pass@8 (x/8 each), and the **gap**
(how many solves above the band). These are the baseline `implement_hardening_levers` must
beat, and the gap tells the doctor how big a dose to administer.

### Step 3 — diagnose WHY it's easy (evidence-grounded, task-specific)

Run the sibling **[`eval-trajectory-failure-analysis`](../eval-trajectory-failure-analysis/)**
skill over the most informative trials (the *solved* trials are the important ones here —
you want to see the *shortest path to a pass*). Use its scripts (paths relative to the
`skills/` dir) to read where the agent went:

```bash
python3 skills/eval-trajectory-failure-analysis/scripts/trajectory_stats.py <trial_dir>
python3 skills/eval-trajectory-failure-analysis/scripts/show_steps.py <trial_dir> --grep "diff|apply|test|PASS|def "
```

From the passing trajectories, extract — with `step_id` + snippet evidence — which of
these **easiness causes** apply (usually 1–3). This drives lever selection:

1. **Single obvious implementation** — the agent one-shot the fix with little exploration;
   there's one natural way to write it and no edge matrix to trip on.
2. **Leaked / over-specified instruction** — the statement (or `problem_statement.md`)
   named files, hinted the root cause/approach, or gave examples that reveal the fix, so
   the agent skipped exploration and went straight to the change.
3. **Weak / holey verifier** — a *naive or partial* solution passed: tests only cover the
   happy path, miss the edge matrix, assert loosely, or the agent reward-hacked
   (special-cased inputs, edited/peeked at tests). This is BOTH a difficulty gap and a
   false-positive to close.
4. **Scope too small** — the golden is basically one file / a few lines; nothing forces
   cross-module reasoning or a shared invariant.
5. **Contamination / memorized** — a famous PR/CVE the model recalls; it "knew" the fix
   without reasoning.
6. **Copyable analogue** — a near-identical fix exists elsewhere in the repo and the agent
   transcribed it with no adaptation.

Write the diagnosis as the "Why it's easy" section of the spec — every claim cites a
trajectory `step_id` (or a verifier hole you can point at), never a hunch.

### Step 4 — select task-specific levers (calibrated + rubric-safe)

Map each diagnosed cause to one or more **levers** from
[hardness_levers_catalog.md](hardness_levers_catalog.md). **Levers must be specific to
THIS task** — name the actual subsystem, files, edge cases, and tests, not a generic
"add more tests". Calibrate to severity: *severe* usually needs a surface-deepening lever
(cross-module scope / exact-spec parity / non-local invariant), not just verifier
tightening; *light* often needs one edge-matrix + de-leak lever.

For **every** selected lever, confirm it keeps the task legal and fair — this is
non-negotiable and is written into the spec per lever:

- **Requirements** — golden stays **avg ~350 LoC (≈150–800), multi-file**; the new tests
  are **~10–20 NEW F2P** (never new pass2pass — the repo's existing suite is the pass2pass
  guard); **deterministic + offline**; `source_type` still valid at the pinned base SHA
  (PR-based golden still matches the **canonical upstream fix**); `<100 MB` image;
  taxonomy unchanged (or re-tag if the objective shifts).
- **Quality rubrics** (the auto-qc rubrics — don't trade difficulty for a rubric failure):
  - **test↔issue alignment** — new assertions test behavior the (possibly widened) problem
    statement actually implies; no requirements absent from the issue.
  - **test coverage / robustness** — outcome-based, adversarial, regression-backed; no
    structural/diff/keyword matching; not coupled to the reference solution.
  - **fairness & realism** — the harder task reads like one plausible engineering ask, not
    a chain of unrelated changes or a contrived puzzle.
  - **not underspecified** — hardness comes from the *logic*, not from hiding the goal; a
    capable engineer can still find the surface from the statement.
  - **not over-strict / no false negatives** — a correct solution (the golden, and other
    legitimate correct approaches) must still pass; you are tightening the *bar*, not
    pinning an implementation.
  - **no leakage** — de-leaking is itself a lever; never add root-cause/fix/file hints.

### Step 5 — rank by ROI + write `tasks/<slug>/hardness_levers.md`

**ROI = expected difficulty added ÷ (amount of change + rubric/solvability risk).** Rank the
candidate levers so the highest-ROI cure comes first:

- **High ROI** — closes the exact easy path the trajectories took, small blast radius, low
  false-negative risk (e.g. add the regression/edge case every passing run skipped;
  de-leak a hint). Usually verifier- or instruction-side.
- **Lower ROI** — large surface-deepening changes (cross-module scope, exact-spec parity)
  that add a lot of difficulty but touch the golden heavily and carry more risk of breaking
  solvability or realism. Necessary for *severe* cases, but dose carefully.

Also state, per lever, **what it forces the implementer to touch** — instruction only,
tests only, or tests **and** golden (scope-growing levers change the golden too). That is
what lets the doctor pick the minimal dose.

Use [hardness_levers_template.md](hardness_levers_template.md) verbatim as the structure.
It captures: the header (task, target band, before-signals, severity, **gap to close**),
the evidence-backed **Why it's easy** diagnosis, each **candidate lever** (ROI rank →
concrete change → why it's hard → what it touches → requirements check → rubric-safety
check → predicted pass@8 delta), and the **combined predicted impact** if the top-ROI
subset is applied. This spec is the reviewable prescription and the contract
`implement_hardening_levers` treats against.

## Handoff

Point **[`implement_hardening_levers`](../implement_hardening_levers/)** at
`tasks/<slug>/hardness_levers.md` + the task dir. That skill decides the *dose* (how many of
the ROI-ranked levers are actually needed to close the gap), applies them to a new version,
rebuilds the golden/tests/instruction as each lever demands, validates both directions
(golden still passes; the previously-easy fix now fails), and re-runs Phase 5/6/7. This
skill's job ends at a clear, ROI-ranked, rubric-safe prescription.

## Output

- **`tasks/<slug>/hardness_levers.md`** — the per-task diagnosis + ROI-ranked lever
  prescription (the only deliverable; the task is left untouched).

## Anti-patterns (don't prescribe these)

- **Levers that make the verifier unfair** — false negatives, ambiguous gates, or
  leakage-by-omission. The lower pass-rate must come from the task being hard, not the
  scorer being broken. A legitimate correct solution must always pass.
- **"Hard because vague"** — a lever that strips the instruction until the goal is unclear.
  De-leak, don't obscure. A capable engineer must still be able to find the surface.
- **Chaining unrelated subtasks** to inflate size/scope. The hardened task stays ONE
  coherent, realistic goal (avg ~350 LoC, multi-file — hard ≠ huge).
- **New pass2pass tests** — the repo's existing suite is the pass2pass guard; only the
  ~10–20 F2P are in scope.
- **Diagnosing without evidence** — every "why it's easy" claim and every lever must trace
  to a trajectory `step_id` or a concrete verifier hole, not a hunch.
- **Generic, non-task-specific levers** — "add edge cases" without naming which edges of
  which subsystem and why the model missed them.
- **Modifying the task** — this skill only writes the spec; all edits belong to
  `implement_hardening_levers`.

## Supporting files

- [hardness_levers_catalog.md](hardness_levers_catalog.md) — the levers, grouped by
  "why the task was easy", each with what it does, why it's hard, the requirement +
  rubric-safety constraints it must respect, and its typical Phase-7 pass@8 impact.
- [hardness_levers_template.md](hardness_levers_template.md) — the exact structure of the
  per-task `hardness_levers.md` output.

---
name: auto_quality_fix
description: >-
  Fix a Harbor (SWE-Bench-style fail2pass) task that the Phase-6 Auto-QC (ARIA) pipeline
  REJECTED on quality, and drive it to an ACCEPT — in a capped feedback loop with the
  pipeline. Reads the auto-qc output (autoqc/<slug>.autoqc.json: failing gates, reasons,
  flags, the nine rubric scores, fairness verdict) and optionally the Phase-5 (Sonnet 5)
  or Phase-7 eval outputs + trajectories, first TRIAGES whether the task is fixable, and if
  so applies targeted, requirement-preserving fixes to the flagged rubrics (issue clarity,
  gold-patch clarity, gold-patch↔issue alignment, test clarity, test↔issue alignment,
  fairness, instruction leakage, test false negatives, test false positives), re-runs
  auto-qc, and loops until the task
  is accepted — MAX 3 iterations (stop early on accept) to cap cost. If the task is
  unfixable, it flags that up front with the reason + what an expert human could do or
  whether to reject, and ends without burning QC runs. Task requirements are non-negotiable
  and preserved throughout. Use when asked to fix / repair / remediate / un-reject a task
  that failed Auto-QC, or to loop a task through the QC pipeline until it passes.
---

# Auto quality-fix (rejected by Auto-QC → accepted, capped loop)

Take a task the **Phase-6 Auto-QC (ARIA)** pipeline **rejected** and turn it into one that
**passes and is accepted** — by reading exactly why it failed, fixing those rubric
problems without breaking the task requirements, and re-running the pipeline in a **capped
loop (≤ 3 iterations)**. Before spending any QC runs, decide whether the task is even
**fixable**; if it isn't, say so up front with a reason and a recommendation, and stop.

This is the remediation counterpart to **[`auto-qc`](../auto-qc/)** (Phase 6): auto-qc
*judges*, this skill *repairs to a pass*. It targets the **quality gate** (the nine ARIA
rubrics). A pure **difficulty** flag (`difficulty_concern` — cheap model solved
it) is not a quality problem; that's the hardening loop
(**[`identify_hardening_levers`](../identify_hardening_levers/)** →
**[`implement_hardening_levers`](../implement_hardening_levers/)**), not this skill.

## Non-negotiables

- **Requirements are preserved, always.** Every fix must keep: golden = source-only, avg
  ~350 LoC (≈150–800), multi-file, matching the **canonical upstream fix** for
  PR/commit/issue tasks; **~10–20 NEW F2P** tests (never new pass2pass — the repo's
  existing suite is the pass2pass guard), deterministic + offline; `source_type` valid at
  the pinned base SHA; `<100 MB` image; taxonomy/labels intact. A "fix" that violates a
  requirement is not a fix.
- **Don't fix quality by lowering difficulty.** Keep the task in its difficulty band; if a
  clarity/alignment fix would make it trivially easy, that's a redesign, not a QC fix.
- **Solvability + verifier integrity hold after every change** — the golden still makes the
  verifier pass; the F2P still fail on baseline; no false negatives introduced.
- **Cap at 3 QC iterations** (stop early on accept). The point is to un-reject cheaply, not
  to grind the pipeline. If it can't get there in 3, stop and report.

## Inputs

- **Required — the task** at `<task_dir>/` (Harbor format: `instruction.md`, `task.toml`,
  `environment/{Dockerfile,problem_statement.md}`, `solution/{golden.patch,solve.sh}`,
  `tests/test.sh`).
- **Required — the Phase-6 auto-qc output** for it: `autoqc/<slug>.autoqc.json` (final
  verdict, **failing gates**, reasons, flags, the nine rubric scores, fairness verdict)
  and the raw `aria/markdown/<slug>.md` for the per-rubric rationale. This is the diagnosis
  you fix against.
- **Optional — eval evidence:** Phase-5 (Sonnet 5 pass@1) or Phase-7 (Opus 4.8 / GPT-5.5
  pass@8) run dirs + trajectories. Use these to sanity-check a fix (e.g. a fairness/leakage
  fix shouldn't make the task suddenly solvable; a robustness fix should still let the
  golden pass), via **[`eval-trajectory-failure-analysis`](../eval-trajectory-failure-analysis/)**.
- **Helpful** — the task's `task_spec_*.md` and the repo clone at the base SHA for
  rebuilding patches.

If there is no auto-qc output yet, run `auto-qc` first — this skill repairs against a
verdict, it doesn't produce the first one.

## Workflow

```
- [ ] 1. Read autoqc/<slug>.autoqc.json + aria markdown: list the FAILING GATES + the
        rubric scores + reasons (and any eval evidence).
- [ ] 2. FIXABILITY TRIAGE (before any loop). Fixable → continue. Unfixable → write the
        flag report (reason + human-fix / reject recommendation) and STOP. No QC runs.
- [ ] 3. Branch a working copy: cp -r <task_dir> <task_dir>_fixed (never edit in place).
- [ ] 4. LOOP (attempt = 1..3):
        a. Plan targeted, requirement-preserving fixes for each failing gate
           (rubric_fix_playbook.md). Cascade edits across instruction ⇄ tests ⇄ golden.
        b. Apply in <task_dir>_fixed. Validate locally: golden passes, F2P fail on
           baseline, requirements + separation + non-leak all hold.
        c. Re-run auto-qc on <task_dir>_fixed (a fresh run — this consumes one of the 3).
        d. ACCEPT → stop, output the fixed task. REJECT → read the new failing gates.
           If not improving / a newly-surfaced gate proves it unfixable → flag + stop.
- [ ] 5. After ≤3 attempts: if accepted → done. If still rejected → stop, report the
        remaining gates + the best version + a human-fix / reject recommendation.
```

### Step 2 — fixability triage (do this FIRST, to avoid wasted QC cost)

Judge, from the auto-qc reasons + rubric scores + the task itself, whether targeted edits
can plausibly reach an accept **without** violating a requirement. Flag **unfixable** (and
stop before running the loop) when any of these hold:

- **Invalid surface / structural defect** — golden is effectively empty (the fix already
  landed at the snapshot), the statement describes already-working code as broken, or the
  `source_type` doesn't hold at the base SHA. This is a task-validity problem, not a QC
  polish.
- **Intrinsic unfairness with no deterministic oracle** — "correct" behavior isn't
  derivable from the issue/docs/upstream, or grading needs unknowable exact shapes /
  privileged knowledge. You can't fix fairness by inventing requirements.
- **Environment can't be deterministic/offline** — the tests fundamentally need
  network/GPU/display/live services; fixing that is a rebuild, not a fix.
- **Conflicting deep failures** — e.g. the only way to fix `*_to_issue_alignment` is to
  leak (worsening `instruction_leakage`), or fixing robustness requires re-authoring the
  whole suite AND the surface is weak. When gates can't be satisfied simultaneously without
  a redesign, reject is cheaper.
- **A fix would drop it out of its difficulty band** and there's no in-band way to keep it
  aligned/fair — send to redesign/hardening, not here.

The unfixable flag report (write it, then STOP — no QC runs) contains:

- **Verdict:** `unfixable` (or `needs-human` / `reject`).
- **Why:** the specific failing gate(s) + the structural reason a requirement-preserving
  fix can't reach accept, citing the auto-qc reasons (and eval evidence if used).
- **What an expert could do:** the concrete larger change a human might make (re-pick the
  surface, re-base to a valid parent SHA, re-author the verifier, add a real oracle) — or
  an explicit "recommend reject" if even that isn't worth it.

Only tasks that pass triage enter the loop.

### Step 4 — the fix loop (≤ 3 iterations)

Each iteration fixes **only the gates auto-qc flagged**, using
[rubric_fix_playbook.md](rubric_fix_playbook.md) for the per-rubric remedy and its
requirement guardrails. Key discipline:

- **Cascade edits and keep the three artifacts consistent.** Fixing `instruction_leakage`
  or `issue_clarity` edits BOTH `instruction.md` and `environment/problem_statement.md`.
  Fixing `*_to_issue_alignment` may mean editing the statement to cover behavior the golden
  really implements (without leaking) OR trimming out-of-scope changes from the golden/tests
  — and if the golden's scope changes, the tests follow, and vice-versa. Fixing
  `test_false_positives`/`test_false_negatives`/`test_clarity` rebuilds the embedded F2P
  patch in `tests/test.sh`; if a new fair assertion exposes a gap, extend the **golden** to
  satisfy it (never weaken a test to fit a thin golden). Whenever the F2P set changes,
  keep `task.toml [metadata].fail_to_pass` (and `num_f2p_tests == len(fail_to_pass)`) in
  sync — add/rename/remove node IDs to match the rebuilt tests; update `pass_to_pass` if
  the regression subset changed.
- **Validate locally before re-running QC** (cheaper than a QC run): apply
  `solution/golden.patch` → verifier passes; confirm the F2P fail on baseline; run
  `../task_spec_to_harbor_task/scripts/verify.sh <slug>` (source-only golden, patches apply
  at base SHA, non-leaking, clone clean).
- **Then re-run auto-qc** (this spends one of the three):

```bash
cd scripts/auto_qc
python auto_qc.py <task_dir>_fixed --output-dir out_fix_<attempt>
# reuse the prior ARIA JSON only if nothing relevant changed (rare mid-fix); default is a fresh run
```

- **Read the new verdict.** Accept → done. Reject → target the still-failing gates next
  iteration. If the *same* gate persists with the same reason after a genuine fix, or a fix
  for one gate keeps re-breaking another, re-run triage — it may be unfixable; flag and stop
  rather than burning the last attempt.

### Step 5 — terminate (accept, or capped-out)

- **Accepted within ≤3** → output `<task_dir>_fixed` as the shippable task; report which
  gates were fixed and how, and confirm requirements + solvability held.
- **Still rejected after 3** → stop (cost cap reached). Report the remaining failing gates,
  hand back the best `<task_dir>_fixed`, and give a **human-fix or reject** recommendation
  (like the unfixable flag). Do not keep looping.

## Output

- **`<task_dir>_fixed/`** — the repaired task in clean Harbor format (only when a fix was
  attempted; original left untouched).
- **A fix report** (write alongside, outside the task dir): triage verdict; per-attempt
  {gates targeted → edits made → local validation → auto-qc verdict}; the final verdict
  (accepted / capped-out / unfixable); and, if not accepted, the human-fix/reject
  recommendation. Include the before→after rubric scores.

## Anti-patterns (reject these)

- **Running the QC loop on an unfixable task** — triage first; a hopeless task should never
  consume a QC run.
- **Exceeding 3 QC iterations** — the cap is a cost guard; stop and recommend instead.
- **Fixing a rubric by breaking a requirement** — e.g. deleting F2P tests to pass
  robustness, adding pass2pass tests, shrinking the golden below the LoC band, or dropping
  the canonical-fix match. Non-negotiable.
- **Gaming the annotator** — editing text to satisfy the rubric wording while the underlying
  problem (real leakage, real misalignment, real reward-hackability) remains. Fix the
  substance; the accept must be earned.
- **Fixing quality by lowering difficulty** out of band — that's redesign/hardening, not QC.
- **Editing one artifact without cascading** — a de-leaked/clarified statement that no longer
  matches the tests/golden, or a trimmed golden with stale tests.
- **Editing in place / leaving scratch** (`analyzer/`, QC `out_*` dirs, notes) inside the
  task — branch to `_fixed`, keep it pure Harbor format, keep analysis outside.

## Supporting files

- [rubric_fix_playbook.md](rubric_fix_playbook.md) — per-rubric: what a failing score means,
  the requirement-preserving fix, what it forces you to touch (instruction / tests / golden),
  and the guardrail so the fix doesn't break another gate or a requirement.

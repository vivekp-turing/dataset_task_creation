# Hardness levers catalog

The menu `identify_hardening_levers` prescribes from and `implement_hardening_levers` doses
from. **Levers are organized by the diagnosed
cause of easiness** (from Step 3 of the skill) — pick the levers that match *why the
trajectories show the task was easy*, then instantiate them for the specific subsystem,
files, and edge cases of the task. A lever is only valid if, as applied, it keeps the task
within the requirements AND the quality rubrics (each lever lists the guardrails).

Difficulty must be **justified** — reasoning complexity, cross-module understanding,
subtle behavioral differences, or deep domain knowledge — never vagueness, boilerplate,
artificial limits, or chained unrelated tasks. Calibrate intensity to severity:
**severe** (Sonnet 5 solved pass@1, or frontier ≫ band) needs a *surface-deepening* lever,
not just verifier tightening; **light** (frontier just over band) often needs one
edge-matrix + de-leak lever.

Pass@8 impact ratings below are rough priors (`+` small, `+++` large drop in model
pass-rate); the **re-eval in Step 8 is the real measurement**.

---

## Cause A — Single obvious implementation (agent one-shot it)

*Signal:* passing trajectories show little exploration; the fix is the one natural way to
write it; no edge matrix trips a naive attempt.

### A1 · Widen the edge-case matrix (make a naive fix pass the easy case, fail the matrix)
- **Change:** identify the axes the current golden's naive form gets wrong (sign, zero/
  empty, negative offset, null-vs-NaN, boundary index, unicode, DST/timezone, overflow,
  first-vs-last, duplicate keys) and make correct handling of the *product* of those axes
  required. Add F2P cases across the matrix, including the combinations a quick fix misses.
- **Why it's hard:** the model must reason about interactions, not the happy path; the
  "obvious" implementation now fails a subset.
- **Guardrails:** every added case must be behavior the problem statement implies
  (test↔issue alignment); deterministic + offline; golden extended to actually handle them
  (no false negative). Don't invent requirements the issue never implied.
- **pass@8 impact:** `++` (often the highest-yield, lowest-risk lever).

### A2 · Require an exact-spec / parity oracle (kill "reasonable but wrong")
- **Change:** re-anchor correctness to an exact reference — an RFC/spec, an in-repo
  reference implementation, upstream bug-for-bug behavior, or a naive-recompute oracle —
  and assert against known vectors / the reference output, not "looks right".
- **Why it's hard:** approximate solutions that satisfied loose asserts now fail; the model
  can't wing the precise semantics.
- **Guardrails:** the oracle must be real and derivable from the issue/docs/upstream;
  assertions map inputs→expected correctly; still outcome-based.
- **pass@8 impact:** `++` to `+++` when a real spec/reference exists.

### A3 · Introduce a non-local invariant
- **Change:** make correctness depend on a property that holds *across* the whole
  output/stream/graph — conservation, ordering, contiguity, first-match, release-after-
  last-consumer — not per element. Add tests that check the invariant globally.
- **Why it's hard:** a local edit that looks right violates the invariant somewhere; the
  model must reason about the whole structure.
- **Guardrails:** the invariant must be genuinely part of the desired behavior; golden
  preserves it; tests assert the property, not the implementation.
- **pass@8 impact:** `++`.

---

## Cause B — Leaked / over-specified instruction (agent skipped exploration)

*Signal:* the agent went straight to the right file/approach; the statement named files,
hinted the root cause/fix, or showed revealing examples.

### B1 · De-leak the problem statement
- **Change:** remove file lists ("where to look"), root-cause/fix/algorithm hints, test
  hints, and any example that reveals the mechanism. Restate as **observable behavior +
  success criteria only** in both `instruction.md` and `environment/problem_statement.md`.
- **Why it's hard:** the agent must now *locate* the surface and *diagnose* the cause
  itself — real exploration + reasoning, not transcription.
- **Guardrails:** must stay **solvable** — a capable engineer can still find the surface
  from the behavior described. De-leak ≠ obscure; don't remove information needed to
  understand the goal. This *improves* the `instruction_leakage` rubric.
- **pass@8 impact:** `+` to `++` (bigger when the leak was doing most of the work).

### B2 · Broaden the objective to force exploration
- **Change:** state the goal at a slightly higher level so the agent must map the
  subsystem before fixing it (e.g. "make the recurrence engine RFC-5545-correct for
  exclusion rules" vs "fix EXDATE handling in file X"), keeping it one coherent ask.
- **Why it's hard:** the search space is larger; the model has to build the mental model
  the leaked version handed it.
- **Guardrails:** still one task, still specific enough to be fair and testable; not vague.
- **pass@8 impact:** `+`.

---

## Cause C — Weak / holey verifier (a naive or partial solution passed)

*Signal:* a partial fix scored, or the agent reward-hacked; tests are happy-path only,
assert loosely, or are couplable to the solution. This is a **false positive** to close
AND a difficulty lever.

### C1 · Add the regression + adversarial cases the naive fix fails
- **Change:** from the trajectory, take the exact quick fix that passed and add F2P cases
  that it fails but the canonical/correct fix passes — including a case that reproduces the
  target behavior and the specific edge the partial fix skipped.
- **Why it's hard:** the shortcut the model took is now blocked; it must do the full fix.
- **Guardrails:** aligned to the issue; golden passes them; outcome-based; grow toward the
  ~10–20 F2P target if under it.
- **pass@8 impact:** `++` (directly removes the observed easy path).

### C2 · Tighten loose assertions to exact outcomes
- **Change:** replace "contains / non-empty / no-error" style asserts with exact expected
  values, paired diffs, or round-trip identity; assert the full output, not a substring.
- **Why it's hard:** partial correctness no longer scores; the bar is the precise result.
- **Guardrails:** exact values must be correct and derivable; **no false negatives** — a
  legitimate correct solution still passes. Don't pin incidental formatting the issue
  doesn't require.
- **pass@8 impact:** `+` to `++`.

### C3 · Close reward-hacking / tamper holes
- **Change:** restore test files + any ground-truth from the pristine `/opt/baseline`
  before grading; assert observable behavior via real execution (never diff/source-keyword
  matching); ensure tests don't import/call the reference solution.
- **Why it's hard:** removes shortcuts (special-casing test inputs, editing tests, writing
  answer files) so only real engineering scores.
- **Guardrails:** this is a fairness/robustness *fix*; keep grading deterministic + offline.
- **pass@8 impact:** `+` (mostly integrity; occasionally large if hacking was the path).

---

## Cause D — Scope too small (trivial / single-file golden)

*Signal:* the golden is a few lines in one file; nothing forces cross-module reasoning.

### D1 · Extend to multiple interacting subsystems with a shared invariant
- **Change:** pick a coherent extension of the *same* feature/bug that forces the fix to
  span ≥2 modules sharing an invariant (e.g. parser + evaluator; serializer + its callers;
  schema-gen + arg-binding inverse). Grow the golden toward avg ~350 LoC across files.
- **Why it's hard:** the model must keep multiple components consistent; single-file
  intuition fails.
- **Guardrails:** must be **one coherent task**, not two stapled together (fairness/
  realism); golden stays in the 150–800 LoC band (hard ≠ huge); still buildable + offline.
- **pass@8 impact:** `++` to `+++` — the main lever for *severe* cases.

### D2 · Add a bidirectional / inverse requirement (must round-trip)
- **Change:** require generate-X and parse-X-back (or encode/decode) to round-trip, with
  the oracle being round-trip identity across an input matrix.
- **Why it's hard:** both directions must agree; a fix to one that breaks the other fails.
- **Guardrails:** round-trip is genuinely desired behavior; deterministic; golden supports
  both directions.
- **pass@8 impact:** `++`.

---

## Cause E — Contamination / memorized fix (famous PR/CVE)

*Signal:* the model produced the known fix with no reasoning; the source is a headline
issue/CVE.

### E1 · Re-base to a less-headline change or an adjacent edge-case gap
- **Change:** move the task to a substantive but low-profile change in the same subsystem,
  or to a real edge-case gap the famous fix didn't cover; re-pin the pre-fix parent and
  reproduce the *canonical* fix for the new base.
- **Why it's hard:** the model can't recall the answer; it must reason from the code.
- **Guardrails:** `source_type` must stay valid at the new base SHA (deliverable absent at
  baseline; grep to confirm); PR-based golden matches the canonical upstream fix; realistic.
- **pass@8 impact:** `++` (removes recall advantage).

---

## Cause F — Copyable analogue in the repo (agent transcribed it)

*Signal:* a near-identical fix exists elsewhere in the codebase; the agent copied it with
no adaptation.

### F1 · Require meaningful adaptation the analogue doesn't cover
- **Change:** target the variant that differs from the analogue (different type/shape,
  extra constraint, an interaction the sibling case doesn't have) and add F2P cases that
  the mechanically-copied analogue fails.
- **Why it's hard:** transcription no longer works; the model must understand *why* the
  analogue works and adapt it.
- **Guardrails:** the required adaptation is real and issue-implied; still fair (not a
  trick); golden reflects the adapted fix.
- **pass@8 impact:** `++`.

---

## Combining levers (calibration)

- **Severe (Sonnet 5 pass@1 solved, or frontier ≫ band):** at least one surface-deepening
  lever (A2/A3/D1/D2/E1) **plus** a verifier lever (A1/C1/C2). A verifier-only change will
  not move a fundamentally-easy surface. Floor: Sonnet 5 must fail pass@1 afterward.
- **Moderate (frontier a couple over band):** one edge-matrix/verifier lever (A1/C1/C2) +
  a de-leak (B1) is usually enough.
- **Light (frontier just over band):** the single most-targeted lever — most often A1 or
  C1 aimed exactly at the edge every passing trajectory skipped.

Stack levers **coherently** (they must read as one motivated engineering task), apply them
**a few at a time**, and re-measure after each version so you can attribute the pass-rate
change. Always re-run the solvability guard (golden passes) and the naive-fails guard
(the previously-easy solution now fails) before trusting a version.

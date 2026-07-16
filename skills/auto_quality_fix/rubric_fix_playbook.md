# Rubric-fix playbook

How to repair each Auto-QC (ARIA) rubric failure **without breaking a task requirement**.
Scores are `0` (best) → `3` (worst). Each judge **rejects** when any of these gates trip:

> any of {`issue_clarity`, `test_to_issue_alignment`, `test_false_negatives`,
> `test_false_positives`, `fairness`} ≥ 2 · 3 or more of
> {`test_to_issue_alignment`, `test_false_negatives`, `test_false_positives`, `fairness`}
> score 1 · `instruction_leakage` above the judge's tolerance (lenient judge = 0, strict
> judge ≤ 1; ≥ 2 rejects either)

Because acceptance needs **both** judges to pass and the lenient judge (Kimi) tolerates
**no** leakage, the safe fix target is `instruction_leakage = 0`.

So the target is: **each of those five core rubrics ≤ 1, at most two of the four
test/fairness rubrics at 1, and leakage = 0** — reached by fixing the *substance*, never by
wording the annotator into a pass. `gold_patch_clarity`, `gold_patch_to_issue_alignment`,
and `test_clarity` are scored for information but do **not** gate (still fix them if they
signal a real problem — a weak golden or confusing tests usually drags a gating rubric too).
For each rubric below: what a bad score means → the requirement-preserving fix → what it
forces you to touch → the guardrail (so the fix doesn't trip another gate or a requirement).

Read the `aria/markdown/<slug>.md` rationale for the *specific* reason a rubric scored high;
fix that concrete reason, not the generic category.

---

## `issue_clarity` — the problem statement is unclear/ambiguous
- **Fix:** state the observable behavior and success criteria unambiguously; define terms;
  give a concrete input→expected-output example of the *symptom* (not the fix). Remove
  filler / roleplay / generic tool descriptions (Concise requirement).
- **Touches:** `instruction.md` + `environment/problem_statement.md` (keep identical).
- **Guardrail:** clarify the *problem*, not the *solution* — do not add file paths, root
  cause, or fix steps (that would raise `instruction_leakage`). Don't over-specify to where
  the task becomes trivial (difficulty band).

## `gold_patch_clarity` — the reference solution is hard to follow
- **Fix:** remove unrelated edits / broad refactors / style churn from `solution/golden.patch`
  so it's the minimal coherent change; group related edits; keep it readable.
- **Touches:** `solution/golden.patch` (+ `solve.sh` re-embed).
- **Guardrail:** it must still **match the canonical upstream fix** (PR-based) and stay avg
  ~350 LoC, multi-file, source-only. Don't shrink it below the band or drop required changes.
  If you remove an edit, make sure no F2P test depended on it.

## `gold_patch_to_issue_alignment` — golden does things the issue doesn't imply, or misses parts (info only, non-gating)
- **Fix (two directions):**
  - *Golden does extra* → trim out-of-scope changes so every edit is relevant to and
    permitted by the stated problem (No-unnecessary-changes requirement).
  - *Golden addresses behavior the statement never mentions* → extend the **problem
    statement** to describe that behavior (as a user-facing symptom/requirement), so the
    golden is fully implied — without leaking how to implement it.
- **Touches:** `solution/golden.patch` and/or the statement; keep **tests** in sync with
  whichever way you move.
- **Guardrail:** although this rubric no longer gates directly, misalignment almost always
  drags `test_to_issue_alignment` or the false-negative/positive rubrics — aim for `0`.
  Widening the statement must not leak; trimming the golden must not drop behavior the F2P assert.

## `test_clarity` — the tests are confusing/poorly structured (info only, non-gating)
- **Fix:** clear test/case names tied to the behavior; one behavior per case; explicit
  expected values; remove dead/commented asserts; deterministic setup.
- **Touches:** the F2P patch embedded in `tests/test.sh` (rebuild: edit tests in clone →
  diff → reset → re-embed inline).
- **Guardrail:** keep ~10–20 F2P (no new pass2pass), outcome-based, offline; the golden must
  still pass them and baseline must still fail.

## `test_to_issue_alignment` — tests assert things not in the issue, or miss required behavior (gate: ≥ 2)
- **Fix:**
  - *Extra requirements* → delete asserts that test behavior the issue never specifies
    (No-extra-requirements).
  - *Missing coverage* → add F2P for material behaviors the issue implies but tests skip
    (No-missing-requirements), including the regression case that reproduces the symptom.
- **Touches:** the F2P patch in `tests/test.sh`; if a newly-required behavior isn't handled,
  extend the **golden**.
- **Guardrail:** every assertion maps inputs→expected correctly and is derivable from the
  issue/docs/upstream; stay in the 10–20 F2P band; don't couple to the reference solution.

## `fairness` — the task is unfair (gate: ≥ 2 on the 0-3 rubric)
- **Fix:** make expected outputs **derivable** from the issue/docs/upstream (add the missing
  spec reference or example of the required output structure to the statement if applicable);
  remove any need for privileged knowledge (verifier internals, unknowable exact shapes);
  ensure an expert could solve it within the limits.
- **Touches:** usually the statement (add the derivable spec/format), sometimes the tests
  (stop asserting unknowable exact values).
- **Guardrail:** if fairness can't be reached because there's **no deterministic oracle** for
  the behavior, this is a **triage-unfixable** case — flag it, don't invent requirements.
  Adding a spec reference must not become a fix hint (leakage).

## `instruction_leakage` — the statement reveals files/root cause/fix/tests (gate: per-judge — lenient judge needs 0, strict ≤ 1; aim for 0)
- **Fix:** strip "Where to look: [files]", the root cause, the intended fix/algorithm,
  function names to edit, and any hidden-test detail — **unless it was in the original
  upstream issue**. Restate as behavior + success criteria only.
- **Touches:** `instruction.md` + `environment/problem_statement.md`.
- **Guardrail:** don't over-strip into ambiguity (that raises `issue_clarity`). De-leak,
  don't obscure — a capable engineer must still find the surface.

## `test_false_positives` — tests are reward-hackable / weak / solution-coupled, so a non-fix can pass (gate: ≥ 2)
- **Fix:** make assertions **outcome-based** (execute code, check behavior/final state) —
  never diff shape, line numbers, or source-keyword matching; add adversarial + edge cases so
  a naive/partial fix fails; ensure a **comprehensive F2P** suite incl. the regression case;
  restore test dirs + any ground-truth from the pristine `/opt/baseline` before grading
  (anti-tamper); make sure tests don't import/call the reference solution.
- **Touches:** the F2P patch in `tests/test.sh` (and the restore/anti-tamper block); extend
  the **golden** if a new adversarial assert exposes a real gap.
- **Guardrail:** keep deterministic + offline + fast-enough; do **not** over-tighten into
  false negatives (see below) — the golden and other legitimate correct solutions must still
  pass. Growing robustness may also raise difficulty — fine, as long as it stays in band and fair.

## `test_false_negatives` — tests wrongly REJECT valid solutions (over-strict / pin one implementation) (gate: ≥ 2)
- **Fix:** loosen assertions that pin an internal detail or a single implementation the issue
  never mandates; assert the **observable behaviour / contract** (return value, error, final
  state) rather than exact internal shapes, private field names, log strings, or call order;
  where a format genuinely matters, assert it as an explicit, spec-derivable requirement.
- **Touches:** the F2P patch in `tests/test.sh`; occasionally the **statement** (if a format
  really is required, state it as a requirement so the assertion is fair rather than dropped).
- **Guardrail:** loosening must not create false positives (`test_false_positives`) — keep the
  behavioural core that a real fix must satisfy. Verify at least one alternative correct
  implementation would now pass, while the baseline still fails and the golden still passes.

---

## Cross-cutting guardrails (apply to every fix)

- **Preserve requirements** (non-negotiable): source-only golden, avg ~350 LoC / multi-file,
  canonical-fix match for PR-based, 10–20 NEW F2P (no new pass2pass), deterministic + offline,
  valid `source_type` at base SHA, `<100 MB` image, taxonomy intact.
- **Cascade consistency:** instruction ⇄ tests ⇄ golden must always agree after a fix.
- **Solvability + integrity:** after each fix, golden makes the verifier pass and baseline
  still fails the F2P (no false negative introduced).
- **Don't trade quality for difficulty:** keep the task in band; don't clarify/align it into
  triviality.
- **One or two gates at a time, then re-validate locally** before spending a QC run — the
  loop is capped at 3.

# task_spec.md — required structure

Write each spec in this exact shape. Keep it dense (~70-130 lines). Ground every
claim in real files from the repo's `repo_summary.md` + cloned source.

---

```markdown
# Task Spec — <repo>: <short, specific task title>

**Repo:** `<owner/repo>` (<language>, <version/branch + pinned SHA/tag>, <1 key note>)
**Difficulty target:** **Hard** (frontier solve < 50%)   <!-- or Medium, with rationale -->
**Type:** bug-fix | feature implementation | bug-fix + small feature
**Originality:** net-new feature | real edge-case gap | seeded regression — <one line
proving it vs source, e.g. "grep: no `of S` nth-child variant at SHA abc123">
**Patch size:** ~<N> LoC across <M> files
**Offline:** yes (<test runner / how it stays offline>)

## One-line

<The task in a single sentence: what must change and the correctness condition.>

## Problem domain & current behavior

<2-3 short paragraphs: what the subsystem does (cite real files/types), and what is
wrong or missing. This is design context for the builder — NOT the user-facing
statement. Be concrete about the edge cases / interactions that matter.>

## Why it is hard (deliberately)

1. **<Interacting subsystems>** — <why a fix must span >1 system>.
2. **<Exact-spec correctness>** — <why "reasonable" behavior fails; name the oracle>.
3. **<Non-local invariant / state / lifecycle>** — <the conservation/ordering/state
   property that's easy to violate>.
4. **<Adversarial matrix>** — <the product of cases partial fixes miss>.
5. **<Contamination control>** — <why this is novel, not a public issue>.
<Optionally a 6th. End with an honest line: getting all of this right is author-level
hard / would require iterating against tests.>

## Golden patch — feasibility & approach

**Feasible.** <Name the correctness oracle: RFC/spec / reference impl / corpus /
upstream behavior / naive recompute.>
- <File 1>: <the change>.
- <File 2>: <the change>.
- <File 3 / types / template>: <the change>.
- Keep <invariant/ordering/security guard> intact.

Golden patch lives in `solution/` and touches: `<file>`, `<file>`, `<file>`.

## fail2pass test strategy (deterministic, offline)

<Where tests live + harness style.>

1. **<Primary fail2pass>** — <exact assertions: exact output / paired diffs /
   round-trip / schema equality>. Covers <the key combinations>.
2. **<Edge cases>** — <list the hard combinations the matrix demands>.
3. **<Optional model-based / property test>** — <reference vs implementation>.
4. **pass2pass** — <existing tests that must stay green> (proves no regression).

<Smallest run command, fully offline.>

## Files touched (estimate)

- `<path>` (~<x> LoC: <what>)
- `<path>` (~<x> LoC: <what>)
- `<path>` (~<x> LoC: <what>)
- tests (fail2pass, not counted in patch)

## Harbor / image notes

- <SDK/runtime version + how to pin>; <restore / pre-cache list>; <submodules if any>.
- Verifier: <smallest offline command that runs the new tests>.
- Pin <branch/tag/SHA>; <base image>; reaffirm <100MB git image + no network at test.

## Problem statement draft (non-leaking)

> <2-5 sentences describing ONLY the observable problem a user would report — wrong
> behavior, missing capability — and the correctness condition. No file paths, no
> "where to look", no test names/assertions, no implementation steps.>

*(One line confirming: behavior-focused; no file paths; no test internals.)*
```

---

## Notes on filling it in

- **Title** = repo + the specific behavior, e.g. "recharts: stacked + offset bar
  layout with `minPointSize` sign-correctness across mixed-sign stacks". Specific,
  not "fix bar bug".
- **Difficulty target** is a claim you must justify in "Why it is hard". Default to
  **Hard**; only mark Medium if a frontier model would plausibly hit ~50%.
- **Originality** must be one of the three patterns AND proven against the cloned
  source at the pinned SHA (grep the API/method/option). Never base it on a real
  public issue/PR (leakage + the snapshot may already include or postdate the fix).
  If the subsystem is already correct, use the **seeded-regression** pattern and say
  so — the `environment/` will ship the bug, the gold patch restores correctness.
- **Header `Offline: yes`** must say *how* (runner + why no network) — this is the
  containerization gate.
- **Golden + tests are mandatory.** If either section is vague, you picked the wrong
  surface — go back to Step 3 and pick another.
- **Problem statement** is the only part that becomes user-visible (the eventual
  `instruction.md` seed). Treat it like a Deep-SWE prompt: behavior-focused,
  slightly underspecified, zero verifier leakage.

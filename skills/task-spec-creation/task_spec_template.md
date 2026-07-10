# task_spec.md — required structure

Write each spec in this exact shape. Keep it dense (~70-130 lines). Ground every
claim in real files from the repo's `repo_summary.md` + cloned source.

---

```markdown
# Task Spec — <repo>: <short, specific task title>

**Source idea:** repo_summary "Difficult Task Ideas" #<N> — spec rank #<M> of 3 (hardest-first)
**Repo:** `<owner/repo>` (<language>, <version/branch + pinned SHA/tag>, <1 key note>)
**Difficulty target:** **Hard** (Opus 4.8 / GPT-5.5 solve ≤ 2/8)  <!-- or Medium ≤ 4/8, with rationale -->
**Type:** bug-fix | feature implementation | bug-fix + small feature
**Source type:** PR-based | commit-based | issue-based | derivation | net-new —
<one-line proof vs source, e.g. "pre-fix parent SHA abc123; grep: `of S` nth-child
variant absent". PR-based ⇒ golden matches the canonical upstream fix; net-new < 50%
overall.>
**Category / Subcategory:** <e.g. Software Engineering / Feature implementation>
**Objective labels:** <e.g. Implement, Fix>   **Artifact labels:** <e.g. Codebase>
**Patch size:** ~<N> LoC (avg target ~350; 150–800) across <M> files
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
5. **<Deep domain knowledge>** — <framework/protocol/library internals a generalist
   lacks>.
<Optionally a 6th. End with an honest line: getting all of this right is author-level
hard / would require iterating against tests — and a note that it is FAIR (not vague,
not a chain of unrelated changes; a correct golden of the stated size exists).>

## Golden patch — feasibility & approach

**Feasible.** <Name the correctness oracle: RFC/spec / reference impl / corpus /
upstream behavior / naive recompute.>
- <File 1>: <the change>.
- <File 2>: <the change>.
- <File 3 / types / template>: <the change>.
- Keep <invariant/ordering/security guard> intact.

Golden patch lives in `solution/golden.patch` and touches: `<file>`, `<file>`, `<file>`.

## fail2pass test strategy (deterministic, offline)

<Where tests live + harness style. You author a COMPREHENSIVE NEW suite: ~10–20 F2P
tests (min 10) to prevent reward hacking. Tests assert observable behavior/outcome —
never the file edited, diff shape, or source keywords — and are independent of the
reference solution.>

1. **<Behavior-reproducing case>** — fails pre-fix, passes post-fix (the new
   capability/bug the task is about).
2. **<Core fail2pass cases>** — <exact assertions: exact output / paired diffs /
   round-trip / schema equality>. Covers <the key combinations>.
3. **<Edge-case matrix>** — <the hard combinations partial fixes miss>.
4. **<Optional model-based / property test>** — <reference vs implementation>.

**Pass2pass (existing suite — do NOT author new p2p):** <name the repo's existing
tests / subset that must stay green after the gold patch — the regression guard>.

<Smallest run command, fully offline: runs the new F2P suite + the relevant existing
tests. Note the ~F2P count.>

## Files touched (estimate)

- `<path>` (~<x> LoC: <what>)
- `<path>` (~<x> LoC: <what>)
- `<path>` (~<x> LoC: <what>)
- <sum ≈ 350 LoC in the 150–800 band across multiple files>
- tests (~10–20 fail2pass, not counted in patch)

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
- **Difficulty target** is a claim you must justify in "Why it is hard" (grounded in
  reasoning/cross-module/domain complexity). Default to **Hard** (≤2/8); only mark
  **Medium** (≤4/8) if a frontier model would plausibly hit that band.
- **Source type** must be declared AND proven against the cloned source at the pinned
  base SHA. Prefer **PR/commit/issue-based** (net-new stays < 50%); for those, pin the
  **pre-fix parent** so the deliverable is absent at baseline and make the golden
  match the **canonical upstream fix**. For net-new/edge-case, grep to confirm the
  capability/edge is absent. **Seeded regression** is a last resort (say so; the
  `environment/` ships the bug, the gold patch restores correctness).
- **Category/subcategory + labels** are required metadata (they flow into
  `task.toml`); pick the category matching the dominant work.
- **Header `Offline: yes`** must say *how* (runner + why no network) — this is the
  containerization gate.
- **Golden + comprehensive tests are mandatory.** If either section is vague, or you
  can't see ~10–20 real F2P assertions, you picked the wrong surface — go back to
  Step 3.
- **Problem statement** is the only part that becomes user-visible (the eventual
  `instruction.md` seed). Treat it like a Deep-SWE prompt: behavior-focused,
  slightly underspecified, zero verifier leakage.

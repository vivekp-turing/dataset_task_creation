# task_spec.md — required structure

Write each spec in this exact shape. Keep it dense (~90-150 lines). Ground every
claim in real files from the repo's `repo_summary.md` + cloned source.

---

```markdown
# Task Spec — <repo>: <short, specific task title>

**Repo:** `<owner/repo>` (<language>, <version/branch + pinned SHA/tag>, <1 key note>)
**Difficulty target:** **Hard** (claude-opus-4.6 pass ≤ 60%)   <!-- or Medium, with rationale -->
**Type:** bug-fix | feature implementation | bug-fix + small feature
**Originality:** net-new feature | real edge-case gap | seeded regression — <one line
proving it vs source, e.g. "grep: no `of S` nth-child variant at SHA abc123">
**Patch size:** ~<N> LoC across <M> files
**Offline:** yes (<test runner / how it stays offline>)

## Taxonomy (Alibaba)

- **code_lang:** `<go|c|c++|python|java|js/ts|...>` (see [`docs/alibaba/taxonomy_v1.yaml`](../../docs/alibaba/taxonomy_v1.yaml); ★★★ langs need coverage)
- **task_type:** `<bug-fix|compatibility-fix|feature|refactor|test-add|...>` (second-level label)
- **application:** `<Client_UI|Backend_Infrastructure|AI_ML|Database_Storage|Business_Domain_Logic|...>`
- **High-priority dimensions** (set true only when genuinely required):
  - long_horizon: <true|false> — <justification if true>
  - must_follow_claude_md: <true|false>
  - requires_web_search: <true|false>
  - requires_multi_turn_user: <true|false>
  - requires_subagents: <true|false>
  - requires_skills: <true|false>
  - requires_context_management: <true|false>
  - requires_mcp: <true|false>
  - requires_custom_tools: <true|false>
  - requires_coding_conventions: <true|false>

## Alibaba meta

- **One-sentence description:** <what this task does>
- **Why worth evaluating:** <why it exposes model weaknesses; 1-2 sentences>
- **Author self-assessment (placeholders):**
  - Professional background: <industry, years experience>
  - Personal time estimate: <hours to complete>

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
6. **<Model discrimination>** — <why opus may pass ≤60% but weaker models fail more>.
<Optionally a 7th. End with an honest line: getting all of this right is author-level
hard / would require iterating against tests; expect 20+ agent turns.>

## Golden patch — feasibility & approach

**Feasible.** <Name the correctness oracle: RFC/spec / reference impl / corpus /
upstream behavior / naive recompute.>
- <File 1>: <the change>.
- <File 2>: <the change>.
- <File 3 / types / template>: <the change>.
- Keep <invariant/ordering/security guard> intact.

Golden patch lives in `solution/solve.sh` (embedded) and touches: `<file>`, `<file>`, `<file>`.

## fail2pass test strategy (deterministic, offline)

<Where tests live + harness style.>

1. **<Primary fail2pass>** — <exact assertions: exact output / paired diffs /
   round-trip / schema equality>. Covers <the key combinations>.
2. **<Edge cases>** — <list the hard combinations the matrix demands>.
3. **<Optional model-based / property test>** — <reference vs implementation>.
4. **pass2pass** — <existing tests that must stay green> (proves no regression).

<Smallest run command, fully offline.>

## Rubric seeds (must mirror exec verifier)

Task-specific correctness points for `rubric.md`. These MUST restate the same pass
conditions as the fail2pass tests — no extra requirements, no weaker bar.

### Correctness
- <point 1 — same bar as primary fail2pass>
- <point 2 — edge cases the verifier checks>
- <point 3 — regression / pass2pass preservation>

### Reasoning
- <what good analysis looks like for this task>

### Tool usage
- <expected tool patterns, e.g. subagent use if requires_subagents>

## Files touched (estimate)

- `<path>` (~<x> LoC: <what>)
- `<path>` (~<x> LoC: <what>)
- `<path>` (~<x> LoC: <what>)
- tests (fail2pass, not counted in patch)

## Harbor / image notes

- <SDK/runtime version + how to pin>; <restore / pre-cache list>; <submodules if any>.
- Verifier: <smallest offline command that runs the new tests>.
- Pin <branch/tag/SHA>; <base image>; package as `environment/workspace.tar.gz`.
- Agent timeout: 10800s if long_horizon; else 3600s minimum.

## Problem statement draft (non-leaking)

> <2-5 sentences describing ONLY the observable problem a user would report — wrong
> behavior, missing capability — and the correctness condition. No file paths, no
> "where to look", no test names/assertions, no implementation steps.>

*(One line confirming: behavior-focused; no file paths; no test internals.)*
```

---

## Notes on filling it in

- **Difficulty target** defaults to **Hard** with claude-opus-4.6 pass ≤ 60%. Design for
  20+ agent turns and ≥20% pass-rate gap vs qwen-3.7-max and claude-sonnet-4.6.
- **Taxonomy** values must come from [`docs/alibaba/taxonomy_v1.yaml`](../../docs/alibaba/taxonomy_v1.yaml)
  and [`docs/alibaba/[Public] taxonomy_v1 (English).pdf`](../../docs/alibaba/[Public]%20taxonomy_v1%20(English).pdf).
  Use official `code_lang`, `task_type`, and `application` labels. Check distribution
  caps (≤100 per combination; ≥5 per ★★★ combination).
- **Rubric seeds** become `rubric.md` in Phase 5. Correctness bullets must match the
  exec verifier exactly — this is an Alibaba acceptance gate.
- **High-priority dimensions**: only set `true` when the task genuinely requires that
  capability. `requires_subagents` is required for final Alibaba acceptance.
- **Problem statement** becomes `instruction.md` and `test/<slug>.json` description.

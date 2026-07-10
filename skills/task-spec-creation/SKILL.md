---
name: task-spec-creation
description: >-
  Turn each explored seed repo (its repo_summary.md + the cloned source) into THREE
  high-quality, deliberately HARD task specs — selecting the TOP 3 MOST DIFFICULT task
  ideas from that repo's repo_summary.md "Difficult Task Ideas" section and writing one
  spec each (task_spec_1.md, task_spec_2.md, task_spec_3.md; #1 = hardest) in that
  repo's folder. Each spec must meet every requirement in
  the task spec (avg ~350 LoC / ≈150-800 multi-file gold patch, ~10-20 NEW fail2pass
  offline tests with the repo's existing suite as pass2pass, <100MB git image, harbor
  format), assigns a taxonomy
  category/subcategory + objective/artifact labels, declares a source type
  (PR/commit/issue-based, derivation, or net-new — net-new < 50% overall), is
  realistic + fair, and   hard enough that frontier models (Opus 4.8, GPT-5.5) solve it
  <= 2/8 (Hard) or <= 4/8 (Medium). Each spec covers: the task, why it's hard,
  golden-patch feasibility + how to build it (matching the canonical upstream fix when
  PR-based), and a comprehensive fail2pass suite, plus a non-leaking problem-statement
  draft. Use after seed-repo-exploration when asked to select the top difficult task
  ideas per repo, write task specs, or design hard tasks from explored repos. Runs the
  3 spec-writes per repo in parallel batches.
disable-model-invocation: true
---

# Task-Spec Creation

Take a set of already-explored seed repos (each with a `repo_summary.md`) and write,
for each, **three** task specs — one per each of the **top 3 most difficult task
ideas** in that repo's summary. Each spec is the contract a later Harbor build
(instruction + gold patch + tests) is written against, and each becomes its own
Harbor task downstream.

This skill is the step **after** `seed-repo-exploration`. Exploration
produces the mental model + a ranked list of **5-6 "Difficult Task Ideas"**; this
**selects the 3 hardest of those**, makes each genuinely hard, and writes 3 buildable
specs (`task_spec_1.md` … `task_spec_3.md`, #1 = hardest).

## Key intent (do not violate)

- **Three specs per repo** (`task_spec_1.md`, `task_spec_2.md`, `task_spec_3.md`),
  written into the same `tasks/<slug>/` folder that holds that repo's
  `repo_summary.md`. Do not invent new folders. `_1` is the hardest.
- **Select the top 3 MOST DIFFICULT task ideas** from that repo's `repo_summary.md`
  "Difficult Task Ideas" section (which lists 5-6, already ranked). Rank the ideas by
  genuine difficulty (reasoning/cross-module/subtle-behavior/domain — see
  `difficulty_playbook.md`), confirm each against the cloned source, and take the top
  3 that are actually buildable + valid. If fewer than 3 are viable (some fail the
  validity/buildability check), write specs only for the viable ones and say why.
- **One idea → one spec.** Each spec covers exactly one coherent task; never merge two
  ideas or chain unrelated changes to inflate difficulty.
- **Hard, realistic, and fair.** Target the Medium/Hard bands (see
  `difficulty_playbook.md`): **Medium** = Opus 4.8 / GPT-5.5 solve ≤ 4/8; **Hard** =
  ≤ 2/8 (pass@8). Difficulty must come from **reasoning complexity, cross-module
  understanding, subtle behavioral differences, or deep domain knowledge** — good
  hard tasks are large feature additions, complex debugging, root-cause analysis, or
  hard security/research. It must **not** come from vagueness, artificial
  constraints, boilerplate, or **chaining multiple unrelated tasks** into one. Keep
  it **solvable** by an expert within limits.
- **Declare a source type.** Each spec states one of: **PR-based**, **commit-based**,
  **issue-based**, **derivation** (of an existing PR), or **net-new**. Across the
  dataset **net-new stays < 50%**, so prefer real PR/commit/issue sources. When based
  on a real upstream change, the golden must **match the canonical upstream fix**
  (not an invented alternative) unless that fix is unavailable/unsuitable (justify).
- **Verify against the snapshot (always).** Whatever the source type, confirm against
  the cloned source at the pinned SHA that the task is valid: for net-new/edge-case,
  the capability/edge is genuinely absent; for a PR/commit/issue, pin the **pre-fix
  parent** so the deliverable is absent at baseline and the fix hasn't already landed.
  Never describe already-working code as broken. See `difficulty_playbook.md`.
- **Assign the taxonomy.** Give each spec its dominant **category + subcategory**
  (from the Task-Diversity taxonomy in `task_taxonomy.md`) plus **objective labels**
  and **artifact labels** (multi-label). Pick the category matching the main objective
  of the fix, not incidental steps.
- **Buildable.** Only pick a surface where an **avg-~350-LoC (≈150–800) multi-file
  gold patch** is feasible AND a **comprehensive, deterministic offline fail2pass
  suite (~10–20 tests)** can be written. If you can't see the golden + the tests,
  pick a different surface.
- **Don't leak.** The problem-statement draft must describe the *problem/behavior*
  only — no file lists ("where to look"), no test names/assertions, no
  implementation steps, no root-cause/fix hints (unless present in the original
  issue).
- Write specs in **parallel** where possible (read-only subagents can draft from a
  repo_summary + cloned source; the main agent writes the files).

## Requirements every spec must satisfy

(Read the source spec PDF if available — e.g. `docs/updated_reflection_reqs_*.pdf` —
to confirm; these are the load-bearing ones.)

- **Harbor format**, with a **separate gold patch in a `solution/` folder**
  (`solution/golden.patch`).
- **Avg ~350 LoC patch (≈150–800)** that **edits multiple files**; feature
  implementation OR bug fix.
- **~10–20 NEW fail2pass tests** (a *comprehensive* suite, min 10, to prevent reward
  hacking) that fail on the unpatched repo and pass with the gold patch — these are
  the only tests you author, and they must include one that directly reproduces the
  target behavior/failure. **Do NOT write new pass2pass tests**: the repo's
  **existing** test suite is the pass2pass guard — note the relevant existing
  subset that must stay green (no regression) after the gold patch. Tests verify
  **observable behavior/outcome** (not the file edited, diff shape, or source
  keywords), are deterministic, offline, fast enough for the timeout, and independent
  of the reference solution. **No internet** at test time; offline Docker build.
- **<100 MB git image**, no future commits/reflog/remote.
- **Source type** declared (PR/commit/issue-based, derivation, or net-new; net-new <
  50% overall). PR-based ⇒ golden matches the **canonical upstream fix**.
- **Category + subcategory + objective labels + artifact labels** assigned (taxonomy
  in `task_taxonomy.md`).
- **Difficulty target:** ~50% Medium (≤4/8) / 50% Hard (≤2/8) overall — this skill
  authors toward **Hard**; each spec states its target and a justification grounded in
  reasoning/cross-module/domain complexity. Fair + realistic + solvable, never a
  chain of unrelated tasks.
- **Problem statement** discusses the problem, not the implementation; concise; no
  hidden-test leakage; no explicit "relevant files" lists; no fix/root-cause hints.

## Workflow

```
- [ ] 1. Confirm inputs: the tasks/ dir, which repos (each should already have a
        repo_summary.md), and whether the task-spec PDF is available. Re-read the
        PDF requirements once so the bar is exact.
- [ ] 2. For each repo, read its repo_summary.md — especially the ranked
        "Difficult Task Ideas" (5-6), plus "Testing", "Offline Notes",
        "Risks/Gotchas". These 5-6 ideas are the candidate pool.
- [ ] 3. RANK + SELECT TOP 3: order the 5-6 ideas by genuine difficulty
        (difficulty_playbook.md), then open the cloned source for the top candidates
        to confirm each yields an avg-~350-LoC multi-file golden + a comprehensive
        offline F2P suite. Keep the 3 hardest that are actually buildable + valid;
        skip (drop down the list) any that are easy, need network/display/GPU/live
        services, or are just chained unrelated changes. Result: 3 selected ideas
        ranked hardest-first (fewer only if <3 are viable — note why).
- [ ] 3b. SOURCE-TYPE + VALIDITY CHECK (required, PER selected idea): decide the
        source type (PR/commit/issue-based, derivation, or net-new; keep net-new <
        50% overall) and grep the cloned source at the pinned base SHA to prove the
        task is valid — the deliverable is ABSENT at baseline and the fix hasn't
        already landed. For PR-based tasks pin the pre-fix parent and plan to
        reproduce the canonical fix. Drop any idea already implemented/fixed at the
        snapshot and replace it with the next-hardest viable idea.
- [ ] 4. Draft the 3 specs against task_spec_template.md — one read-only subagent per
        selected idea, launched in parallel (see spec_subagent_brief.md).
- [ ] 5. Self-check each spec against the quality bar + checklist below. Ensure the 3
        specs are DISTINCT tasks (no overlap), each hard on its own.
- [ ] 6. Write task_spec_1.md / task_spec_2.md / task_spec_3.md into tasks/<slug>/
        (alongside repo_summary.md), hardest-first.
- [ ] 7. Verify every repo folder has its (up to) 3 non-trivial task_spec_N.md files;
        report the picks grouped by language with each chosen idea + difficulty target.
```

### Step 2-3: select the top 3 (the hard part)

Source the candidate pool from the repo_summary's ranked "Difficult Task Ideas" (5-6).
Order them by genuine difficulty and, for each of the top candidates, **confirm
against the actual cloned source** that:

- a focused **gold patch** of avg ~350 LoC (≈150–800) across multiple files is
  plausible (you can name the files and the change) — big enough to be cross-module,
  small enough that a correct fix exists,
- there's a clear **oracle** for correctness (a spec/RFC, a reference
  implementation, a corpus, upstream behavior / the canonical PR fix, or a naive
  recompute),
- a **comprehensive, deterministic offline test suite (~10–20 F2P)** can assert
  behavior (exact output, paired diffs, round-trips, property tests), plus a
  regression test that reproduces the issue,
- it's **realistic** (a plausible feature/bug for this project) and **fair** (not
  vague, not a chain of unrelated changes).

**Source-type + validity verification (REQUIRED — grep the source, don't trust the
summary):** declare the source type and prove validity against the snapshot:

- **PR / commit / issue-based** (preferred; keep net-new < 50%) → identify the real
  upstream change, pin the **pre-fix parent** as base, confirm the deliverable is
  absent at baseline, and plan the golden to **match the canonical fix**.
- **Derivation** → an existing PR adapted/extended; note what changed vs upstream.
- **Net-new feature / real edge-case gap** → grep to confirm the capability/edge is
  **genuinely absent** at the pinned SHA. If it already exists, the task is invalid.
- **Seeded regression** (last resort) → subsystem is correct; the task ships a
  realistic **injected bug** in `environment/` and the gold patch restores it. Say so
  explicitly and only when no real source/gap exists on a hard surface.

If you can't establish a valid source type and prove it against the actual source for
a given idea, **drop that idea and select the next-hardest viable one** from the
repo's 5-6 (do not force a spec). Common mistake: describing already-working code as
"broken", or adding a feature that's already implemented (golden would be empty).

Prefer surfaces that combine **multiple interacting subsystems**, **exact-spec
correctness** (not "reasonable" behavior), and **non-local invariants** — these are
what make frontier models fail. See `difficulty_playbook.md` for the levers and a
ranked list of "hard archetypes."

### Step 4: draft the 3 specs (one per selected idea, in parallel)

Launch **one read-only subagent per selected idea** (up to 3, in a single batch),
each drafting one spec for its assigned idea (see
[spec_subagent_brief.md](spec_subagent_brief.md)) — do not have one subagent write all
three. Use the exact structure in [task_spec_template.md](task_spec_template.md). Every
spec must include a dedicated **"Why it is hard (deliberately)"** section and a
**"Golden patch — feasibility & approach"** section naming the files and the change,
plus a **fail2pass test strategy** with the ~10–20 NEW F2P suite (including the
behavior-reproducing case) + edge cases + the existing-suite pass2pass note, and the
header taxonomy/source-type block.

### Step 6-7: write + verify

Write the specs to `<tasks_dir>/<slug>/task_spec_1.md` (hardest), `task_spec_2.md`,
`task_spec_3.md`. Then:

```bash
cd "<tasks_dir>" && for d in */; do n=$(ls "$d"task_spec_*.md 2>/dev/null | wc -l); \
  printf "%-22s %s spec(s)\n" "${d%/}" "$n"; done
```

Expect **3** specs per repo (fewer only where <3 ideas were viable — note which).
A good spec is typically ~70-130 lines. Re-draft anything thin or missing the
hard/golden/tests sections. Each `task_spec_N.md` maps to its own downstream Harbor
task (point `task_spec_to_harbor_task` at each spec separately).

## The output: `task_spec_1.md` … `task_spec_3.md`

Up to three specs per repo (hardest = `_1`), each a self-contained, distinct task.
Every file uses the fixed structure (see
[task_spec_template.md](task_spec_template.md)). Non-negotiable sections:

1. **Title + header block** — task title; **difficulty target** (Hard ≤2/8 / Medium
   ≤4/8) with a one-line justification; type (feature / bug-fix); **source type**
   (PR/commit/issue-based, derivation, or net-new) with a one-line proof against
   source (e.g. "pre-fix parent SHA …; grep confirms no `X`"); **category /
   subcategory** + **objective labels** + **artifact labels**; patch-size estimate
   (avg ~350 LoC, N files); offline (yes + how).
2. **One-line** — the task in a single sentence.
3. **Problem domain & current behavior** — what the subsystem does and what's wrong/
   missing, grounded in real files (this is design context, not the user-facing
   statement).
4. **Why it is hard (deliberately)** — 4-6 numbered reasons: interacting subsystems,
   exact-spec correctness, non-local invariants, state/lifecycle, adversarial test
   matrix, deep domain knowledge. State honestly that it's author-level hard, and why
   it's fair (not vague, not chained).
5. **Golden patch — feasibility & approach** — confirm it's buildable; name the
   oracle (for PR-based, the **canonical upstream fix**); list the files to change and
   the nature of the change; note it lives in `solution/golden.patch`.
6. **fail2pass test strategy** — a **comprehensive ~10–20 NEW F2P suite** with exact
   assertions across the edge matrix, including a case that reproduces the target
   behavior/failure, and optional property/model-based tests; all deterministic +
   offline, outcome-based, independent of the reference solution. Note the **existing
   tests that serve as pass2pass** (the relevant subset to run for regression) — do
   not author new pass2pass tests. Give the smallest run command.
7. **Files touched (estimate)** — bullet list with per-file LoC estimate summing to
   ~350 (in the 150–800 band).
8. **Harbor / image notes** — SDK/runtime version, restore/pre-cache, submodules,
   pin SHA/tag, smallest verify command, base image; reaffirm <100MB + offline.
9. **Problem statement draft (non-leaking)** — the user-facing problem text:
   behavior only, no files, no tests, no implementation. End with a one-line note
   confirming it doesn't leak.

## Quality bar (what makes a spec good)

- **Genuinely hard.** The "why it's hard" reasons are real (a solver must reason
  across systems / hit an exact spec / preserve a non-local invariant), not just
  "the codebase is big." Ideally the author admits they'd need to iterate against
  tests to get it fully right.
- **Buildable golden + tests.** Named files, a real oracle, and a comprehensive
  ~10–20 F2P suite with exact assertions. No surface where you can't see how to
  verify it.
- **Valid source, realistic, offline, fair.** Source type declared and **verified
  against the snapshot** (deliverable absent at the pinned base; PR-based golden
  matches the canonical fix); a plausible feature/bug; runs with no
  network/display/GPU/live services; not a chain of unrelated changes.
- **Avg ~350 LoC (≈150–800), multiple files**, correct type (feature vs bug-fix),
  tagged with category/subcategory + labels, Harbor-ready.
- **Non-leaking statement.** Describes the problem a user would report — nothing
  about files, tests, root cause, or how to fix it.

## Anti-patterns (reject these)

- A task that's a single-function tweak with one obvious implementation (too easy).
- "Add a new rule/transform/command" that's mostly boilerplate + registry edits
  (laborious, not hard) — unless the *logic* inside is the hard part.
- **Chaining multiple unrelated tasks** into one to inflate size (a "bad difficult
  task"); difficulty that comes only from vagueness/underspecification.
- **Describing already-working code as "broken"** or **adding a feature that already
  exists** in the snapshot (golden would be empty / tests already pass). Always grep
  to confirm.
- A PR/issue-based task pinned to the wrong SHA so the fix already landed (golden
  empty) or postdates the snapshot — pin the **pre-fix parent**; verify, don't guess.
- Any surface needing a live server, GPU, display, or the internet to verify.
- A golden you can't sketch, or behavior with no deterministic oracle.
- A problem statement that names files or hints at the tests/fix.

## Subagent brief + supporting files

- [task_spec_template.md](task_spec_template.md) — the exact output structure every
  `task_spec.md` must follow.
- [task_taxonomy.md](task_taxonomy.md) — categories/subcategories + objective/artifact
  labels + source types + distribution targets to tag each spec with.
- [difficulty_playbook.md](difficulty_playbook.md) — Medium/Hard bands + how to make a
  task hard on purpose (levers + ranked "hard archetypes" + a self-test) + source-type
  validity + fairness.
- [spec_subagent_brief.md](spec_subagent_brief.md) — verbatim instructions to give a
  read-only subagent that drafts ONE spec for ONE assigned difficult idea (launch one
  per selected idea, up to 3 per repo).

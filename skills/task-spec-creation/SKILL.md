---
name: task-spec-creation
description: >-
  Turn each explored seed repo (its repo_summary.md + the cloned source) into ONE
  high-quality, deliberately HARD, original task spec written as task_spec.md in
  that repo's folder. Picks the single best task surface per repo that meets every
  requirement in the task spec (~100 LoC multi-file gold patch, fail2pass + pass2pass
  offline tests, workspace.tar.gz env, Alibaba Harbor format), is NOVEL/original
  (not a public GitHub issue or famous CVE), realistic, and hard enough that
  claude-opus-4.6 passes ≤60% with ≥20% gap vs qwen-3.7-max and claude-sonnet-4.6.
  Each spec covers: taxonomy tags, Alibaba meta, rubric seeds, the task, why it's
  hard, golden-patch feasibility + how to build it, and concrete fail2pass tests,
  plus a non-leaking problem-statement draft. Use after seed-repo-
  exploration when asked to pick a task idea per repo, write task specs, or design
  hard original tasks from explored repos. Runs spec-writing in parallel batches.
disable-model-invocation: true
---

# Task-Spec Creation

Take a set of already-explored seed repos (each with a `repo_summary.md`) and write,
for each, **one** `task_spec.md` describing the single strongest **original** task to
build from that repo. The spec is the contract a later Harbor build (instruction +
gold patch + tests) is written against.

This skill is the step **after** `seed-repo-exploration`. Exploration
produces the mental model + "Good Surfaces"; this picks ONE surface per repo, makes
it genuinely hard, and writes a buildable spec.

## Key intent (do not violate)

- **One `task_spec.md` per repo**, written into the same `tasks/<slug>/` folder that
  holds that repo's `repo_summary.md`. Do not invent new folders.
- **Pick exactly one** task idea per repo — the best/hardest viable one — not a list.
- **Hard by design.** The aim is the Alibaba Hard band: claude-opus-4.6 pass ≤60%,
  ≥20% gap vs qwen and sonnet, ≥20 agent turns. If *you* can solve it trivially in
  one shot, it's too easy — push deeper. See `difficulty_playbook.md`.
- **Original & novel (the task spec requires NEW tasks).** Never reproduce or derive
  from a known public GitHub issue, PR, changelog entry, or famous CVE. Two failure
  modes to avoid: (a) **leakage** — a public issue+fix is likely in training data, so
  it's trivially solved; (b) **snapshot/timeline mismatch** — the repo is pinned to a
  past snapshot, so a real issue may have been fixed *after* the snapshot (golden
  duplicates a future PR) or the feature already landed *before* it (golden already
  in-tree). **Always verify against the actual cloned source at the pinned SHA** that
  the gap/bug is real — don't trust memory or the summary. Every spec must declare
  which of three originality patterns it uses (net-new feature / real edge-case gap /
  seeded regression — see `difficulty_playbook.md`).
- **Buildable.** Only pick a surface where a ~100-LoC multi-file **gold patch** is
  feasible AND **deterministic offline fail2pass tests** can be written. If you
  can't see the golden + the tests, pick a different surface.
- **Don't leak.** The problem-statement draft must describe the *problem/behavior*
  only — no file lists ("where to look"), no test names/assertions, no
  implementation steps.
- Write specs in **parallel** where possible (read-only subagents can draft from a
  repo_summary + cloned source; the main agent writes the files).

## Requirements every spec must satisfy

(Read the source spec PDF if available — e.g. `.../SWE-Bench-task-spec.pdf` — to
confirm; these are the load-bearing ones.)

- **Alibaba Harbor format** — see [`docs/alibaba/README.md`](../../docs/alibaba/README.md).
- **~100 LoC patch** across multiple files; feature implementation OR bug fix.
- **fail2pass + pass2pass** tests; **no internet** at grade time; `workspace.tar.gz` env.
- **Taxonomy tags** from [`docs/alibaba/taxonomy_v1.yaml`](../../docs/alibaba/taxonomy_v1.yaml)
  (`code_lang`, `task_type`, `application`).
- **Rubric seeds** whose correctness points mirror the exec verifier (Alibaba gate).
- **Alibaba meta**: one-sentence description, why worth evaluating, author self-assessment.
- **High-priority dimension flags** — only when genuinely required.
- **Difficulty target:** author toward **Hard** (opus ≤60%); design for model discrimination.
- **Problem statement** discusses the problem, not the implementation; no hidden-test
  leakage; no explicit "relevant files" lists.

## Workflow

```
- [ ] 1. Confirm inputs: the tasks/ dir, which repos (each should already have a
        repo_summary.md), and whether the task-spec PDF is available. Re-read the
        PDF requirements once so the bar is exact.
- [ ] 2. For each repo, read its repo_summary.md (esp. "Good Surfaces for Original
        Tasks", "Testing", "Offline Notes", "Risks/Gotchas"). Open the cloned source
        for the candidate surface to confirm the golden + tests are real.
- [ ] 3. Pick the SINGLE hardest viable surface per repo (use difficulty_playbook.md).
        Reject surfaces that are easy, can't yield a ~100-LoC multi-file golden,
        need network/display/GPU/live services, or mirror a public issue.
- [ ] 3b. ORIGINALITY CHECK (required): grep the cloned source at the pinned SHA to
        prove the gap/bug is real and classify the task as net-new feature / real
        edge-case gap / seeded regression. Reject anything that's already implemented,
        already fixed, or derived from a known public issue/PR/CVE.
- [ ] 4. Draft each task_spec.md against task_spec_template.md (parallel batches OK).
- [ ] 5. Self-check each spec against the quality bar + checklist below.
- [ ] 6. Write task_spec.md into tasks/<slug>/ (alongside repo_summary.md).
- [ ] 7. Verify every repo folder has a non-trivial task_spec.md; report the picks
        grouped by language with the chosen surface + difficulty target.
```

### Step 2-3: pick the surface (the hard part)

Source the candidate list from the repo_summary's "Good Surfaces". Then **confirm
against the actual cloned source** that:

- a focused **gold patch** of ~100 LoC across 2-5 files is plausible (you can name
  the files and the change),
- there's a clear **oracle** for correctness (a spec/RFC, a reference
  implementation, a corpus, lodash/upstream behavior, or a naive recompute),
- **deterministic offline tests** can assert exact behavior (exact output, paired
  diffs, round-trips, model-based property tests),
- it's **novel** (not a famous bug) and **realistic** (a plausible real feature/bug).

**Originality verification (REQUIRED — grep the source, don't trust the summary):**
classify the task into exactly one pattern and prove it against the snapshot:

1. **Net-new feature** → grep to confirm the capability is **absent** at the pinned
   SHA. If it already exists, the task is invalid — re-frame or pick another surface.
2. **Real edge-case gap** → confirm the feature exists but the specific variant/edge
   you target is genuinely unhandled in the snapshot.
3. **Seeded regression** → the subsystem is already correct; the task ships a
   realistic **injected bug** in `environment/` and the gold patch restores correct
   behavior. The spec must say so explicitly.

If you can't prove one of these three against the actual source, do not write the
spec for that surface. Common mistake: describing already-working code as "broken"
(it isn't) or adding a feature that's already implemented (golden would be empty).

Prefer surfaces that combine **multiple interacting subsystems**, **exact-spec
correctness** (not "reasonable" behavior), and **non-local invariants** — these are
what make frontier models fail. See `difficulty_playbook.md` for the levers and a
ranked list of "hard archetypes."

### Step 4: draft the spec

Use the exact structure in [task_spec_template.md](task_spec_template.md). Every spec
must include a dedicated **"Why it is hard (deliberately)"** section and a
**"Golden patch — feasibility & approach"** section naming the files and the change,
plus a **fail2pass test strategy** with a primary test + edge cases + pass2pass.

### Step 6-7: write + verify

Write to `<tasks_dir>/<slug>/task_spec.md`. Then:

```bash
cd "<tasks_dir>" && for d in */; do f="${d}task_spec.md"; \
  [ -f "$f" ] && printf "%-22s %5s lines\n" "${d%/}" "$(wc -l < "$f")" \
  || printf "%-22s MISSING\n" "${d%/}"; done
```

A good spec is typically ~70-130 lines. Re-draft anything thin or missing the
hard/golden/tests sections.

## The output: `task_spec.md`

Fixed structure (see [task_spec_template.md](task_spec_template.md)). Non-negotiable
sections:

1. **Title + header block** — difficulty target (Hard/Medium), type, originality,
   patch size, offline.
2. **Taxonomy (Alibaba)** — `code_lang`, `task_type`, `application`, high-priority
   dimension booleans with justifications.
3. **Alibaba meta** — one-sentence description, why worth evaluating, author
   self-assessment placeholders.
4. **One-line**, **Problem domain**, **Why it is hard** (include model discrimination).
5. **Golden patch — feasibility & approach** — oracle, files, lives in `solution/solve.sh`.
6. **fail2pass test strategy** — primary, edges, pass2pass, run command.
7. **Rubric seeds** — correctness/reasoning/tool_usage points mirroring the verifier.
8. **Files touched**, **Harbor / image notes** (`workspace.tar.gz`, agent timeout).
9. **Problem statement draft (non-leaking)** — becomes `instruction.md` + query JSON.

## Quality bar (what makes a spec good)

- **Genuinely hard.** The "why it's hard" reasons are real (a solver must reason
  across systems / hit an exact spec / preserve a non-local invariant), not just
  "the codebase is big." Ideally the author admits they'd need to iterate against
  tests to get it fully right.
- **Buildable golden + tests.** Named files, a real oracle, and a primary fail2pass
  with exact assertions. No surface where you can't see how to verify it.
- **Original, realistic, offline.** Not a public issue and **verified against source**
  (the gap/bug is real at the pinned SHA, or the regression is explicitly seeded); a
  plausible feature/bug; runs with no network/display/GPU/live services.
- **~100 LoC, multiple files**, correct type (feature vs bug-fix), Harbor-ready.
- **Non-leaking statement.** Describes the problem a user would report — nothing
  about files, tests, or how to fix it.

## Anti-patterns (reject these)

- A task that's a single-function tweak with one obvious implementation (too easy).
- "Add a new rule/transform/command" that's mostly boilerplate + registry edits
  (laborious, not hard) — unless the *logic* inside is the hard part.
- Reproducing a known CVE / headline bug / public issue (contamination).
- **Describing already-working code as "broken"** or **adding a feature that already
  exists** in the snapshot (golden would be empty / tests already pass). Always grep
  to confirm.
- A task derived from a real issue that may have been fixed *after* the snapshot
  (golden duplicates a future PR) — verify the snapshot, not your memory.
- Any surface needing a live server, GPU, display, or the internet to verify.
- A golden you can't sketch, or behavior with no deterministic oracle.
- A problem statement that names files or hints at the tests.

## Subagent brief + supporting files

- [task_spec_template.md](task_spec_template.md) — the exact output structure every
  `task_spec.md` must follow.
- [difficulty_playbook.md](difficulty_playbook.md) — how to make a task hard on
  purpose (levers + ranked "hard archetypes" + a self-test: "is this actually hard?").
- [spec_subagent_brief.md](spec_subagent_brief.md) — verbatim instructions to give a
  read-only subagent that drafts one spec from a repo_summary + cloned source.

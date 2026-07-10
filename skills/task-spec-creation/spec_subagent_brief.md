# Spec subagent brief (give this to each spec-drafting subagent)

Use **one read-only subagent per selected difficult idea** (up to 3 per repo, launched
in parallel) to draft one `task_spec.md` for its assigned idea. The subagent analyzes
and returns markdown; the **main agent selects the top-3 ideas, assigns one per
subagent, and writes the files** (`task_spec_1.md` … `task_spec_3.md`). Give each
subagent: the repo's `repo_summary.md` (full text), **which of the "Difficult Task
Ideas" it is assigned** (idea # + its one-line description) and its difficulty rank,
the cloned source path, the task requirements (below), `task_spec_template.md`,
`task_taxonomy.md`, and `difficulty_playbook.md`.

---

## Your job (subagent)

You are assigned **ONE specific difficult task idea** (given below) from this repo's
`repo_summary.md`. Using the summary and the cloned source at `<path>`, develop that
idea into **one `task_spec.md`** following the provided template exactly, and return
only that markdown as your final message. Build the spec for the ASSIGNED idea — do
not swap to a different surface unless the assigned idea is invalid/unbuildable at the
snapshot (in that case, say so clearly in your reply so the main agent can reassign).

## Confirm the assigned idea against the source

Take your assigned idea, then confirm against the actual source. The idea MUST:

- Yield an **avg-~350-LoC (≈150–800) gold patch across multiple files** (you can name
  the files + change) — one coherent task, not a chain of unrelated changes.
- Have an **exact correctness oracle** (spec/RFC, reference impl, corpus, upstream
  parity / the canonical PR fix, or naive recompute).
- Be verifiable with a **comprehensive, deterministic, offline suite of NEW fail2pass
  tests (~10–20, min 10)** — including one that reproduces the target behavior — with
  the repo's **existing** suite as pass2pass (do NOT author new p2p; note the subset
  to run for regression). No network/display/GPU/live services. Tests assert
  observable behavior, not the file edited / diff shape / source keywords.
- Have a declared **source type** — PR-based / commit-based / issue-based / derivation
  / net-new (keep net-new < 50%). **Verify against the cloned source at the pinned base
  SHA**: the deliverable must be ABSENT at baseline. For PR/commit/issue-based tasks,
  pin the **pre-fix parent** and make the golden **match the canonical upstream fix**.
  For net-new/edge-case, grep to confirm the capability/edge is absent. Seeded
  regression only as a last resort. NEVER describe already-working code as broken or
  add a feature that already exists.
- Be **realistic + fair** and **genuinely hard**: pass the self-test in
  `difficulty_playbook.md` (difficulty from reasoning/cross-module/domain complexity,
  not vagueness). If the assigned idea turns out too easy (you could one-shot a perfect
  golden), escalate it with the difficulty levers to reach the target band; if it
  can't be made genuinely hard, say so so the main agent can reassign.
- Be tagged with a **category + subcategory** and **objective/artifact labels** from
  `task_taxonomy.md`.

Reject: single-function tweaks with one obvious fix; pure boilerplate/registry "add a
thing" tasks; **chains of unrelated tasks**; anything needing live infra; anything
already implemented/fixed at the snapshot.

## Requirements the spec must satisfy

- Harbor format with a **separate gold patch in `solution/golden.patch`**; avg ~350
  LoC (150–800), **multiple files**; feature impl OR bug fix.
- **~10–20 NEW fail2pass** (incl. a behavior-reproducing case); repo's existing suite
  = pass2pass (don't author new p2p). **No internet**, offline Docker, **<100MB git
  image**.
- Difficulty target **Hard** (≤2/8) unless you justify **Medium** (≤4/8).
- Source type declared + proven; category/subcategory + objective/artifact labels set.
- Problem statement: **problem/behavior only** — no "where to look" file lists, no
  test info, no root-cause/fix hints, no implementation steps.

## Output

Follow `task_spec_template.md` exactly. Mandatory sections: header block (difficulty
target + band, type, source type + proof, category/subcategory + labels, patch size,
offline), one-line, problem domain & current behavior, **Why it is hard
(deliberately)**, **Golden patch — feasibility & approach** (name files + oracle),
**fail2pass test strategy** (~10–20 NEW F2P + behavior-reproducing case + edges +
existing-suite pass2pass note + run command), files-touched estimate (~350 LoC),
Harbor/image notes, and a **non-leaking problem-statement draft**.

Ground every architectural/flow claim in a real file you actually inspected. If you
cannot see both the golden and the tests for your assigned idea, report that back so
the main agent can reassign the next-hardest idea — do not silently swap surfaces.

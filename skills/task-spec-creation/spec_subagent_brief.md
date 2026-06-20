# Spec subagent brief (give this to each spec-drafting subagent)

Use a **read-only subagent per repo** to draft one `task_spec.md`. The subagent
analyzes and returns markdown; the **main agent writes the file**. Give the subagent:
the repo's `repo_summary.md` (full text), the cloned source path, the task
requirements (below), `task_spec_template.md`, and `difficulty_playbook.md`.

---

## Your job (subagent)

From this repo's `repo_summary.md` and the cloned source at `<path>`, choose the
**single best ORIGINAL task** to build and return **one `task_spec.md`** following the
provided template exactly. Return only that markdown as your final message.

## Pick exactly one surface — the hardest viable one

Start from the "Good Surfaces for Original Tasks" in the repo_summary, then confirm
against the actual source. The chosen surface MUST:

- Yield a **~100 LoC gold patch across 2-5 files** (you can name the files + change).
- Have an **exact correctness oracle** (spec/RFC, reference impl, corpus, upstream
  parity, or naive recompute).
- Be verifiable with **deterministic, offline fail2pass + pass2pass** tests (no
  network/display/GPU/live services).
- Be **novel** — NOT a known public GitHub issue, PR, changelog entry, or CVE — and
  **realistic** (a plausible feature/bug for this project). **Verify against the
  cloned source at the pinned SHA** (grep the relevant API/method/option): the gap or
  bug must be real in the snapshot. Classify the task as exactly one of: **net-new
  feature** (capability confirmed absent), **real edge-case gap** (feature exists,
  specific variant unhandled), or **seeded regression** (subsystem is correct; the
  task ships an injected bug in `environment/` and the gold patch restores it). State
  which, with a one-line proof. NEVER describe already-working code as broken or add
  a feature that already exists — and never derive from a real issue (it may be fixed
  after, or landed before, this snapshot).
- Be **genuinely hard**: pass the self-test in `difficulty_playbook.md`. If you could
  one-shot a perfect golden, it's too easy — pick a harder surface or escalate with
  the difficulty levers (interacting subsystems, exact-spec correctness, non-local
  invariants, state/lifecycle, edge-case matrix).

Reject: single-function tweaks with one obvious fix; pure boilerplate/registry "add a
thing" tasks; anything needing live infra; anything mirroring a public bug.

## Requirements the spec must satisfy

- Harbor format with a **separate gold patch in `solution/`**; ~100 LoC, **multiple
  files**; feature impl OR bug fix.
- **fail2pass + pass2pass**, **no internet**, offline Docker, **<100MB git image**.
- Difficulty target **Hard** (frontier solve <50%) unless you justify Medium.
- Problem statement: **problem/behavior only** — no "where to look" file lists, no
  test info, no implementation steps.

## Output

Follow `task_spec_template.md` exactly. Mandatory sections: header block (difficulty
target, type, patch size, offline), one-line, problem domain & current behavior,
**Why it is hard (deliberately)**, **Golden patch — feasibility & approach** (name
files + oracle), **fail2pass test strategy** (primary + edges + pass2pass + run
command), files-touched estimate (~100 LoC), Harbor/image notes, and a **non-leaking
problem-statement draft**.

Ground every architectural/flow claim in a real file you actually inspected. If you
cannot see both the golden and the tests for a surface, pick a different surface.

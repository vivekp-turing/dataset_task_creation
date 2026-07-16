# Difficulty playbook — making a task hard on purpose

Target distribution ≈ **50% Medium / 50% Hard**, measured as **pass@8** with the
models in their harnesses (Codex + Claude Code):

- **Medium** — Opus 4.8 / GPT-5.5 solve **≤ 4/8**.
- **Hard** — Opus 4.8 / GPT-5.5 solve **≤ 2/8**.

Prefilter cheaply: a task easily solved by Sonnet/Haiku is unlikely to be Hard for
Opus, so drop it early. A task is not hard because the repo is big or the patch is
long. It is hard because **correctness requires reasoning a strong model tends to get
partially wrong**, and difficulty must be **justified** — it must arise from reasoning
complexity, cross-module understanding, subtle behavioral differences, or deep domain
knowledge.

**Good difficult tasks:** large feature additions, complex debugging, root-cause
analysis, hard security/research problems. **Bad difficult tasks:** combining multiple
unrelated tasks into one; tasks that are "hard" only because they're vague or
underspecified. Keep every task **fair, realistic, and solvable** by an expert within
the time/resource limits. Use these levers.

## The self-test (apply to every candidate)

Ask, honestly:

1. **Could I one-shot a fully-correct golden** without running the tests? If yes →
   too easy. A good hard task is one you'd need to *iterate against tests* to nail.
2. **Is there a single obvious implementation?** If yes → too easy (or it's
   boilerplate). Hard tasks have a correct-but-subtle implementation among
   plausible-but-wrong ones.
3. **Does a naive fix pass the easy case but fail a matrix of edge cases?** If yes →
   good; that gap is exactly where models fail.
4. **Is the oracle exact (spec/RFC/reference/corpus)** rather than "looks reasonable"?
   Exact oracles punish approximate solutions → harder + more verifiable.

If a candidate fails 1-2 (too easy), escalate using the levers below or pick another
surface from the repo_summary.

## Levers that add real difficulty

- **Multiple interacting subsystems.** Force a fix to span ≥2 systems with a shared
  invariant (e.g. parser + reactive engine; range model + audit passes; schema-gen +
  arg-binding inverse; solver + marker algebra + lock). Single-file fixes are rarely
  hard.
- **Exact-spec / parity correctness.** Target behavior defined by an RFC, a reference
  implementation, or bug-for-bug upstream parity (lodash, OpenSSH AEAD framing,
  RFC 5545 recurrence, JSON-Schema). "Reasonable" ≠ correct, so the model can't wing
  it.
- **Non-local invariants.** Conservation / ordering / contiguity / first-match /
  release-after-last-consumer — properties that hold across an array/graph/stream,
  not per-element. Easy to violate with a local change.
- **State machines & lifecycles.** Incremental/differential updates under
  retractions, per-invocation isolation, async re-dispatch, generator-ordered
  pipelines, cache cold-vs-warm. Bugs appear on the *second* item, not the first.
- **Sign/baseline/variance/null matrices.** Mixed-sign, negative offsets, wildcard
  variance, null-vs-NaN, DST boundaries — products of cases a partial fix misses.
- **Security-adjacent correctness.** Tamper rejection, prototype-pollution guards,
  auth precedence, timing-safe compares — wrong "fixes" silently weaken safety, so
  the bar is exact and the tests are adversarial.
- **Cross-backend / cross-compiler / multi-target parity.** Same semantics across
  pandas/polars/arrow, javac/ECJ, BCL/BouncyCastle — one engine right, others wrong
  is the common partial failure.

## Ranked "hard archetypes" (good defaults per repo shape)

1. **Incremental/differential engine under deletions** (diff dataflow, reactive
   re-eval) — emit minimal correct diff including boundary pull-ins. Oracle = naive
   recompute. (e.g. IVM topK, nth-child re-indexing.)
2. **Spec-exact protocol/format framing** — wire/serialization formats with offsets,
   sequence numbers, AAD, tags. Oracle = spec + known vectors. (e.g. AEAD ciphers,
   line folding, expression-string building.)
3. **Boolean/algebraic edge solving** — marker algebra, generic/wildcard resolution,
   range/scope resolution. Oracle = the algebra's laws + reference. (e.g. overlapping
   markers, nested-generic forging, disable-range scoping.)
4. **Parity re-implementation** — match an external reference across an edge matrix.
   Oracle = the reference. (e.g. lodash mergeWith, RFC recurrence vs libical corpus.)
5. **Bidirectional/inverse pairs** — generate X and parse X back; must round-trip.
   Oracle = round-trip identity. (e.g. schema-gen ↔ arg-binding, serialize ↔ parse.)
6. **Precedence/arbitration under mixed inputs** — value/source precedence, retry
   signal precedence, first-match authorization. Oracle = documented precedence.
7. **Coordinate/geometry consistency across transforms** — keep multiple outputs in
   sync under a transform + filter. Oracle = closed-form geometry. (e.g. image+bbox+
   keypoint co-transform, stacked-bar layout.)

## Keeping it FAIR while hard (don't make it impossible or flaky)

- A correct golden must **exist, be multi-file, and be sized to the provided task
  requirements** (e.g. a minimum gold-patch LoC and/or a minimum number of non-test
  files touched) — hard ≠ huge. If the only fix is 2000 LoC across 30 files, it's the
  wrong surface (or a chain of unrelated tasks).
- **One coherent task, not a chain.** Difficulty must come from the logic, not from
  stapling several unrelated changes together.
- **Comprehensive but scoped tests:** author a comprehensive **>5 NEW F2P (min 5)**
  suite to prevent reward hacking, including one that reproduces the target behavior.
  **Don't write new
  pass2pass** — the repo's **existing** suite is the pass2pass guard; just run the
  relevant existing subset to confirm no regression. Tests must be **deterministic &
  offline** — no timing/wall-clock dependence (drive delays from headers/inputs), no
  network, no GPU/display — **outcome-based** (assert behavior, not the file edited /
  diff shape / source keywords), and **independent of the reference solution**. Fast
  enough for the timeout. Use property tests with a reference, not flaky randomness.
- The **problem statement stays solvable**: behavior-focused and slightly
  underspecified, but a capable engineer reading it could find the surface. Hardness
  comes from the *logic*, not from hiding the goal or leaking the tests.
- **No verifier leakage** — don't encode the test's exact numbers into the statement,
  and don't reveal the root cause, the fix, or the files to edit.

## Net-new tasks + snapshot validity (MANDATORY — prove it)

These tasks are **strictly net-new**: an original feature/capability or a real
edge-case gap authored fresh from the repo. **Do NOT** build tasks from existing
PRs/commits/issues, derivations of upstream changes, or seeded regressions — the
deliverable must be something **genuinely absent at the pinned base SHA** that you add.

A net-new task is only valid if the gap is real **at the pinned base snapshot**. Two
failure modes to prevent:

1. **Already-present capability** — grep/read the source at the pinned SHA to confirm
   the capability (or the specific edge/variant) does **not** already exist. If it's
   already there, the golden would be empty → invalid.
2. **Already-correct code** — never describe working code as "broken".

Rules:

- Mark `source_type = net-new` in the spec and in `task.toml`.
- **Verify against the actual snapshot source (don't trust memory or the summary):**
  - Net-new feature → grep to confirm the capability is **genuinely absent** at the
    pinned SHA; the gold patch adds it.
  - Real edge-case gap → the feature exists but the specific variant/edge is unhandled
    at the snapshot; confirm the gap is real; the gold patch handles it.
- Pin a stable base **SHA/tag** so the baseline is reproducible and the deliverable is
  absent there.
- Contamination note: avoid re-creating a famous public feature/CVE a model likely
  memorized; author substantive, less-headline capabilities so the task isn't trivially
  solved.
- Realistic > contrived: it should read like a plausible feature-request or gap for
  that project — the kind of net-new work a real engineer on that repo would take on.

If you cannot prove the capability/edge is **genuinely absent** at the snapshot, the
task is not valid — pick another surface.

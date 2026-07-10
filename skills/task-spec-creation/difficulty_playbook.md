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

- A correct golden must **exist and average ~350 LoC (≈150–800) across multiple
  files** — hard ≠ huge. If the only fix is 2000 LoC across 30 files, it's the wrong
  surface (or a chain of unrelated tasks).
- **One coherent task, not a chain.** Difficulty must come from the logic, not from
  stapling several unrelated changes together.
- **Comprehensive but scoped tests:** author ~10–20 NEW F2P (min 10) to prevent
  reward hacking, including one that reproduces the target behavior. **Don't write new
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

## Source types + snapshot validity (MANDATORY — declare and prove it)

Tasks may be **PR-based, commit-based, issue-based, a derivation of an existing PR, or
net-new** — with **net-new kept < 50%** of the dataset. Prefer real
PR/commit/issue sources (SWE-Bench style): when a task is based on a real upstream
change, the golden must **match the canonical upstream fix** (not an invented
alternative), unless that fix is unavailable/unsuitable for benchmark use (justify).

Whatever the source, the task is only valid if it is real **at the pinned base
snapshot**. Two failure modes to prevent:

1. **Snapshot/timeline mismatch** — pin the **pre-fix parent** commit as the base so
   the deliverable is ABSENT at baseline. If you pin too late, the fix already landed
   (golden empty); base it on a change that postdates your snapshot and the task
   duplicates a future PR.
2. **Already-correct code** — never describe working code as "broken", and never add a
   capability that already exists.

Rules:

- **Declare the source type in the spec** and mark it in `task.toml` (`source_type`).
- **Verify against the actual snapshot source (don't trust memory or the summary):**
  - PR/commit/issue-based → identify the real change, pin its **parent** SHA, confirm
    the deliverable is absent at baseline, and reproduce the canonical fix as golden.
  - Net-new feature → grep to confirm the capability is **genuinely absent** at the
    pinned SHA.
  - Real edge-case gap → the feature exists but the specific variant/edge is unhandled
    in the snapshot; confirm the gap is real.
- **Seeded regression is a LAST RESORT.** Only inject a bug if, after genuinely
  searching, there's no real source/gap on a hard surface. The spec must say so
  ("environment seeds a regression in X; baseline differs from upstream").
- Contamination note: extremely famous public issues/CVEs are more likely memorized by
  models; favor substantive, less-headline changes so the task isn't trivially solved.
- Realistic > contrived: it should read like a plausible feature-request or bug report
  for that project.

### Valid source types (state which in the spec; keep net-new < 50%)

1. **PR-based / commit-based / issue-based** (preferred) — a real upstream change;
   base = its pre-fix parent; golden = the canonical fix. (Verify the deliverable is
   absent at baseline.)
2. **Derivation** — an existing PR adapted/extended; note what differs from upstream.
3. **Net-new feature / real edge-case gap** — capability/edge confirmed absent in the
   snapshot; gold patch adds/handles it. (Verify absence by grep.) Net-new < 50%.
4. **Seeded regression** (last resort only) — subsystem is correct; environment ships
   a realistic injected bug; gold patch restores correctness. Use only when 1–3 are
   genuinely unavailable on a hard surface.

If you cannot place your task in one of these and prove it against source, the task is
not valid — pick another surface.

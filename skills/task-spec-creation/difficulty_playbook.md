# Difficulty playbook — making a task hard on purpose

The "Difficult" band = **frontier (Opus, GPT-5.5) and OSS models solve
< 50%**. A task is not hard because the repo is big or the patch is long. It is hard
because **correctness requires reasoning a strong model tends to get partially
wrong.** Use these levers.

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

- A correct golden must **exist and be ~100 LoC** — hard ≠ huge. If the only fix is
  500 LoC across 15 files, it's the wrong surface.
- Tests must be **deterministic & offline** — no timing/wall-clock dependence (drive
  delays from headers/inputs), no network, no GPU/display. Use property tests with a
  reference, not flaky randomness.
- The **problem statement stays solvable**: behavior-focused and slightly
  underspecified, but a capable engineer reading it could find the surface. Hardness
  comes from the *logic*, not from hiding the goal or leaking the tests.
- **No verifier leakage** — don't encode the test's exact numbers into the statement.

## Contamination control + novelty (MANDATORY — the task spec requires NEW original tasks)

The task spec requires **new, original, novel** tasks — not tasks derived from a
real issue/PR. This matters for two reasons:

1. **Leakage/training contamination** — a public issue + its fix may already be in
   model training data, so the "hard" task is trivially solved.
2. **Snapshot/timeline mismatch** — these repos are pinned to a past snapshot. If you
   base a task on a real issue, that issue may have been **fixed AFTER the snapshot**
   (or the feature already landed BEFORE it). Either way the task is invalid: the
   golden either already exists in-tree or duplicates a real future PR.

Rules:

- **Never base a task on a known public GitHub issue, PR, changelog entry, or CVE.**
  If you recognize the exact bug/feature as real and famous, discard it.
- **Verify against the actual snapshot source (do not trust memory or the summary):**
  - If the task is a **feature**, confirm the capability is **genuinely absent** in
    the cloned source at the pinned SHA (grep for the API/method/option). If it's
    already implemented, the task is invalid — pick a real gap or re-frame.
  - If the task is a **bug-fix**, confirm the buggy behavior is real in the snapshot
    (or that you will *introduce* a synthetic regression — see below). Do NOT claim
    existing, correct code is "broken."
- **STRONGLY PREFER net-new features and genuinely-missing edges/variants.** This is
  the whole point of seed-repo selection + deep exploration: find a real capability
  the snapshot lacks (a missing API/option/variant) or a real edge case it doesn't
  handle. These are the highest-quality original tasks. Do the work to find one.
- **Seeded regression is a LAST RESORT, not the default.** Only fall back to injecting
  a bug if, after genuinely searching the repo, there is no buildable net-new feature
  or real edge gap on a hard surface. If used, the spec must say so explicitly
  ("environment seeds a regression in X; task is to restore correct behavior") — but
  treat needing this as a signal you may have picked a weak surface.
- Favor obscure-but-real modules over headline features (less trafficked = less
  contaminated and less likely already-fixed).
- Realistic > contrived: it should read like a plausible feature-request or bug
  report for that project — even if synthetic.

### Three valid originality patterns (state which one in the spec; prefer 1 & 2)

1. **Net-new feature** (preferred) — capability is confirmed absent in the snapshot;
   gold patch adds it. (Verify absence by grep.)
2. **Real edge-case gap** (preferred) — feature exists but a specific variant/edge is
   unhandled in the snapshot; gold patch handles it. (Verify the gap is real.)
3. **Seeded regression** (last resort only) — subsystem is correct in the snapshot;
   environment ships a realistic injected bug; gold patch restores correctness. (Spec
   must declare the seeded bug + that baseline `environment/` differs from upstream.)
   Use only when 1 and 2 are genuinely unavailable on a hard surface.

If you cannot place your task in one of these three and prove it against source, the
task is not valid — pick another surface.

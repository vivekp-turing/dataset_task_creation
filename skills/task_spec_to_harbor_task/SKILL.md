---
name: task_spec_to_harbor_task
description: >-
  Convert a SWE-Bench-style task spec (task_spec.md + a pinned repo
  clone) into ONE complete, runnable Harbor-format task folder — instruction.md,
  task.toml, environment/{Dockerfile,problem_statement.md},
  solution/{golden.patch,solve.sh}, tests/test.sh — with a real source-only golden
  patch (avg ~350 LoC, multi-file) and a comprehensive NEW fail2pass verifier (~10-20
  F2P tests; the repo's existing suite is the pass2pass guard, not re-authored) that
  grades offline by writing a 0/1 reward. task.toml [metadata] carries
  the category/subcategory + objective/artifact labels + source_type + difficulty.
  Use when asked to build/create a Harbor task (or batch of tasks) from task specs, to
  author the golden solution + verifier tests, or to verify that such Harbor tasks
  apply cleanly and are non-leaking. Do NOT use the harbor-long-range-task-create skill
  for this — that is for long-horizon LLM-judge tasks, not SWE-Bench fail2pass tasks.
---

# Task spec → Harbor task

Convert ONE task spec into ONE complete, correct Harbor SWE-Bench-style task
folder. For a batch, repeat per slug. The golden solution is a real source patch
(avg ~350 LoC across multiple files, matching the canonical upstream fix for
PR/commit/issue-based tasks); the verifier is a **comprehensive suite of NEW
fail2pass tests (~10–20 F2P, including one that reproduces the target behavior)**
that **fails on baseline, passes after the gold patch**, graded **offline**. The
repo's **existing** tests are the **pass2pass** guard (already in the image — run a
relevant subset for regression; do NOT author new pass2pass tests).

This is NOT the long-range/LLM-judge Harbor format. Do not invoke
`harbor-long-range-task-create`. There is no LLM judge — grading is a single
deterministic test run that writes `0` or `1` to `/logs/verifier/reward.txt`.

## Inputs (per task slug `<S>`)

- Spec: `<root>/tasks/<S>/task_spec.md` — authoritative. Source of: pinned base
  SHA, source_type, category/subcategory + objective/artifact labels, golden approach
  + the exact source files it touches, the fail2pass matrix (~10–20 F2P), the offline
  run command, image/toolchain notes, a non-leaking problem-statement draft, and the
  source-type validity proof.
- Repo: `<root>/clones/<S>/` — real source. Usually already at the baseline SHA;
  confirm with `git -C clones/<S> rev-parse HEAD`. Some tasks pin a **pre-fix
  parent** commit, so the clone HEAD may differ from the spec base SHA — always
  build and verify patches against the **spec base SHA**.

`<root>` is the task set's `initial_task_list/` (or equivalent). Confirm with the
user if ambiguous.

## Output — create EXACTLY these 7 files at `<root>/harbor_tasks/<S>/`

```
<S>/
  instruction.md                  # problem statement only — no solution, no leakage
  task.toml                       # config + [metadata] taxonomy/source/difficulty
  environment/Dockerfile          # pin SHA, install deps at BUILD time, bake /opt/baseline
  environment/problem_statement.md # same non-leaking statement as instruction.md
  solution/golden.patch           # golden SOURCE change only (no test files)
  solution/solve.sh               # embeds golden.patch inline + applies it
  tests/test.sh                   # embeds the NEW fail2pass TEST patch inline; restores
                                  #   pristine tests, applies it, runs new F2P + existing
                                  #   (pass2pass) subset offline, writes reward
```

This matches the Reflection submission format: `solution/{solve.sh, golden.patch}`,
`environment/{Dockerfile, problem_statement.md}`, and a **`tests/` folder limited to
at most 3 files** (`grade.py`, `config.json`, `test.sh`). Because the test patch is
**embedded inline in `test.sh`** (like `solve.sh` embeds the golden), the shipped
`tests/` holds only `test.sh` (add `grade.py`/`config.json` only if your grading needs
them). Nothing extra inside a task folder. Build/QA helpers (this skill's
`scripts/verify.sh`) live OUTSIDE the task folders.

## Hard rules (non-negotiable)

1. **Two cleanly-separated patches.** The golden = source files ONLY (the real
   fix/feature), saved as `solution/golden.patch`. The test patch = test files ONLY,
   **embedded inline in `tests/test.sh`**. Build each by editing the clone, then
   `git -C clones/<S> --no-pager diff -- <paths>`, then
   `git -C clones/<S> checkout -- <paths>` to reset. **Never leave the clone dirty.**
2. **fail2pass is real and comprehensive.** With ONLY the test patch applied (no
   gold), the new tests must FAIL on baseline; with BOTH applied they must PASS. The
   test patch contains **only NEW F2P tests** — a **comprehensive suite (~10–20, min
   10)** to prevent reward hacking, including one that reproduces the target behavior.
   **Do NOT author new pass2pass tests:** the repo's **existing** suite is the
   pass2pass guard (already baked into the image) — pick a relevant existing subset
   and run it alongside the new tests so a regression fails grading. Tests must verify
   **observable behavior/outcome** (never the file edited, diff shape, or source
   keywords), be deterministic, offline, fast enough for the timeout, and
   **independent of the reference solution** (don't import/call it). If you cannot run
   the toolchain locally, reason carefully from the real source that the new
   assertions fail pre-fix and pass post-fix. Prefer asserting against an
   already-correct oracle in the repo when one exists (rou3 compares interpreted vs
   compiled output this way).
3. **Pin the baseline SHA from the spec** in the Dockerfile (`REPO_SHA`) and in
   `task.toml` (`base_commit`). Use the real upstream repo URL. For pre-fix-parent
   tasks, use that parent SHA — the SHA where the deliverable is ABSENT.
4. **Offline at grade time.** Dockerfile may fetch repo + deps at BUILD time;
   after that the agent and verifier have no network. Bake a pristine copy to
   `/opt/baseline` and restore the test dir(s) from it before grading
   (anti-tamper — the agent must not be able to weaken the verifier).
5. **instruction.md = problem only.** Adapt the spec's non-leaking problem
   statement (and mirror it into `environment/problem_statement.md`). NO file paths
   to edit, NO function/algorithm prescription, NO root-cause/fix hints, NO mention
   of tests/verifier/reward, NO "where to look". Describe observable behavior +
   success criteria. Naming public API/behavior the user wants is fine.
6. **Working dir is `/testbed`** (SWE-Bench Harbor convention).
7. **task.toml** carries the full `[metadata]` (see template): `repo`, `base_commit`,
   `source_type`, `difficulty` + `difficulty_explanation`, `category`, `subcategory`,
   `objective_labels`, `artifact_labels`, `num_f2p_tests`, and `pass_at_k_*` (filled
   after eval). No network at agent/verifier time; `cpus = 2`, `memory_mb = 4096`,
   `storage_mb = 10240`, `gpus = 0`; verifier timeout 1800, agent 3600, build 1800.
8. **`test.sh` and `solve.sh` executable** (`chmod +x`).
9. **Keep image < 10GB, git dir small** — shallow fetch only (`--depth 1`), no
   full history.

## Workflow (per slug)

```
- [ ] Read task_spec.md (base SHA, source_type, category/labels, golden files,
      fail2pass matrix, run cmd, image notes)
- [ ] Confirm repo URL + that clone has the base SHA (git rev-parse / cat-file).
      For PR/commit/issue-based tasks the base SHA is the PRE-FIX PARENT.
- [ ] Build golden.patch: edit SOURCE in clone → diff → reset clone (avg ~350 LoC,
      multi-file; match the canonical upstream fix when PR-based)
- [ ] Build the test patch (~10–20 NEW F2P, incl. a behavior-reproducing case): edit
      TESTS in clone → diff → reset clone, then embed inline in tests/test.sh. (No new
      pass2pass — pick the existing tests/subset to run for regression.)
- [ ] Write the 7 files (mirror the reference task; adapt toolchain); fill task.toml
      [metadata] taxonomy from the spec
- [ ] chmod +x solution/solve.sh tests/test.sh
- [ ] Verify (scripts/verify.sh <S>): golden + embedded test patch apply @ base SHA;
      source/test separation; clone clean; instruction non-leak
- [ ] Report: repo+SHA, source_type, category, files+LoC, #F2P, apply-checks, run cmd,
      one-line fail2pass rationale
```

Always rebuild the diffs **against the base SHA** (use a worktree at that SHA if
the clone HEAD differs), and leave the clone + any worktrees clean.

## Templates (mirror the worked reference)

If a fully worked reference task exists (e.g. `harbor_tasks/rou3/`), read it and
mirror its file shapes. The shapes below are the canonical ones.

### task.toml

```toml
schema_version = "1.3"  # Harbor format version (NOT task version)

[task]
name        = "<owner>/<repo>-<short-slug>"
description = "<one-line task description>"
authors     = [{ name = "Turing", email = "tasks@turing.com" }]
keywords    = ["code", "swe", "<lang>", "<area>"]
metadata    = { vendor = "Turing" }

[environment]
# TODO(pre-submission): pin the digest after `docker push` (…@sha256:<digest>)
docker_image      = "<registry>/<path>/<owner>__<repo>-<slug>:latest"
os                = "linux"
cpus              = 2
memory_mb         = 4096
storage_mb        = 10240
gpus              = 0
gpu_types         = []
build_timeout_sec = 1800
workdir           = "/testbed"
network_mode      = "no-network"
allowed_hosts     = []

[agent]
timeout_sec = 3600

[verifier]
timeout_sec = 1800

[solution]
# solution/solve.sh applies solution/golden.patch

[metadata]
repo                   = "<owner>/<repo>"
base_commit            = "<BASE_SHA>"            # pre-fix parent for PR/commit/issue tasks
source_type            = "PR-based"              # PR-based | commit-based | issue-based | derivation | net-new
difficulty             = "hard"                  # medium | hard
difficulty_explanation = "<why it's hard: reasoning/cross-module/subtlety/domain>"
category               = "<e.g. Software Engineering>"
subcategory            = "<e.g. Feature implementation>"
objective_labels       = ["Implement"]          # multi-label
artifact_labels        = ["Codebase"]           # multi-label
num_f2p_tests          = 0                       # set to the real count (target 10–20)
# TODO(pre-submission): fill measured pass@8 after eval
# pass_at_k_gpt_5_5    = "x/8"
# pass_at_k_opus_4_8   = "x/8"
```

### environment/Dockerfile (shape — adapt base image + dep install per language)

```dockerfile
FROM <base-image>

# Build-time only. Agent + verifier run with no network; everything is baked in.
RUN <install git + ca-certificates + toolchain prereqs>

WORKDIR /testbed

# Pin the baseline commit where the deliverable is absent.
ARG REPO_URL=https://github.com/<owner>/<repo>.git
ARG REPO_SHA=<BASE_SHA>
RUN git init -q . \
    && git remote add origin "$REPO_URL" \
    && git fetch --depth 1 origin "$REPO_SHA" \
    && git checkout -q FETCH_HEAD \
    && git reset --hard -q FETCH_HEAD

# Install deps (build-time network) so grading runs fully offline later.
# Also WARM the offline cache by running the affected suite once if needed
# (e.g. Gradle/Maven so --offline works at grade time).
RUN <install deps>

# Bake a pristine baseline so the verifier can restore test files + detect tamper.
RUN cp -a /testbed /opt/baseline

RUN git -C /testbed add -A \
    && git -C /testbed -c user.email=t@t -c user.name=t commit -q -m baseline --allow-empty

CMD ["bash"]
```

### tests/test.sh (shape — embeds the test patch inline; adapt restored paths + run cmd)

```bash
#!/bin/bash
set -uo pipefail
mkdir -p /logs/verifier
fail() { echo 0 > /logs/verifier/reward.txt; exit 0; }
pass() { echo 1 > /logs/verifier/reward.txt; exit 0; }

cd /testbed || fail

# 1) Restore pristine test dir(s) so source edits stay but tests can't be tampered.
rm -rf /testbed/<TESTDIR>
cp -a /opt/baseline/<TESTDIR> /testbed/<TESTDIR>

# 2) Apply the hidden NEW fail2pass TEST patch (embedded inline so the shipped tests/
#    folder stays within the 3-file limit). Keep the markers verbatim.
cat > /tmp/test_patch.diff << '__TEST_PATCH_EOF__'
<contents of the test-only diff verbatim (~10–20 NEW F2P incl. a behavior-reproducing case)>
__TEST_PATCH_EOF__
git apply --whitespace=nowarn /tmp/test_patch.diff || \
  patch -p1 --fuzz=5 < /tmp/test_patch.diff || fail

# 3) Run OFFLINE: the NEW fail2pass tests AND a relevant subset of the repo's EXISTING
#    tests (pass2pass regression guard — already in the image, not re-authored).
<OFFLINE RUN COMMAND FROM SPEC: new F2P tests + existing pass2pass subset>
status=$?

[ "$status" -eq 0 ] && pass || fail
```

### solution/solve.sh (shape — embed golden inline, apply)

```bash
#!/bin/bash
set -euo pipefail
cd /testbed

cat > /tmp/golden.patch << '__GOLD_PATCH_EOF__'
<contents of solution/golden.patch verbatim>
__GOLD_PATCH_EOF__

git apply --whitespace=nowarn /tmp/golden.patch || patch -p1 --fuzz=5 < /tmp/golden.patch
echo "Applied golden patch."
```

### instruction.md (shape)

Behavior-focused problem statement only: what's wrong / what's wanted, observable
examples, success criteria. No files, no algorithm, no tests/verifier mentions,
no "where to look".

## Per-language Dockerfile / run cues (adapt to the repo)

- **JS/TS**: `FROM node:22-bookworm`; `corepack enable`; install per lockfile
  (`pnpm install --frozen-lockfile` / `npm ci` / `yarn`). Run: `pnpm exec vitest run …` / jest / node test.
- **Python**: `FROM python:3.X-bookworm` (match repo); `pip install -e .[test]`
  or `pip install -r requirements*.txt` + the package. Run: `pytest <paths> -q`.
- **Java**: `FROM eclipse-temurin:<JDK>-jdk` (match what the build needs); use the
  repo's Gradle/Maven wrapper; pre-resolve deps at BUILD and warm the offline
  cache. Run: `./gradlew :<module>:test --offline --no-daemon --tests '…'` or
  `./mvnw -o test -pl <module> -Dtest=…`.
- **C#**: `FROM mcr.microsoft.com/dotnet/sdk:<TFM>`; `dotnet restore` at build.
  Run: `dotnet test <project> --filter … --no-restore` offline.
- **Go**: `FROM golang:1.X`; `go mod download` at build. Run: `go test ./<pkg> -run …`.
- **Rust**: `FROM rust:1.X`; `cargo fetch` / build at build. Run: `cargo test …`.
- Always: shallow-fetch the SHA, install deps, `cp -a /testbed /opt/baseline`,
  commit a clean tree.

## Verify before finishing (and report it)

Use `scripts/verify.sh` (set its `ROOT` to the task set, or pass it). It checks,
**against each task's own base_commit** (worktree if the clone HEAD differs):

- golden.patch applies — OK
- the test patch embedded in tests/test.sh applies — OK (extracted from the heredoc)
- both together apply — OK
- golden = source-only (a `WARN: gold may touch tests` that fires only because a
  SOURCE filename/path contains "Test"/"spec" — e.g. `ParameterizedTest.java`,
  `src/TestFramework/…` — is a false positive; confirm the `+++ b/` targets are
  production source)
- clone left clean (0 dirty lines)

Also confirm by eye: instruction.md (and environment/problem_statement.md) leak
nothing; task.toml `[metadata]` has source_type + category/subcategory + labels +
difficulty; Dockerfile `REPO_SHA` == `base_commit` == spec SHA; the 7 files exist and
scripts are executable. Deep verifier/leakage QA is the `harbor-verifier-check` /
`harbor-task-sanity-check` skills' job.

```bash
bash scripts/verify.sh <S> [<S2> ...]
# whole set:
bash scripts/verify.sh $(ls -1 <root>/harbor_tasks | grep -v '^_')
```

## Final report (per task or batch)

Repo URL + base SHA (+ source_type); category/subcategory + difficulty;
module/toolchain + base image; source files changed + LoC (avg ~350); count of NEW
fail2pass cases (target 10–20) + the existing tests used as pass2pass; the three
apply-checks pass against the base SHA; clone clean; the offline run command; and a
one-line fail2pass rationale (why the new tests fail pre-fix and pass post-fix).

---
name: task_spec_to_harbor_task
description: >-
  Convert a SWE-Bench-style task spec (task_spec.md + a pinned repo
  clone) into ONE complete, runnable Harbor-format task folder — instruction.md,
  task.toml, environment/Dockerfile, solution/{gold_patch.diff,solve.sh},
  tests/{test_patch.diff,test.sh} — with a real source-only golden patch and a
  test-only fail2pass verifier that grades offline by writing a 0/1 reward. Use
  when asked to build/create a Harbor task (or batch of tasks) from task
  specs, to author the golden solution + verifier tests for such tasks, or
  to verify that such Harbor tasks apply cleanly and are non-leaking. Do NOT use
  the harbor-long-range-task-create skill for this — that is for long-horizon
  LLM-judge tasks, not SWE-Bench fail2pass tasks.
---

# Task spec → Harbor task

Convert ONE task spec into ONE complete, correct Harbor SWE-Bench-style task
folder. For a batch, repeat per slug. The golden solution is a real source patch;
the verifier is a real test patch that **fails on baseline, passes after the
gold patch**, graded **offline**.

This is NOT the long-range/LLM-judge Harbor format. Do not invoke
`harbor-long-range-task-create`. There is no LLM judge — grading is a single
deterministic test run that writes `0` or `1` to `/logs/verifier/reward.txt`.

## Inputs (per task slug `<S>`)

- Spec: `<root>/tasks/<S>/task_spec.md` — authoritative. Source of: pinned base
  SHA, golden approach + the exact source files it touches, the fail2pass matrix,
  the offline run command, image/toolchain notes, a non-leaking problem-statement
  draft, and the originality proof.
- Repo: `<root>/clones/<S>/` — real source. Usually already at the baseline SHA;
  confirm with `git -C clones/<S> rev-parse HEAD`. Some tasks pin a **pre-fix
  parent** commit, so the clone HEAD may differ from the spec base SHA — always
  build and verify patches against the **spec base SHA**.

`<root>` is the task set's `initial_task_list/` (or equivalent). Confirm with the
user if ambiguous.

## Output — create EXACTLY these 7 files at `<root>/harbor_tasks/<S>/`

```
<S>/
  instruction.md            # problem statement only — no solution, no leakage
  task.toml                 # config + [metadata] repo/base_commit/difficulty
  environment/Dockerfile    # pin SHA, install deps at BUILD time, bake /opt/baseline
  solution/gold_patch.diff  # golden SOURCE change only (no test files)
  solution/solve.sh         # embeds gold_patch.diff inline + applies it
  tests/test_patch.diff     # fail2pass + pass2pass TEST changes only (no source)
  tests/test.sh             # restore pristine tests, apply test patch, run, write reward
```

Nothing extra inside a task folder. Build/QA helpers (this skill's
`scripts/verify.sh`) live OUTSIDE the task folders.

## Hard rules (non-negotiable)

1. **Two cleanly-separated patches.** `gold_patch.diff` = source files ONLY (the
   real fix/feature). `test_patch.diff` = test files ONLY. Build each by editing
   the clone, then `git -C clones/<S> --no-pager diff -- <paths>`, then
   `git -C clones/<S> checkout -- <paths>` to reset. **Never leave the clone dirty.**
2. **fail2pass is real.** With ONLY the test patch applied (no gold), the new
   tests must FAIL on baseline; with BOTH applied they must PASS. If you cannot
   run the toolchain locally, reason carefully from the real source that the new
   assertions fail pre-fix and pass post-fix. Prefer asserting against an
   already-correct oracle in the repo when one exists (rou3 compares interpreted
   vs compiled output this way).
3. **Pin the baseline SHA from the spec** in the Dockerfile (`REPO_SHA`) and in
   `task.toml` (`base_commit`). Use the real upstream repo URL. For pre-fix-parent
   tasks, use that parent SHA — the SHA where the deliverable is ABSENT.
4. **Offline at grade time.** Dockerfile may fetch repo + deps at BUILD time;
   after that the agent and verifier have no network. Bake a pristine copy to
   `/opt/baseline` and restore the test dir(s) from it before grading
   (anti-tamper).
5. **instruction.md = problem only.** Adapt the spec's non-leaking problem
   statement. NO file paths to edit, NO function/algorithm prescription, NO
   mention of tests/verifier/reward, NO "where to look". Describe observable
   behavior + success criteria. Naming public API/behavior the user wants is fine.
6. **Working dir is `/testbed`** (SWE-Bench Harbor convention).
7. **task.toml**: `difficulty` from spec; `allow_internet = false`; `cpus = 2`,
   `memory_mb = 4096`, `storage_mb = 10240`, `gpus = 0`; verifier timeout 1800,
   agent 3600, build 1800; `[metadata]` includes `repo` and `base_commit`.
8. **`test.sh` and `solve.sh` executable** (`chmod +x`).
9. **Keep image < 10GB, git dir small** — shallow fetch only (`--depth 1`), no
   full history.

## Workflow (per slug)

```
- [ ] Read task_spec.md (base SHA, golden files, fail2pass matrix, run cmd, image notes)
- [ ] Confirm repo URL + that clone has the base SHA (git rev-parse / cat-file)
- [ ] Build gold_patch.diff: edit SOURCE in clone → diff → reset clone
- [ ] Build test_patch.diff: edit TESTS in clone → diff → reset clone
- [ ] Write the 7 files (mirror the reference task; adapt toolchain)
- [ ] chmod +x solution/solve.sh tests/test.sh
- [ ] Verify (scripts/verify.sh <S>): gold/test/both apply @ base SHA; source/test
      separation; clone clean; instruction non-leak
- [ ] Report: repo+SHA, files+LoC, apply-checks, run cmd, one-line fail2pass rationale
```

Always rebuild the diffs **against the base SHA** (use a worktree at that SHA if
the clone HEAD differs), and leave the clone + any worktrees clean.

## Templates (mirror the worked reference)

If a fully worked reference task exists (e.g. `harbor_tasks/rou3/`), read it and
mirror its file shapes. The shapes below are the canonical ones.

### task.toml

```toml
version = "1.0"

[task]
name = "<slug-descriptive-name>"
authors = []
keywords = ["<lang>", "<area>", "<category>"]

[metadata]
author_name = "Task Author"
author_email = "tasks@example.com"
difficulty = "hard"
category = "bug-fix"
tags = ["<lang>", "<area>"]
repo = "<owner>/<repo>"
base_commit = "<BASE_SHA>"

[verifier]
timeout_sec = 1800.0

[agent]
timeout_sec = 3600.0

[environment]
build_timeout_sec = 1800.0
cpus = 2
memory_mb = 4096
storage_mb = 10240
gpus = 0
allow_internet = false
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

### tests/test.sh (shape — adapt restored test paths + run command)

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

# 2) Apply the hidden fail2pass / pass2pass test patch.
git apply --whitespace=nowarn /tests/test_patch.diff || \
  patch -p1 --fuzz=5 < /tests/test_patch.diff || fail

# 3) Run affected suites OFFLINE (fail2pass + pass2pass).
<OFFLINE RUN COMMAND FROM SPEC>
status=$?

[ "$status" -eq 0 ] && pass || fail
```

### solution/solve.sh (shape — embed gold inline, apply)

```bash
#!/bin/bash
set -euo pipefail
cd /testbed

cat > /tmp/gold_patch.diff << '__GOLD_PATCH_EOF__'
<contents of solution/gold_patch.diff verbatim>
__GOLD_PATCH_EOF__

git apply --whitespace=nowarn /tmp/gold_patch.diff || patch -p1 --fuzz=5 < /tmp/gold_patch.diff
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

- gold_patch applies — OK
- test_patch applies — OK
- both together apply — OK
- gold = source-only (a `WARN: gold may touch tests` that fires only because a
  SOURCE filename/path contains "Test"/"spec" — e.g. `ParameterizedTest.java`,
  `src/TestFramework/…` — is a false positive; confirm the `+++ b/` targets are
  production source)
- clone left clean (0 dirty lines)

Also confirm by eye: instruction.md leaks nothing; Dockerfile `REPO_SHA` ==
`base_commit` == spec SHA; the 7 files exist and scripts are executable.

```bash
bash scripts/verify.sh <S> [<S2> ...]
# whole set:
bash scripts/verify.sh $(ls -1 <root>/harbor_tasks | grep -v '^_')
```

## Final report (per task or batch)

Repo URL + base SHA; module/toolchain + base image; source files changed + LoC;
test files + count of new fail2pass cases; the three apply-checks pass against the
base SHA; clone clean; the offline run command; and a one-line fail2pass rationale
(why the new tests fail pre-fix and pass post-fix).

---
name: task_spec_to_harbor_task
description: >-
  Convert a SWE-Bench-style task spec (task_spec.md + a pinned repo
  clone) into ONE complete, runnable Harbor-format task folder — instruction.md,
  task.toml, environment/{Dockerfile,problem_statement.md},
  solution/{golden.patch,solve.sh}, tests/test.sh — with a real new golden
  patch and a comprehensive NEW fail2pass verifier (atleast >5 F2P tests; the repo's existing suite is the pass2pass guard, not re-authored) that
  grades offline by writing a 0/1 reward. task.toml [metadata] carries
  the category/subcategory + objective/artifact labels + source_type + difficulty.
  Use when asked to build/create a Harbor task (or batch of tasks) from task specs, to
  author the golden solution + verifier tests, or to verify that such Harbor tasks
  apply cleanly and are non-leaking. These are net new category of tasks, so these are 
  brand new tasks for which task specs have been created. So the harbor format task is brand new.
  A task requirements file will be optionally provided to give the requirements of these net
  new tasks, make sure those requirements are strictly adhered to when creating the harbor
  format tasks, in additional to the general task requirements mentioned below.
---

# Task spec → Harbor task

Convert ONE task spec into ONE complete, correct Harbor SWE-Bench-style task
folder. For a batch, repeat per slug. The golden solution is a real source patch
matching the task requirements as provided. The verifier is a **comprehensive suite of NEW
fail2pass tests (>5 F2P, including one that reproduces the target behavior)**
that **fails on baseline, passes after the gold patch**, graded **offline**. The
repo's **existing** tests are the **pass2pass** guard (already in the image — run a
relevant subset for regression; do NOT author new pass2pass tests).

Grading is a single deterministic test run that writes `0` or `1` to `/logs/verifier/reward.txt`.

## Inputs (per task slug `<S>`)

- Spec: `<root>/tasks/<S>/task_spec.md` — authoritative. Source of: pinned base
  SHA, source_type, category/subcategory + objective/artifact labels, golden approach
  + the exact source files it touches, the fail2pass matrix (atleast >5 F2P), the offline
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

This matches the submission format: `solution/{solve.sh, golden.patch}`,
`environment/{Dockerfile, problem_statement.md}`, and a **`tests/` folder limited to
at most 3 files** (`grade.py`, `config.json`, `test.sh`). Because the test patch is
**embedded inline in `test.sh`** (like `solve.sh` embeds the golden), the shipped
`tests/` holds only `test.sh` (add `grade.py`/`config.json` only if your grading needs
them). Nothing extra inside a task folder. Build/QA helpers (this skill's
`scripts/verify.sh`) live OUTSIDE the task folders.

## Hard rules (non-negotiable)

1. **Two cleanly-separated patches.** The golden = source files ONLY 
   saved as `solution/golden.patch`. The test patch = test files ONLY,
   **embedded inline in `tests/test.sh`**. Build each by editing the clone, then
   `git -C clones/<S> --no-pager diff -- <paths>`, then
   `git -C clones/<S> checkout -- <paths>` to reset. **Never leave the clone dirty.**
2. **fail2pass is real and comprehensive.** With ONLY the test patch applied (no
   gold), the new tests must FAIL on baseline; with BOTH applied they must PASS. The
   test patch contains **only NEW F2P tests** — a **comprehensive suite (atleast >5, min
   5)** to prevent reward hacking, including one that reproduces the target behavior.
   **Do NOT author new pass2pass tests:** the repo's **existing** suite is the
   pass2pass guard (already baked into the image) — pick a relevant existing subset
   and run it alongside the new tests so a regression fails grading. Tests must verify
   **observable behavior/outcome** (never the file edited, diff shape, or source
   keywords), be deterministic, offline, fast enough for the timeout, and
   **independent of the reference solution** (don't import/call it). If you cannot run
   the toolchain locally, reason carefully from the real source that the new
   assertions fail pre-fix and pass post-fix. Prefer asserting against an
   already-correct oracle in the repo when one exists (rou3 compares interpreted vs
   compiled output this way). **Record the graded test node IDs in `task.toml`
   `[metadata]` (see template): `fail_to_pass` = every NEW test you embedded (its
   length must equal `num_f2p_tests`); `pass_to_pass` = the existing regression
   subset `test.sh` runs.** Write each ID in the test runner's own node-id format —
   the exact string that runner prints/reports — so downstream eval reports can key
   on them: pytest `pkg/test_mod.py::TestClass::test_case[param]`, vitest/jest
   `src/x/foo.test.ts > describe block > it title`, `go test` `./pkg::TestName`,
   cargo `module::tests::case`. Harbor still grades pass/fail from `test.sh`; these
   lists are authoritative metadata for reporting/difficulty.
3. **Pin the baseline SHA from the spec** in the Dockerfile (`REPO_SHA`) and in
   `task.toml` (`base_commit`). Use the real upstream repo URL. For pre-fix-parent
   tasks, use that parent SHA — the SHA where the deliverable is ABSENT.
4. **Offline at grade and run time.** Dockerfile may fetch repo + deps at BUILD time;
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
   `objective_labels`, `artifact_labels`, `num_f2p_tests`, `fail_to_pass` +
   `pass_to_pass` (the graded test node-id lists — see rule 2), and `pass_at_k_*`
   (filled after eval). No network at agent/verifier time; `cpus = 2`, `memory_mb = 4096`,
   `storage_mb = 10240`, `gpus = 0`; verifier timeout 1800, agent 3600, build 1800.
8. **`test.sh` and `solve.sh` executable** (`chmod +x`).
9. **Keep image < 10GB, git dir small** — shallow fetch only (`--depth 1`), no
   full history.

## General Task Requirements (every task created must follow) ##

- **Task statement/description clarity.** Task description must be clear, not too vague. Slightly underspecified
  is fine, but not too much underspecified. It shouldn't be over specified telling the agent what it should do.
  Task description/instruction should stick to just a task, like a formal task spec, without "you" or anything of 
  that sort. Anything that can be inferred from the repo can be avoided in the task instruction. It must be fair,
  so while it's really difficult, make sure it's a fair task. Don't chain multiple requirements to make it difficult.
- **Test to task instruction alignment.** Make sure the tests (f2p tests) have high coverage that cover the task requirements
  really well. Make sure it's aligned with the task instruction and doesn't deviate too much. It's okay to lean on slightly strict
  tests, but don't make them unfair. Make sure tests don't have false positives or false negatives. Ensure it's not pinned to a
  very specific implementation, but slightly generic enough to verify multiple implementations. Make sure tests have clarity and 
  don't cover things that cannot be inferred or derived from the task instruction or the repos. Don't under specify the tests as well,
  make sure they are comprehensive to prevent reward hacking.
- **Gold path clarity and alignment.** Make sure the golden patch is aligned well with the task instruction, and actually solves the task
  and pass all the tests. Make sure the golden patch follows whatever requirements have been provided if they have been provided. 
  Usually tasks are selected such that golden patch will have certain minimum number of lines of code (LOC) and/or also have
  minimum number of non test files edited to make the tasks difficult and long horizon. Ensure it's adhered to. Ensure the golden pathc
  is clear.
- **Task instruction/description realism and difficulty.** The task should be realistic, something that real 
  engineers would solve, not some random difficult puzzles. It must be really difficult for leading frontier models, and
  they are really good. Make sure it's high quality SWE and research based tasks.

## Workflow (per slug)

```
- [ ] Read task_spec.md (base SHA, source_type, category/labels, golden files,
      fail2pass matrix, run cmd, image notes)
- [ ] Confirm repo URL + that clone has the base SHA (git rev-parse / cat-file).
      For PR/commit/issue-based tasks the base SHA is the PRE-FIX PARENT.
- [ ] Build golden.patch: edit SOURCE in clone → diff → reset clone. Make sure it matches
      the task requirements if provided.
- [ ] Build the test patch (> 5 NEW F2P, incl. a behavior-reproducing case): edit
      TESTS in clone → diff → reset clone, then embed inline in tests/test.sh. (No new
      pass2pass — pick the existing tests/subset to run for regression.)
- [ ] Write the 7 files (mirror the reference task; adapt toolchain); fill task.toml
      [metadata] taxonomy from the spec, incl. fail_to_pass / pass_to_pass node IDs
      in the runner's own format (fail_to_pass length == num_f2p_tests)
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
num_f2p_tests          = 0                       # real count; must equal len(fail_to_pass)

# Graded test node IDs in the runner's OWN format (the exact string it reports), so
# eval reports can key on them. fail_to_pass = the NEW tests embedded in tests/test.sh;
# pass_to_pass = the existing regression subset test.sh runs. Harbor still grades via
# test.sh — these are authoritative metadata. Formats: pytest
# "pkg/test_mod.py::TestClass::test_case", vitest/jest
# "src/x/foo.test.ts > describe > it title", go "./pkg::TestName", cargo "mod::tests::case".
fail_to_pass = [
  # "…",  # one entry per NEW F2P test (count == num_f2p_tests)
]
pass_to_pass = [
  # "…",  # the existing tests the run command exercises as the regression guard
]
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

# --no-verify + hooksPath=/dev/null: repos that install husky/lefthook hooks during
# the deps step (e.g. a gitleaks pre-commit) would otherwise abort this baseline commit.
RUN git -C /testbed add -A \
    && git -C /testbed -c core.hooksPath=/dev/null \
       -c user.email=t@t -c user.name=t commit -q --no-verify -m baseline --allow-empty

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
fail2pass cases (target 10–20) + the existing tests used as pass2pass; the
`fail_to_pass` / `pass_to_pass` node-id lists recorded in task.toml (fail_to_pass
count == num_f2p_tests); the three apply-checks pass against the base SHA; clone
clean; the offline run command; and a one-line fail2pass rationale (why the new
tests fail pre-fix and pass post-fix).

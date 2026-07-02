---
name: alibaba-harbor-task-build
description: >-
  Convert a task spec (task_spec.md + pinned repo clone) into ONE complete Alibaba
  Coding Evals Harbor bundle — test/<slug>.json, test-assets/<slug>/ with
  instruction.md, task.toml, environment/{Dockerfile,workspace.tar.gz},
  tests/{test.sh,test_outputs.py}, solution/solve.sh, rubric.md, metadata/,
  runs/, scoring/. Uses embedded fail2pass patches (sample10 pattern) and
  workspace.tar.gz packaging (harbor_case pattern). Use when building Alibaba
  Harbor tasks from task specs. Do NOT use the old SWE-Bench 7-file layout.
---

# Alibaba Harbor task build

Convert ONE `task_spec.md` into ONE complete Alibaba ship bundle. For a batch,
repeat per slug. Grading is **exec-based only** — no LLM judges.

Reference: [`docs/alibaba/README.md`](../../docs/alibaba/README.md) · Worked example:
[`docs/alibaba/sample_task/rou3-repeated-regex-modifier-constraints/`](../../docs/alibaba/sample_task/rou3-repeated-regex-modifier-constraints/)

## Inputs (per task slug `<S>`)

- Spec: `<root>/tasks/<S>/task_spec.md` — pinned SHA, golden approach, fail2pass
  matrix, offline run command, taxonomy tags, Alibaba meta, rubric seeds, problem
  statement draft.
- Repo: `<root>/clones/<S>/` — real source at or containing the base SHA.

`<root>` is the task set directory (contains `tasks/`, `clones/`, `deliverables/`).

## Output — create this tree at `<root>/deliverables/<S>/`

```
<S>/
  test/<S>.json
  test-assets/<S>/
    instruction.md
    task.toml
    environment/Dockerfile
    environment/workspace.tar.gz
    tests/test.sh
    tests/test_outputs.py
    solution/solve.sh
    rubric.md                    # draft from spec rubric seeds; refine in rubric skill
    metadata/author_self_assessment.json
    runs/model_runs.json         # scaffold
    scoring/scoring_summary.json # scaffold
```

## Hard rules (non-negotiable)

1. **Harbor query JSON.** `test/<S>.json`:
   ```json
   {
     "instance_id": "<S>",
     "dataset": "alibaba-coding-evals",
     "split": "test",
     "description": "<same text as instruction.md>"
   }
   ```
2. **Two cleanly-separated patches** (built in clone, embedded in shell scripts):
   - Gold = source files ONLY → embedded in `solution/solve.sh`
   - Test = test files ONLY → embedded in `tests/test.sh`
   Build via edit → `git diff` → reset clone. **Never leave clone dirty.**
3. **fail2pass is real.** Test patch alone FAILS on baseline; gold + test PASS.
4. **workspace.tar.gz** — export pinned clone at base SHA; Dockerfile extracts it
   (no git-fetch at grade time). Use `scripts/pack_workspace.sh`.
5. **Offline at grade time.** Build deps at Docker BUILD; bake `/opt/baseline` for
   test-file restore (anti-tamper).
6. **instruction.md = problem only.** No file paths, no test/verifier mentions.
7. **Working dir `/testbed`** for SWE-style repos (adapt if harbor_case uses `/app`).
8. **task.toml** includes `[metadata]` (`language`=code_lang, `task_type`, `domain`=application)
   and `[alibaba]` (dimension flags, one_sentence_description, why_worth_using,
   status=`draft`). Use official labels from `docs/alibaba/taxonomy_v1.yaml`; legacy
   sample10 names (e.g. `Backend`) map via `application_aliases`.
9. **test_outputs.py** — patch-artifact mirror (base64) for Terminal-Bench compat;
   shell verifier embeds patch directly so Python is optional at grade time.
10. **Scripts executable** (`chmod +x` on test.sh, solve.sh).

## Workflow (per slug)

```
- [ ] Read task_spec.md (SHA, golden, tests, taxonomy, Alibaba meta, rubric seeds)
- [ ] Confirm clone has base SHA (worktree if HEAD differs)
- [ ] Build gold_patch + test_patch in clone → diff → reset
- [ ] pack_workspace.sh → environment/workspace.tar.gz
- [ ] Write all bundle files (mirror docs/alibaba/sample_task/)
- [ ] Draft rubric.md from spec rubric seeds
- [ ] Scaffold metadata/, runs/, scoring/
- [ ] chmod +x tests/test.sh solution/solve.sh
- [ ] Verify: scripts/verify.sh <S>
- [ ] Report: repo+SHA, bundle file count, apply-checks, fail2pass rationale
```

## Templates

### task.toml

```toml
version = "1.0"

[task]
name = "<S>"
authors = []
keywords = ["<program_lang>", "<task_type>", "<domain>"]

[metadata]
author_name = "Task Author"
author_email = "tasks@example.com"
difficulty = "hard-candidate"
category = "<task_type>"
tags = ["<program_lang>", "<task_type>", "<domain>"]
repo = "<owner>/<repo>"
base_commit = "<BASE_SHA>"
language = "<program_lang>"
task_type = "<task_type>"
domain = "<domain>"

[alibaba]
status = "draft"
one_sentence_description = "<from spec>"
why_worth_using = "<from spec>"
long_horizon = <true|false>
must_follow_claude_md = <true|false>
requires_subagents = <true|false>
requires_web_search = <true|false>
requires_multi_turn_user = <true|false>
requires_skills = <true|false>
requires_context_management = <true|false>
requires_mcp = <true|false>
requires_custom_tools = <true|false>

[verifier]
timeout_sec = 1800.0

[agent]
timeout_sec = <10800.0 if long_horizon else 3600.0>

[environment]
build_timeout_sec = 1800.0
cpus = 2
memory_mb = 4096
storage_mb = 10240
gpus = 0
allow_internet = false
```

### environment/Dockerfile (workspace.tar.gz pattern)

```dockerfile
FROM <base-image>

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates patch \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /testbed

COPY workspace.tar.gz /tmp/workspace.tar.gz
RUN tar -xzf /tmp/workspace.tar.gz -C /testbed \
    && rm /tmp/workspace.tar.gz \
    && git init -q . \
    && git add -A \
    && git -c user.email=t@t -c user.name=t commit -q -m source-baseline --allow-empty

RUN <install deps + warm offline cache>

RUN cp -a /testbed /opt/baseline

RUN git -C /testbed add -A \
    && git -C /testbed -c user.email=t@t -c user.name=t commit -q -m baseline --allow-empty

CMD ["bash"]
```

### tests/test.sh (embedded patch pattern)

```bash
#!/bin/bash
set -uo pipefail
mkdir -p /logs/verifier
fail() { echo 0 > /logs/verifier/reward.txt; exit 0; }
pass() { echo 1 > /logs/verifier/reward.txt; exit 0; }

cd /testbed || fail

# Restore pristine test file(s)
cp /opt/baseline/<test-path> <test-path> || fail

cat > /tmp/alibaba_test_patch.diff <<'__ALIBABA_TEST_PATCH__'
<test_patch.diff contents verbatim>
__ALIBABA_TEST_PATCH__

git apply --whitespace=nowarn /tmp/alibaba_test_patch.diff || \
  patch -p1 --fuzz=5 < /tmp/alibaba_test_patch.diff || fail

<OFFLINE RUN COMMAND>
[ $? -eq 0 ] && pass || fail
```

### solution/solve.sh

```bash
#!/bin/bash
set -euo pipefail
cd /testbed

cat > /tmp/alibaba_gold_patch.diff <<'__ALIBABA_GOLD_PATCH__'
<gold_patch.diff contents verbatim>
__ALIBABA_GOLD_PATCH__

git apply --whitespace=nowarn /tmp/alibaba_gold_patch.diff || \
  patch -p1 --fuzz=5 < /tmp/alibaba_gold_patch.diff
echo "Applied golden patch."
```

### Scaffold files

**metadata/author_self_assessment.json** — from spec Alibaba meta section.

**runs/model_runs.json** — copy schema from sample10; `status: NEEDS_REAL_MODEL_RUNS`.

**scoring/scoring_summary.json** — `{ "status": "NEEDS_SECOND_SCORING", "rubric_test_alignment": true, "scorer_agreement": null }`.

## Per-language cues

Same as prior skill: match base image + lockfile install + offline test command.
Always package workspace at pinned SHA, pre-cache deps at build, bake `/opt/baseline`.

## Verify before finishing

```bash
ROOT=<root> bash skills/alibaba-harbor-task-build/scripts/verify.sh <S>
ROOT=<root> bash skills/alibaba-harbor-task-build/scripts/pack_workspace.sh <S>  # if rebuilding tarball
```

See `scripts/verify.sh` for the full checklist.

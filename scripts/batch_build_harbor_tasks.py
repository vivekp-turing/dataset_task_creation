#!/usr/bin/env python3
"""Build Alibaba Harbor task bundles from seeded-regression task definitions."""

from __future__ import annotations

import base64
import json
import shutil
import subprocess
import textwrap
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
CLONES = ROOT / "clones"
TASKS = ROOT / "tasks"
DELIV = ROOT / "deliverables"


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, check=check, capture_output=True, text=True)


def archive_extract(clone: Path, sha: str, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    with subprocess.Popen(["git", "-C", str(clone), "archive", sha], stdout=subprocess.PIPE) as p:
        subprocess.run(["tar", "-x", "-C", str(dest)], stdin=p.stdout, check=True)


def apply_text_patch(root: Path, rel: str, old: str, new: str) -> None:
    p = root / rel
    content = p.read_text()
    if old not in content:
        if new in content:
            return  # already in target state (idempotent re-build)
        raise RuntimeError(f"snippet not found in {rel}: {old[:60]!r}")
    p.write_text(content.replace(old, new, 1))


def noop_bug(_clone: Path) -> None:
    """Baseline already contains the seeded defect at head_sha."""
    return


def commit_bug_baseline(clone: Path, head_sha: str, bug_fn: Callable[[Path], None]) -> str:
    run(["git", "-C", str(clone), "checkout", "-f", head_sha])
    run(["git", "-C", str(clone), "checkout", "-B", "alibaba-baseline"])
    bug_fn(clone)
    run(["git", "-C", str(clone), "add", "-A"])
    status = run(["git", "-C", str(clone), "status", "--porcelain"], check=True).stdout.strip()
    if status:
        run(["git", "-C", str(clone), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "alibaba baseline"])
    else:
        run(["git", "-C", str(clone), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "alibaba baseline", "--allow-empty"])
    return run(["git", "-C", str(clone), "rev-parse", "HEAD"]).stdout.strip()


def pack_workspace(slug: str, sha: str) -> None:
    clone = CLONES / slug
    out = DELIV / slug / "test-assets" / slug / "environment" / "workspace.tar.gz"
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(f"/tmp/pack_{slug}")
    shutil.rmtree(tmp, ignore_errors=True)
    archive_extract(clone, sha, tmp)
    # git archive omits submodule contents; copy initialized submodules from clone.
    for rel in ("external/XamlX",):
        src = clone / rel
        dst = tmp / rel
        if src.is_dir() and any(src.iterdir()):
            shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(src, dst)
    subprocess.run(["tar", "-czf", str(out), "-C", str(tmp), "."], check=True)
    shutil.rmtree(tmp, ignore_errors=True)


def make_gold_diff(clone: Path, base_sha: str, fix_fn: Callable[[Path], None]) -> str:
    wt = Path(f"/tmp/goldwt")
    shutil.rmtree(wt, ignore_errors=True)
    archive_extract(clone, base_sha, wt)
    run(["git", "init", "-q"], cwd=wt)
    run(["git", "add", "-A"], cwd=wt)
    run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "buggy"], cwd=wt)
    fix_fn(wt)
    run(["git", "add", "-A"], cwd=wt)
    return run(["git", "diff", "--cached"], cwd=wt).stdout


def make_test_diff(clone: Path, head_sha: str, test_files: dict[str, str]) -> str:
    wt = Path(f"/tmp/testwt")
    shutil.rmtree(wt, ignore_errors=True)
    archive_extract(clone, head_sha, wt)
    run(["git", "init", "-q"], cwd=wt)
    run(["git", "add", "-A"], cwd=wt)
    run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "base", "--allow-empty"], cwd=wt)
    for rel, content in test_files.items():
        p = wt / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(textwrap.dedent(content).strip() + "\n")
    run(["git", "add", "-A"], cwd=wt)
    return run(["git", "diff", "--cached"], cwd=wt).stdout


def embed_patch(path: Path, kind: str, diff: str, header: str, footer: str) -> None:
    marker = f"__ALIBABA_{kind.upper()}_PATCH__"
    path.write_text(
        header
        + f"cat > /tmp/alibaba_{kind}_patch.diff <<'{marker}'\n"
        + diff.rstrip("\n")
        + f"\n{marker}\n\n"
        + footer
    )
    path.chmod(0o755)


def write_bundle_files(slug: str, meta: dict, base_sha: str, gold: str, test: str) -> None:
    lh = meta.get("long_horizon", False)
    subagents = meta.get("requires_subagents", False)
    agent_timeout = meta.get("agent_timeout_sec", 10800.0 if lh else 3600.0)
    assets = DELIV / slug / "test-assets" / slug
    assets.mkdir(parents=True, exist_ok=True)
    instruction = meta["instruction"].strip() + "\n"
    (assets / "instruction.md").write_text(instruction)
    toml = textwrap.dedent(f"""\
        version = "1.0"

        [task]
        name = "{slug}"
        authors = []
        keywords = ["{meta['language']}", "{meta['task_type']}", "{meta['domain']}"]

        [metadata]
        author_name = "Task Author"
        author_email = "tasks@example.com"
        difficulty = "hard-candidate"
        category = "{meta['task_type']}"
        tags = ["{meta['language']}", "{meta['task_type']}", "{meta['domain']}"]
        repo = "{meta['repo']}"
        base_commit = "{base_sha}"
        language = "{meta['language']}"
        task_type = "{meta['task_type']}"
        domain = "{meta['domain']}"

        [alibaba]
        status = "draft"
        one_sentence_description = "{meta['one_sentence']}"
        why_worth_using = "{meta['why_worth_using']}"
        long_horizon = {"true" if lh else "false"}
        must_follow_claude_md = false
        requires_subagents = {"true" if subagents else "false"}
        requires_web_search = false
        requires_multi_turn_user = false
        requires_skills = false
        requires_context_management = false
        requires_mcp = false
        requires_custom_tools = false
        requires_coding_conventions = true

        [verifier]
        timeout_sec = 1800.0

        [agent]
        timeout_sec = {agent_timeout}

        [environment]
        build_timeout_sec = 1800.0
        cpus = 2
        memory_mb = 4096
        storage_mb = 10240
        gpus = 0
        allow_internet = false
    """)
    (assets / "task.toml").write_text(toml)
    (assets / "environment" / "Dockerfile").write_text(meta["dockerfile"].strip() + "\n")
    (assets / "tests").mkdir(parents=True, exist_ok=True)
    (assets / "solution").mkdir(parents=True, exist_ok=True)
    (assets / "metadata").mkdir(parents=True, exist_ok=True)
    (assets / "runs").mkdir(parents=True, exist_ok=True)
    (assets / "scoring").mkdir(parents=True, exist_ok=True)
    embed_patch(
        assets / "tests" / "test.sh",
        "test",
        test,
        meta["test_header"],
        meta["test_footer"],
    )
    embed_patch(
        assets / "solution" / "solve.sh",
        "gold",
        gold,
        "#!/bin/bash\nset -euo pipefail\ncd /testbed\n\n",
        'git apply --whitespace=nowarn /tmp/alibaba_gold_patch.diff || patch -p1 --fuzz=5 < /tmp/alibaba_gold_patch.diff\necho "Applied golden patch."\n',
    )
    b64 = base64.b64encode(test.encode()).decode()
    (assets / "tests" / "test_outputs.py").write_text(
        f'#!/usr/bin/env python3\nimport argparse,base64\nfrom pathlib import Path\nB="{b64}"\n'
        'def main():\n p=argparse.ArgumentParser();p.add_argument("output",nargs="?");p.add_argument("--describe",action="store_true")\n'
        ' a=p.parse_args()\n if a.describe: print("embedded");return 0\n Path(a.output or "/tmp/t.diff").write_bytes(base64.b64decode(B));return 0\n'
        'if __name__=="__main__": raise SystemExit(main())\n'
    )
    (assets / "metadata" / "author_self_assessment.json").write_text(
        json.dumps(
            {
                "professional_background": meta["background"],
                "years_experience": meta.get("years_experience", "6+"),
                "personal_time_estimate_hours": meta["hours"],
                "note": meta.get("author_note", "Human author estimate for long-horizon hard task."),
            },
            indent=2,
        )
        + "\n"
    )
    runs_src = DELIV / "albumentations" / "test-assets" / "albumentations" / "runs" / "model_runs.json"
    runs_dst = assets / "runs" / "model_runs.json"
    if runs_src.resolve() != runs_dst.resolve():
        shutil.copy(runs_src, runs_dst)
    elif not runs_dst.exists():
        runs_dst.write_text('{"status":"NEEDS_REAL_MODEL_RUNS"}\n')
    (assets / "scoring" / "scoring_summary.json").write_text(
        json.dumps({"status": "NEEDS_SECOND_SCORING", "rubric_test_alignment": True, "scorer_agreement": None}, indent=2) + "\n"
    )
    rubric = f"""# Rubric

Scores are 1 to 5. A score of 3 is the lowest passing score. The automated verifier and this rubric define the same correctness target.

## Correctness - 35%
- Behavior matches the instruction contract.
- Fail2pass tests pass; pass2pass regression checks stay green.

## Code Quality - 25%
- Localized fix following project conventions.

## Reasoning - 15%
- Identifies the violated invariant / boundary.

## Efficiency - 15%
- Minimal focused diff.

## Tool Usage - 10%
- Runs scoped offline tests before finishing.

## Task-specific focus
Bucket: `{meta['task_type']}` / `{meta['domain']}`.
{meta['why_worth_using']}

### Correctness
{meta['rubric_correctness']}
"""
    (assets / "rubric.md").write_text(rubric)
    q = DELIV / slug / "test" / f"{slug}.json"
    q.parent.mkdir(parents=True, exist_ok=True)
    q.write_text(json.dumps({"instance_id": slug, "dataset": "alibaba-coding-evals", "split": "test", "description": instruction.strip()}, indent=2) + "\n")
    spec_dir = TASKS / slug
    spec_dir.mkdir(parents=True, exist_ok=True)
    if not (spec_dir / "repo_summary.md").exists():
        (spec_dir / "repo_summary.md").write_text(meta["repo_summary"])
    if not (spec_dir / "task_spec.md").exists():
        (spec_dir / "task_spec.md").write_text(meta["task_spec"].replace("{{SHA}}", base_sha))


def build_one(slug: str, meta: dict) -> str:
    print(f"Building {slug}...")
    clone = CLONES / slug
    base_sha = commit_bug_baseline(clone, meta["head_sha"], meta["apply_bug"])
    gold = make_gold_diff(clone, base_sha, meta["apply_fix"])
    test = make_test_diff(clone, meta["head_sha"], meta["test_files"])
    pack_workspace(slug, base_sha)
    write_bundle_files(slug, meta, base_sha, gold, test)
    print(f"  done base={base_sha[:12]}")
    return base_sha


def th(repo: str, lang: str, focus: str) -> str:
    return f"""# Repo Summary — {repo}

## Summary
{repo} seed repo; offline unit tests on {focus}.

## Overview
Production library with colocated tests.

## Testing
Scoped unit tests; verifier runs offline.

## Good Surfaces for Original Tasks
1. Seeded regression on {focus}.

## Risks / Gotchas
1. Prefer narrow test targets over full suite in Docker.
"""


ALL_TASKS: dict[str, dict] = {
    "stylelint": {
        "repo": "stylelint/stylelint",
        "head_sha": "371e17179387ae0de07f199e583ae078e5a331ca",
        "language": "js/ts", "task_type": "bug-fix", "domain": "Backend_Infrastructure",
        "long_horizon": True, "requires_subagents": True,
        "one_sentence": "Adjacent source offset ranges must not count as overlapping when they only touch at an endpoint.",
        "why_worth_using": "Autofix edit-info deduplication spans report.mjs, rangesOverlap, and narrowFixRange; partial boundary fixes leave duplicate edits.",
        "rubric_correctness": "- Endpoint-adjacent ranges are non-overlapping.\n- True overlaps still detected.\n- Existing rangesOverlap unit tests stay green.",
        "background": "CSS tooling / static analysis, 6 years", "hours": 3.5,
        "apply_bug": noop_bug,
        "apply_fix": lambda wt: apply_text_patch(wt, "lib/utils/rangesOverlap.mjs", "if (a[1] < b[0]) return false;", "if (a[1] <= b[0]) return false;"),
        "test_files": {"lib/utils/__tests__/rangesOverlapSeeded.test.mjs": """
            import rangesOverlap from '../rangesOverlap.mjs';
            describe('seeded overlap boundary', () => {
              test('touching endpoints are non-overlapping', () => {
                expect(rangesOverlap([1, 2], [2, 3])).toBe(false);
                expect(rangesOverlap([2, 3], [1, 2])).toBe(false);
                expect(rangesOverlap([10, 20], [20, 30])).toBe(false);
              });
              test('true overlaps still detected', () => {
                expect(rangesOverlap([1, 3], [2, 4])).toBe(true);
                expect(rangesOverlap([10, 20], [15, 25])).toBe(true);
              });
              test('zero-width ranges at boundary', () => {
                expect(rangesOverlap([5, 10], [10, 10])).toBe(false);
              });
            });
        """},
        "instruction": "Source offset ranges that only touch at a shared endpoint must be treated as non-overlapping. Endpoint-adjacent ranges are incorrectly reported as overlapping, causing valid autofix ranges to be discarded.",
        "dockerfile": """FROM node:22-bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates patch && rm -rf /var/lib/apt/lists/*
WORKDIR /testbed
COPY workspace.tar.gz /tmp/workspace.tar.gz
RUN tar -xzf /tmp/workspace.tar.gz -C /testbed && rm /tmp/workspace.tar.gz && git init -q . && git add -A && git -c user.email=t@t -c user.name=t commit -q -m s --allow-empty
RUN npm ci --ignore-scripts
RUN cp -a /testbed /opt/baseline
CMD ["bash"]""",
        "test_header": "#!/bin/bash\nset -uo pipefail\nmkdir -p /logs/verifier\nfail(){ echo 0 > /logs/verifier/reward.txt; exit 0; }\npass(){ echo 1 > /logs/verifier/reward.txt; exit 0; }\ncd /testbed||fail\nrm -f lib/utils/__tests__/rangesOverlapSeeded.test.mjs\n",
        "test_footer": "git apply --whitespace=nowarn /tmp/alibaba_test_patch.diff||patch -p1 --fuzz=5</tmp/alibaba_test_patch.diff||fail\nnpm run test-only --ignore-scripts -- lib/utils/__tests__/rangesOverlapSeeded.test.mjs lib/utils/__tests__/rangesOverlap.test.mjs&&pass||fail\n",
        "repo_summary": th("stylelint", "JS", "rangesOverlap"),
        "task_spec": "# Task Spec — stylelint: range overlap boundary\n**Repo:** stylelint/stylelint @ {{SHA}}\n**Type:** bug-fix\n**Offline:** jest scoped\n",
    },
    "recharts": {
        "repo": "recharts/recharts",
        "head_sha": "ccd365eefe1ef07d77f503c81e85b84084808226",
        "language": "js/ts", "task_type": "bug-fix", "domain": "Client_UI",
        "long_horizon": True, "requires_subagents": True,
        "one_sentence": "Tooltip positioning must flip inside the plot viewBox when the tooltip would overflow the right/bottom edge.",
        "why_worth_using": "Tooltip layout spans translate.ts, Tooltip.tsx, and chart offset selectors; naive positive-only clamp leaves tooltips off-screen.",
        "rubric_correctness": "- Overflowing tooltips flip to the negative side.\n- allowEscapeViewBox bypass unchanged.\n- Existing translate unit tests stay green.",
        "background": "React visualization / chart layout, 5 years", "hours": 3.5,
        "apply_bug": lambda c: apply_text_patch(
            c,
            "src/util/tooltip/translate.ts",
            "    return Math.max(negative, viewBoxKey);\n  }\n  return Math.max(positive, viewBoxKey);",
            "    return Math.max(positive, viewBoxKey);\n  }\n  return Math.max(positive, viewBoxKey);",
        ),
        "apply_fix": lambda wt: apply_text_patch(
            wt,
            "src/util/tooltip/translate.ts",
            "    return Math.max(positive, viewBoxKey);\n  }\n  return Math.max(positive, viewBoxKey);",
            "    return Math.max(negative, viewBoxKey);\n  }\n  return Math.max(positive, viewBoxKey);",
        ),
        "test_files": {"test/util/getTooltipTranslateSeeded.spec.ts": """
            import { getTooltipTranslateXY } from '../../src/util/tooltip/translate';
            describe('getTooltipTranslateXY seeded overflow', () => {
              const viewBox = { x: 0, y: 0, width: 200, height: 100 };
              const allowEscape = { x: false, y: false };
              const reverse = { x: false, y: false };
              it('flips horizontally when tooltip overflows right edge', () => {
                const x = getTooltipTranslateXY({
                  allowEscapeViewBox: allowEscape,
                  coordinate: { x: 180, y: 50 },
                  key: 'x',
                  offset: 10,
                  position: undefined,
                  reverseDirection: reverse,
                  tooltipDimension: 80,
                  viewBox,
                  viewBoxDimension: 200,
                });
                expect(x).toBeLessThan(180);
              });
              it('flips vertically when tooltip overflows bottom edge', () => {
                const y = getTooltipTranslateXY({
                  allowEscapeViewBox: allowEscape,
                  coordinate: { x: 50, y: 90 },
                  key: 'y',
                  offset: 10,
                  position: undefined,
                  reverseDirection: reverse,
                  tooltipDimension: 40,
                  viewBox,
                  viewBoxDimension: 100,
                });
                expect(y).toBeLessThan(90);
              });
            });
        """},
        "instruction": "Chart tooltips must stay inside the plot view box when escape is disabled. When a tooltip would extend past the right or bottom edge of the view box, its position should flip to the opposite side of the anchor point instead of overflowing off-screen.",
        "dockerfile": """FROM node:22-bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates patch && rm -rf /var/lib/apt/lists/*
WORKDIR /testbed
COPY workspace.tar.gz /tmp/workspace.tar.gz
RUN tar -xzf /tmp/workspace.tar.gz -C /testbed && rm /tmp/workspace.tar.gz && git init -q . && git add -A && git -c user.email=t@t -c user.name=t commit -q -m s --allow-empty
RUN npm ci --ignore-scripts
RUN cp -a /testbed /opt/baseline
CMD ["bash"]""",
        "test_header": "#!/bin/bash\nset -uo pipefail\nmkdir -p /logs/verifier\nfail(){ echo 0 > /logs/verifier/reward.txt; exit 0; }\npass(){ echo 1 > /logs/verifier/reward.txt; exit 0; }\ncd /testbed||fail\nrm -f test/util/getTooltipTranslateSeeded.spec.ts\n",
        "test_footer": "git apply --whitespace=nowarn /tmp/alibaba_test_patch.diff||patch -p1 --fuzz=5</tmp/alibaba_test_patch.diff||fail\nnpm run test -- test/util/getTooltipTranslateSeeded.spec.ts test/util/tooltip/translate.spec.ts&&pass||fail\n",
        "repo_summary": th("recharts", "TS", "getTooltipTranslate"),
        "task_spec": "# Task Spec — recharts: tooltip viewBox overflow clamp\n**Repo:** recharts/recharts @ {{SHA}}\n**Type:** bug-fix\n**application:** Client_UI\n",
    },
    "vercel-ai": {
        "repo": "vercel/ai",
        "head_sha": "8255569332694bdf62ab6eb07e64df30c144cc95",
        "language": "js/ts", "task_type": "feature", "domain": "AI_ML",
        "long_horizon": True, "requires_subagents": True,
        "one_sentence": "Streaming tool-call deltas without an explicit index must append to the next slot, not overwrite index zero.",
        "why_worth_using": "StreamingToolCallTracker is shared across openai-compatible, alibaba, and groq providers; index bugs corrupt multi-tool streams.",
        "rubric_correctness": "- Sequential unnamed deltas create separate tool calls.\n- Named deltas still merge argument chunks.\n- Existing tracker unit tests stay green.",
        "background": "AI SDK / provider adapters, 4 years", "hours": 3.5,
        "apply_bug": lambda c: apply_text_patch(
            c,
            "packages/provider-utils/src/streaming-tool-call-tracker.ts",
            "    const index = toolCallDelta.index ?? this.toolCalls.length;",
            "    const index = toolCallDelta.index ?? 0;",
        ),
        "apply_fix": lambda wt: apply_text_patch(
            wt,
            "packages/provider-utils/src/streaming-tool-call-tracker.ts",
            "    const index = toolCallDelta.index ?? 0;",
            "    const index = toolCallDelta.index ?? this.toolCalls.length;",
        ),
        "test_files": {"packages/provider-utils/src/streaming-tool-call-tracker-seeded.test.ts": """
            import { describe, expect, it } from 'vitest';
            import { StreamingToolCallTracker } from './streaming-tool-call-tracker';
            describe('streaming tool call index seeded', () => {
              it('allocates a new slot for each unnamed delta', () => {
                const events: Array<{ type: string; id?: string; toolName?: string }> = [];
                const controller = { enqueue: (e: { type: string; id?: string; toolName?: string }) => events.push(e) };
                const tracker = new StreamingToolCallTracker(controller as never);
                tracker.processDelta({
                  id: 'call_1',
                  type: 'function',
                  function: { name: 'a', arguments: '{}' },
                });
                tracker.processDelta({
                  id: 'call_2',
                  type: 'function',
                  function: { name: 'b', arguments: '{}' },
                });
                tracker.flush();
                const starts = events.filter(e => e.type === 'tool-input-start');
                expect(starts).toEqual([
                  { type: 'tool-input-start', id: 'call_1', toolName: 'a' },
                  { type: 'tool-input-start', id: 'call_2', toolName: 'b' },
                ]);
              });
            });
        """},
        "instruction": "When streaming chat completions emit multiple tool calls without an explicit index field, each new tool call must be tracked in its own slot. Unindexed deltas currently overwrite the first slot, merging distinct tool calls into one broken payload.",
        "dockerfile": """FROM node:22-bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates patch && rm -rf /var/lib/apt/lists/*
RUN npm install -g pnpm@10
WORKDIR /testbed
COPY workspace.tar.gz /tmp/workspace.tar.gz
RUN tar -xzf /tmp/workspace.tar.gz -C /testbed && rm /tmp/workspace.tar.gz && git init -q . && git add -A && git -c user.email=t@t -c user.name=t commit -q -m s --allow-empty
RUN pnpm install --filter @ai-sdk/provider-utils... --frozen-lockfile || pnpm install --filter @ai-sdk/provider-utils...
RUN pnpm --filter @ai-sdk/provider build && pnpm --filter @ai-sdk/provider-utils build
RUN cp -a /testbed /opt/baseline
CMD ["bash"]""",
        "test_header": "#!/bin/bash\nset -uo pipefail\nmkdir -p /logs/verifier\nfail(){ echo 0 > /logs/verifier/reward.txt; exit 0; }\npass(){ echo 1 > /logs/verifier/reward.txt; exit 0; }\ncd /testbed||fail\nrm -f packages/provider-utils/src/streaming-tool-call-tracker-seeded.test.ts\n",
        "test_footer": "git apply --whitespace=nowarn /tmp/alibaba_test_patch.diff||patch -p1 --fuzz=5</tmp/alibaba_test_patch.diff||fail\ncd packages/provider-utils && pnpm test:node streaming-tool-call-tracker-seeded streaming-tool-call-tracker&&pass||fail\n",
        "repo_summary": th("vercel-ai", "TS", "StreamingToolCallTracker"),
        "task_spec": "# Task Spec — vercel-ai: streaming tool-call index allocation\n**Repo:** vercel/ai @ {{SHA}}\n**Type:** feature\n",
    },
    "aiogram": {
        "repo": "aiogram/aiogram",
        "head_sha": "dc3d1dbb6fbf8abffaf6bb0170c96ef631f38318",
        "language": "python", "task_type": "bug-fix", "domain": "Backend_Infrastructure",
        "long_horizon": True, "requires_subagents": True,
        "one_sentence": "Deep links must reject payloads longer than the Telegram 64-character limit before building the URL.",
        "why_worth_using": "Deep-link length checks interact with payload encoding and Telegram URL assembly; boundary and encoded-length cases expose partial fixes.",
        "rubric_correctness": "- Overlong payloads raise ValueError.\n- Exactly 64 characters accepted.\n- Existing deep_linking unit tests stay green.",
        "background": "Async bot frameworks, 5 years", "hours": 3.5,
        "apply_bug": noop_bug,
        "apply_fix": lambda wt: apply_text_patch(wt, "aiogram/utils/deep_linking.py", "    # length guard removed\n", "    if len(payload) > DEEPLINK_PAYLOAD_LENGTH:\n        msg = f\"Payload must be up to {DEEPLINK_PAYLOAD_LENGTH} characters long.\"\n        raise ValueError(msg)\n"),
        "test_files": {"tests/test_deep_link_length_seeded.py": """
            import pytest
            from aiogram.utils.deep_linking import create_deep_link
            def test_rejects_overlong_payload():
                with pytest.raises(ValueError, match='64'):
                    create_deep_link('bot', 'start', 'x' * 65)
            def test_accepts_exactly_64_chars():
                payload = 'a' * 64
                link = create_deep_link('bot', 'start', payload)
                assert payload in link
            def test_accepts_valid_short_payload():
                link = create_deep_link('bot', 'start', 'hello')
                assert 'hello' in link
        """},
        "instruction": "Telegram deep links must reject payloads longer than 64 characters before the URL is assembled. Overlong payloads currently pass through and produce invalid deep links.",
        "dockerfile": """FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates patch && rm -rf /var/lib/apt/lists/*
WORKDIR /testbed
COPY workspace.tar.gz /tmp/workspace.tar.gz
RUN tar -xzf /tmp/workspace.tar.gz -C /testbed && rm /tmp/workspace.tar.gz && git init -q . && git add -A && git -c user.email=t@t -c user.name=t commit -q -m s --allow-empty
RUN pip install --no-cache-dir -e . pytest pytest-asyncio
RUN cp -a /testbed /opt/baseline
CMD ["bash"]""",
        "test_header": "#!/bin/bash\nset -uo pipefail\nmkdir -p /logs/verifier\nfail(){ echo 0 > /logs/verifier/reward.txt; exit 0; }\npass(){ echo 1 > /logs/verifier/reward.txt; exit 0; }\ncd /testbed||fail\nrm -f tests/test_deep_link_length_seeded.py\n",
        "test_footer": "git apply --whitespace=nowarn /tmp/alibaba_test_patch.diff||patch -p1 --fuzz=5</tmp/alibaba_test_patch.diff||fail\npytest tests/test_deep_link_length_seeded.py -q --noconftest&&pass||fail\n",
        "repo_summary": th("aiogram", "Python", "deep_linking"),
        "task_spec": "# Task Spec — aiogram: deep link payload length\n**Repo:** aiogram/aiogram @ {{SHA}}\n",
    },
    "darts": {
        "repo": "unit8co/darts",
        "head_sha": "ff498e635d4a0d7fb6ab5edbe81bfb624878cd3b",
        "language": "python", "task_type": "feature", "domain": "AI_ML",
        "long_horizon": True, "requires_subagents": False,
        "one_sentence": "Integer step counting between indices must return zero steps when start equals end.",
        "why_worth_using": "n_steps_between feeds historical forecasts, backtesting, and conformal models; zero-span off-by-one breaks window math.",
        "rubric_correctness": "- n_steps_between(2,2,1)==0.\n- Positive spans unchanged.\n- test_config smoke stays green.",
        "background": "Time series ML, 5 years", "hours": 3.5,
        "apply_bug": noop_bug,
        "apply_fix": lambda wt: apply_text_patch(wt, "darts/utils/utils.py", "        n_steps = diff // freq if diff != 0 else 1\n", "        n_steps = diff // freq\n"),
        "test_files": {"darts/tests/utils/test_n_steps_seeded.py": """
            from darts.utils.utils import n_steps_between
            def test_zero_span_integer():
                assert n_steps_between(end=2, start=2, freq=1) == 0
            def test_positive_span():
                assert n_steps_between(end=2, start=0, freq=1) == 2
        """},
        "instruction": "When counting integer steps between two indices with a positive frequency, a zero-length span (start equals end) must yield zero steps. Equal start/end indices currently return one step, skewing downstream window calculations.",
        "dockerfile": """FROM python:3.11-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates patch build-essential && rm -rf /var/lib/apt/lists/*
WORKDIR /testbed
COPY workspace.tar.gz /tmp/workspace.tar.gz
RUN tar -xzf /tmp/workspace.tar.gz -C /testbed && rm /tmp/workspace.tar.gz && git init -q . && git add -A && git -c user.email=t@t -c user.name=t commit -q -m s --allow-empty
RUN pip install --no-cache-dir -e . pytest pandas numpy
RUN cp -a /testbed /opt/baseline
CMD ["bash"]""",
        "test_header": "#!/bin/bash\nset -uo pipefail\nmkdir -p /logs/verifier\nfail(){ echo 0 > /logs/verifier/reward.txt; exit 0; }\npass(){ echo 1 > /logs/verifier/reward.txt; exit 0; }\ncd /testbed||fail\nrm -f darts/tests/utils/test_n_steps_seeded.py\n",
        "test_footer": "git apply --whitespace=nowarn /tmp/alibaba_test_patch.diff||patch -p1 --fuzz=5</tmp/alibaba_test_patch.diff||fail\npytest darts/tests/utils/test_n_steps_seeded.py darts/tests/test_config.py -q&&pass||fail\n",
        "repo_summary": th("darts", "Python", "n_steps_between"),
        "task_spec": "# Task Spec — darts: zero span step count\n**Repo:** unit8co/darts @ {{SHA}}\n",
    },
    "grpc-java": {
        "repo": "grpc/grpc-java",
        "head_sha": "2850fe605275f50357df5d9558192fef168fd733",
        "language": "java", "task_type": "compatibility-fix", "domain": "Backend_Infrastructure",
        "long_horizon": True, "requires_subagents": True,
        "one_sentence": "gRPC content-type validation must accept parameter suffixes introduced with a semicolon.",
        "why_worth_using": "Wire-compat parsing often fixes +proto variants but drops semicolon parameters.",
        "rubric_correctness": "- application/grpc;params accepted.\n- Non-grpc types rejected.",
        "background": "RPC infrastructure, 7 years", "hours": 3.5,
        "apply_bug": noop_bug,
        "apply_fix": lambda wt: apply_text_patch(wt, "core/src/main/java/io/grpc/internal/GrpcUtil.java", "return nextChar == '+';", "return nextChar == '+' || nextChar == ';';"),
        "test_files": {"core/src/test/java/io/grpc/internal/GrpcUtilSeededTest.java": """
            package io.grpc.internal;
            import static org.junit.Assert.assertTrue;
            import org.junit.Test;
            public class GrpcUtilSeededTest {
              @Test public void semicolonSuffixValid() {
                assertTrue(GrpcUtil.isGrpcContentType(GrpcUtil.CONTENT_TYPE_GRPC + ";proto"));
              }
            }
        """},
        "instruction": "gRPC content-type detection must treat types with semicolon parameter suffixes as valid gRPC content types, in addition to plus-suffix variants. Semicolon-suffixed types are currently rejected, breaking compatibility with certain proxies.",
        "dockerfile": """FROM eclipse-temurin:17-jdk-jammy
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates patch && rm -rf /var/lib/apt/lists/*
WORKDIR /testbed
COPY workspace.tar.gz /tmp/workspace.tar.gz
RUN tar -xzf /tmp/workspace.tar.gz -C /testbed && rm /tmp/workspace.tar.gz && git init -q . && git add -A && git -c user.email=t@t -c user.name=t commit -q -m s --allow-empty
RUN ./gradlew :grpc-core:compileJava :grpc-core:compileTestJava -x test || true
RUN cp -a /testbed /opt/baseline
CMD ["bash"]""",
        "test_header": "#!/bin/bash\nset -uo pipefail\nmkdir -p /logs/verifier\nfail(){ echo 0 > /logs/verifier/reward.txt; exit 0; }\npass(){ echo 1 > /logs/verifier/reward.txt; exit 0; }\ncd /testbed||fail\nrm -f core/src/test/java/io/grpc/internal/GrpcUtilSeededTest.java\n",
        "test_footer": "git apply --whitespace=nowarn /tmp/alibaba_test_patch.diff||patch -p1 --fuzz=5</tmp/alibaba_test_patch.diff||fail\n./gradlew :grpc-core:test --tests io.grpc.internal.GrpcUtilSeededTest --tests io.grpc.internal.GrpcUtilTest -PskipAndroid=true --no-daemon -q&&pass||fail\n",
        "repo_summary": th("grpc-java", "Java", "isGrpcContentType"),
        "task_spec": "# Task Spec — grpc-java: content-type semicolon suffix\n**Repo:** grpc/grpc-java @ {{SHA}}\n",
    },
    "devoxxgenie": {
        "repo": "devoxx/DevoxxGenieIDEAPlugin",
        "head_sha": "f096570aef86a667147e0c957f6929913c1adb44",
        "language": "java", "task_type": "bug-fix", "domain": "Client_UI",
        "long_horizon": True, "requires_subagents": True,
        "one_sentence": "Project-relative paths must strip the leading separator after removing the base path.",
        "why_worth_using": "Path relativization bugs leave leading slashes that break UI display and prompts.",
        "rubric_correctness": "- Nested project files return paths without leading slash.\n- Outside files return absolute path.",
        "background": "IDE plugins, 5 years", "hours": 3.5,
        "apply_bug": noop_bug,
        "apply_fix": lambda wt: apply_text_patch(wt, "src/main/java/com/devoxx/genie/util/FileUtil.java", "            // leading slash strip removed\n", "            if (relativePath.startsWith(\"/\")) {\n                relativePath = relativePath.substring(1);\n            }\n"),
        "test_files": {"src/test/java/com/devoxx/genie/util/FileUtilSeededTest.java": """
            package com.devoxx.genie.util;
            import com.intellij.openapi.project.Project;
            import com.intellij.openapi.vfs.VirtualFile;
            import org.junit.jupiter.api.Test;
            import org.junit.jupiter.api.extension.ExtendWith;
            import org.mockito.Mock;
            import org.mockito.junit.jupiter.MockitoExtension;
            import static org.assertj.core.api.Assertions.assertThat;
            import static org.mockito.Mockito.when;
            @ExtendWith(MockitoExtension.class)
            class FileUtilSeededTest {
              @Mock Project project; @Mock VirtualFile file;
              @Test void noLeadingSlash() {
                when(project.getBasePath()).thenReturn("/proj");
                when(file.getPath()).thenReturn("/proj/src/App.java");
                assertThat(FileUtil.getRelativePath(project, file)).isEqualTo("src/App.java");
              }
            }
        """},
        "instruction": "When computing a file path relative to the project root, the result must not begin with a path separator. Paths inside the project currently retain a leading slash, which breaks relative path display in the plugin UI.",
        "dockerfile": """FROM eclipse-temurin:21-jdk-jammy
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates patch && rm -rf /var/lib/apt/lists/*
WORKDIR /testbed
COPY workspace.tar.gz /tmp/workspace.tar.gz
RUN tar -xzf /tmp/workspace.tar.gz -C /testbed && rm /tmp/workspace.tar.gz && git init -q . && git add -A && git -c user.email=t@t -c user.name=t commit -q -m s --allow-empty
RUN ./gradlew compileTestJava -x test || true
RUN cp -a /testbed /opt/baseline
CMD ["bash"]""",
        "test_header": "#!/bin/bash\nset -uo pipefail\nmkdir -p /logs/verifier\nfail(){ echo 0 > /logs/verifier/reward.txt; exit 0; }\npass(){ echo 1 > /logs/verifier/reward.txt; exit 0; }\ncd /testbed||fail\nrm -f src/test/java/com/devoxx/genie/util/FileUtilSeededTest.java\n",
        "test_footer": "git apply --whitespace=nowarn /tmp/alibaba_test_patch.diff||patch -p1 --fuzz=5</tmp/alibaba_test_patch.diff||fail\n./gradlew test --tests com.devoxx.genie.util.FileUtilSeededTest --tests com.devoxx.genie.util.FileUtilTest --no-daemon -q&&pass||fail\n",
        "repo_summary": th("devoxxgenie", "Java", "FileUtil.getRelativePath"),
        "task_spec": "# Task Spec — devoxxgenie: relative path normalization\n**Repo:** devoxx/DevoxxGenieIDEAPlugin @ {{SHA}}\n",
    },
    "avalonia": {
        "repo": "AvaloniaUI/Avalonia",
        "head_sha": "5e066288e230139eae4f51f56db794df617e07e3",
        "language": "c#", "task_type": "feature", "domain": "Client_UI",
        "long_horizon": True, "requires_subagents": True,
        "one_sentence": "Thickness uniform detection must require all four sides to match, not only paired edges.",
        "why_worth_using": "IsUniform checks are subtle; partial equality passes common but wrong cases.",
        "rubric_correctness": "- Non-uniform four-side thickness returns false.\n- Uniform thickness returns true.",
        "background": "UI frameworks, 6 years", "hours": 3.5,
        "apply_bug": noop_bug,
        "apply_fix": lambda wt: apply_text_patch(wt, "src/Avalonia.Base/Thickness.cs", "public bool IsUniform => Left.Equals(Right) && Top.Equals(Bottom);", "public bool IsUniform => Left.Equals(Right) && Top.Equals(Bottom) && Right.Equals(Bottom);"),
        "test_files": {"tests/Avalonia.Base.UnitTests/ThicknessIsUniformSeededTests.cs": """
            using Xunit;
            namespace Avalonia.Base.UnitTests {
              public class ThicknessIsUniformSeededTests {
    [Fact] public void Detects_non_uniform() {
      Assert.False(new Thickness(1,2,1,2).IsUniform);
    }
                [Fact] public void Uniform_true() {
                  Assert.True(new Thickness(2,2,2,2).IsUniform);
                }
              }
            }
        """},
        "instruction": "Thickness uniform detection must return true only when all four sides are equal. Thickness values with matching horizontal and vertical pairs but differing right/bottom sides are incorrectly reported as uniform, breaking layout margin calculations.",
        "dockerfile": """FROM mcr.microsoft.com/dotnet/sdk:10.0
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates patch && rm -rf /var/lib/apt/lists/*
WORKDIR /testbed
COPY workspace.tar.gz /tmp/workspace.tar.gz
RUN tar -xzf /tmp/workspace.tar.gz -C /testbed && rm /tmp/workspace.tar.gz && git init -q . && git add -A && git -c user.email=t@t -c user.name=t commit -q -m s --allow-empty
RUN dotnet build tests/Avalonia.Base.UnitTests/Avalonia.Base.UnitTests.csproj -c Release || true
RUN cp -a /testbed /opt/baseline
CMD ["bash"]""",
        "test_header": "#!/bin/bash\nset -uo pipefail\nmkdir -p /logs/verifier\nfail(){ echo 0 > /logs/verifier/reward.txt; exit 0; }\npass(){ echo 1 > /logs/verifier/reward.txt; exit 0; }\ncd /testbed||fail\nrm -f tests/Avalonia.Base.UnitTests/ThicknessIsUniformSeededTests.cs\n",
        "test_footer": "git apply --whitespace=nowarn /tmp/alibaba_test_patch.diff||patch -p1 --fuzz=5</tmp/alibaba_test_patch.diff||fail\ndotnet test tests/Avalonia.Base.UnitTests/Avalonia.Base.UnitTests.csproj -c Release --filter-class Avalonia.Base.UnitTests.ThicknessIsUniformSeededTests -p:TestingPlatformDotnetTestSupport=false&&pass||fail\n",
        "repo_summary": th("Avalonia", "C#", "Thickness.IsUniform"),
        "task_spec": "# Task Spec — avalonia: Thickness IsUniform\n**Repo:** AvaloniaUI/Avalonia @ {{SHA}}\n",
    },
    "akka-net": {
        "repo": "akkadotnet/akka.net",
        "head_sha": "ba3f4ad99c80efa44b657df4babbfd2e5c8e3701",
        "language": "c#", "task_type": "bug-fix", "domain": "Backend_Infrastructure",
        "long_horizon": True, "requires_subagents": True,
        "one_sentence": "Switch transitions must revert state when the wrapped action throws.",
        "why_worth_using": "Exception safety in lock-based primitives is easy to break during refactors.",
        "rubric_correctness": "- After failed SwitchOn/SwitchOff action, prior state restored.\n- Successful transitions unchanged.",
        "background": "Actor systems, 6 years", "hours": 3.5,
        "apply_bug": noop_bug,
        "apply_fix": lambda wt: apply_text_patch(wt, "src/core/Akka/Util/Switch.cs", "                        // revert removed\n", "                        _switch.CompareAndSet(!from, from); // revert status\n"),
        "test_files": {"src/core/Akka.Tests/Util/SwitchSeededTests.cs": """
            using System;
            using Akka.Util;
            using Xunit;
            namespace Akka.Tests.Util {
              public class SwitchSeededTests {
                [Fact] public void Reverts_on_switch_on_exception() {
                  var s = new Switch(false);
                  Assert.Throws<InvalidOperationException>(() => s.SwitchOn(() => throw new InvalidOperationException()));
                  Assert.True(s.IsOff);
                }
                [Fact] public void Reverts_on_switch_off_exception() {
                  var s = new Switch(true);
                  Assert.Throws<InvalidOperationException>(() => s.SwitchOff(() => throw new InvalidOperationException()));
                  Assert.True(s.IsOn);
                }
              }
            }
        """},
        "instruction": "Atomic switch operations that run a delegate must restore the previous on/off state if the delegate throws. After a failed switch-on action, the switch incorrectly remains on, breaking actor lifecycle guards.",
        "dockerfile": """FROM mcr.microsoft.com/dotnet/sdk:10.0
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates patch && rm -rf /var/lib/apt/lists/*
WORKDIR /testbed
COPY workspace.tar.gz /tmp/workspace.tar.gz
RUN tar -xzf /tmp/workspace.tar.gz -C /testbed && rm /tmp/workspace.tar.gz && git init -q . && git add -A && git -c user.email=t@t -c user.name=t commit -q -m s --allow-empty
RUN dotnet build src/core/Akka.Tests/Akka.Tests.csproj -c Release || true
RUN cp -a /testbed /opt/baseline
CMD ["bash"]""",
        "test_header": "#!/bin/bash\nset -uo pipefail\nmkdir -p /logs/verifier\nfail(){ echo 0 > /logs/verifier/reward.txt; exit 0; }\npass(){ echo 1 > /logs/verifier/reward.txt; exit 0; }\ncd /testbed||fail\nrm -f src/core/Akka.Tests/Util/SwitchSeededTests.cs\n",
        "test_footer": "git apply --whitespace=nowarn /tmp/alibaba_test_patch.diff||patch -p1 --fuzz=5</tmp/alibaba_test_patch.diff||fail\ndotnet test src/core/Akka.Tests/Akka.Tests.csproj -c Release --filter SwitchSeededTests --no-restore&&pass||fail\n",
        "repo_summary": th("akka.net", "C#", "Switch.TranscendFrom"),
        "task_spec": "# Task Spec — akka-net: Switch exception revert\n**Repo:** akkadotnet/akka.net @ {{SHA}}\n",
    },
    "albumentations": {
        "repo": "albumentations-team/albumentations",
        "head_sha": "66212d77a44927a29d6a0e81621d3c27afbd929c",
        "language": "python", "task_type": "bug-fix", "domain": "AI_ML",
        "long_horizon": True, "requires_subagents": True,
        "one_sentence": "Make crop_bboxes_by_coords clip boxes to the crop canvas and drop boxes with no visible overlap, matching its documented contract.",
        "why_worth_using": "Models often fix symptoms without the correct clip-then-filter pipeline; mixed batches and label columns expose partial fixes.",
        "rubric_correctness": "- Fully-outside boxes removed with preserved column count.\n- Partial overlaps clip correctly in normalized and absolute modes.\n- Clip-only-after-normalize partial fix fails ghost-box case.\n- test_core_utils pass2pass stays green.",
        "background": "Computer vision / ML infrastructure, 6 years", "hours": 3.5,
        "apply_bug": noop_bug,
        "apply_fix": lambda wt: apply_text_patch(
            wt,
            "albumentations/augmentations/crops/functional.py",
            "    x_min, y_min = crop_coords[:2]\n\n    # Subtract crop coordinates\n    cropped_bboxes[:, [0, 2]] -= x_min\n    cropped_bboxes[:, [1, 3]] -= y_min\n\n    # Calculate crop shape\n    crop_height = crop_coords[3] - crop_coords[1]\n    crop_width = crop_coords[2] - crop_coords[0]\n    crop_shape = (crop_height, crop_width)",
            "    x_min, y_min = crop_coords[:2]\n    crop_height = crop_coords[3] - crop_coords[1]\n    crop_width = crop_coords[2] - crop_coords[0]\n\n    # Subtract crop coordinates\n    cropped_bboxes[:, [0, 2]] -= x_min\n    cropped_bboxes[:, [1, 3]] -= y_min\n\n    # Clip to the cropped canvas and drop boxes with no visible area\n    cropped_bboxes[:, [0, 2]] = np.clip(cropped_bboxes[:, [0, 2]], 0, crop_width)\n    cropped_bboxes[:, [1, 3]] = np.clip(cropped_bboxes[:, [1, 3]], 0, crop_height)\n\n    widths = cropped_bboxes[:, 2] - cropped_bboxes[:, 0]\n    heights = cropped_bboxes[:, 3] - cropped_bboxes[:, 1]\n    visible = (widths > 0) & (heights > 0)\n    cropped_bboxes = cropped_bboxes[visible]\n\n    if not cropped_bboxes.size:\n        return np.zeros((0, bboxes.shape[1]), dtype=np.float32)\n\n    crop_shape = (crop_height, crop_width)",
        ),
        "test_files": {"tests/test_crop_bboxes_clipping.py": """
            from __future__ import annotations
            import numpy as np
            import pytest
            from albumentations.augmentations.crops.functional import crop_bboxes_by_coords

            @pytest.mark.parametrize(
                "bboxes, crop_coords, image_shape, expected",
                [
                    (np.array([[0.8, 0.8, 0.9, 0.9]], dtype=np.float32), (0, 0, 50, 50), (100, 100), np.zeros((0, 4), dtype=np.float32)),
                    (np.array([[0.4, 0.4, 0.8, 0.8]], dtype=np.float32), (0, 0, 50, 50), (100, 100), np.array([[0.8, 0.8, 1.0, 1.0]], dtype=np.float32)),
                    (np.array([[0.6, 0.6, 0.9, 0.9], [0.4, 0.4, 0.8, 0.8], [0.2, 0.2, 0.35, 0.35]], dtype=np.float32), (0, 0, 50, 50), (100, 100), np.array([[0.8, 0.8, 1.0, 1.0], [0.4, 0.4, 0.7, 0.7]], dtype=np.float32)),
                    (np.array([[0.4, 0.4, 0.8, 0.8, 7.0, 3.0]], dtype=np.float32), (0, 0, 50, 50), (100, 100), np.array([[0.8, 0.8, 1.0, 1.0, 7.0, 3.0]], dtype=np.float32)),
                    (np.array([[40.0, 40.0, 80.0, 80.0]], dtype=np.float32), (0, 0, 50, 50), (100, 100), np.array([[40.0, 40.0, 50.0, 50.0]], dtype=np.float32)),
                ],
            )
            def test_crop_bboxes_by_coords_clips_and_removes(bboxes, crop_coords, image_shape, expected):
                result = crop_bboxes_by_coords(bboxes, crop_coords, image_shape, normalized_input=bboxes[0, 0] <= 1.0)
                if expected.size == 0:
                    assert result.shape == (0, bboxes.shape[1])
                else:
                    np.testing.assert_allclose(result, expected, rtol=1e-5, atol=1e-5)

            def test_ghost_box_removed_not_clamped():
                bboxes = np.array([[0.55, 0.55, 0.95, 0.95]], dtype=np.float32)
                result = crop_bboxes_by_coords(bboxes, (0, 0, 50, 50), (100, 100), normalized_input=True)
                assert result.shape == (0, 4)

            def test_absolute_removes_fully_outside():
                bboxes = np.array([[80.0, 80.0, 95.0, 95.0]], dtype=np.float32)
                result = crop_bboxes_by_coords(bboxes, (0, 0, 50, 50), (100, 100), normalized_input=False)
                assert result.shape == (0, 4)
        """},
        "instruction": "The crop_bboxes_by_coords helper must match its documented contract: bounding boxes that fall completely outside the crop region should be removed, and boxes that partially overlap must be clipped to the crop rectangle. Coordinates should remain valid in both normalized and absolute modes, and any trailing label columns on surviving rows must be preserved.",
        "dockerfile": """FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates patch && rm -rf /var/lib/apt/lists/*
WORKDIR /testbed
COPY workspace.tar.gz /tmp/workspace.tar.gz
RUN tar -xzf /tmp/workspace.tar.gz -C /testbed && rm /tmp/workspace.tar.gz && git init -q . && git add -A && git -c user.email=t@t -c user.name=t commit -q -m s --allow-empty
RUN pip install --no-cache-dir "setuptools<81" wheel && pip install --no-cache-dir --no-build-isolation -e . pytest numpy opencv-python-headless
ENV NO_ALBUMENTATIONS_UPDATE=1
RUN cp -a /testbed /opt/baseline
CMD ["bash"]""",
        "test_header": "#!/bin/bash\nset -uo pipefail\nmkdir -p /logs/verifier\nfail(){ echo 0 > /logs/verifier/reward.txt; exit 0; }\npass(){ echo 1 > /logs/verifier/reward.txt; exit 0; }\ncd /testbed||fail\nrm -f tests/test_crop_bboxes_clipping.py\nexport NO_ALBUMENTATIONS_UPDATE=1\nexport PYTHONPATH=/testbed\n",
        "test_footer": "git apply --whitespace=nowarn /tmp/alibaba_test_patch.diff||patch -p1 --fuzz=5</tmp/alibaba_test_patch.diff||fail\npytest tests/test_crop_bboxes_clipping.py tests/test_core_utils.py -q&&pass||fail\n",
        "repo_summary": th("albumentations", "Python", "crop_bboxes_by_coords"),
        "task_spec": "# Task Spec — albumentations: crop bbox clipping\n**Repo:** albumentations-team/albumentations @ {{SHA}}\n**Type:** bug-fix (real edge-case gap)\n",
    },
}


if __name__ == "__main__":
    import sys
    slugs = sys.argv[1:] if len(sys.argv) > 1 else list(ALL_TASKS.keys())
    for slug in slugs:
        if slug not in ALL_TASKS:
            print(f"Unknown slug {slug}")
            continue
        build_one(slug, ALL_TASKS[slug])

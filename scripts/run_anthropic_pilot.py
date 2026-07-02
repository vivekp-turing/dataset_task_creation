#!/usr/bin/env python3
"""Run Anthropic agent pilots against Alibaba Harbor bundles (Docker + tool use + subagents)."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DELIV = ROOT / "deliverables"
PILOT_RUNS = ROOT / "pilot_runs"

MODEL_IDS = {
    "claude-opus-4.6": "claude-opus-4-6",
    "claude-sonnet-4.6": "claude-sonnet-4-6",
}


def load_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        return key
    for rel in (".env.pilot", ".env"):
        p = ROOT / rel
        if not p.is_file():
            continue
        for line in p.read_text().splitlines():
            line = line.strip()
            if line.startswith("ANTHROPIC_API_KEY="):
                return line.split("=", 1)[1].strip().strip("'\"")
    raise SystemExit(
        "ANTHROPIC_API_KEY not set. Export it or create .env.pilot with:\n"
        "  ANTHROPIC_API_KEY=sk-ant-...\n"
    )


def run(cmd: list[str], **kw: Any) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


@dataclass
class DockerSession:
    slug: str
    image: str
    container: str
    tests_dir: Path

    @classmethod
    def start(cls, slug: str) -> DockerSession:
        env_dir = DELIV / slug / "test-assets" / slug / "environment"
        tests_dir = DELIV / slug / "test-assets" / slug / "tests"
        image = f"harbor-pilot-{slug}"
        r = run(["docker", "build", "-t", image, str(env_dir)])
        if r.returncode != 0:
            raise RuntimeError(f"docker build failed for {slug}:\n{r.stderr[-4000:]}")
        name = f"pilot-{slug}-{uuid.uuid4().hex[:8]}"
        r = run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                name,
                "-v",
                f"{tests_dir}:/tests:ro",
                image,
                "sleep",
                "7200",
            ]
        )
        if r.returncode != 0:
            raise RuntimeError(f"docker run failed: {r.stderr}")
        sess = cls(slug=slug, image=image, container=name, tests_dir=tests_dir)
        sess.reset_workspace()
        return sess

    def exec(self, bash_cmd: str, timeout: int = 600) -> tuple[int, str]:
        r = run(
            ["docker", "exec", self.container, "bash", "-lc", bash_cmd],
            timeout=timeout,
        )
        out = (r.stdout or "") + (r.stderr or "")
        return r.returncode, out[-12000:]

    def reset_workspace(self) -> None:
        self.exec("rm -rf /logs/verifier && mkdir -p /logs/verifier && cp -a /opt/baseline/. /testbed/.")

    def stop(self) -> None:
        run(["docker", "rm", "-f", self.container], check=False)

    def grade(self) -> tuple[int, str]:
        code, out = self.exec(
            "mkdir -p /logs/verifier && bash /tests/test.sh 2>&1; "
            "echo REWARD=$(cat /logs/verifier/reward.txt 2>/dev/null || echo 0)",
            timeout=1800,
        )
        m = re.search(r"REWARD=(\d)", out)
        reward = int(m.group(1)) if m else 0
        return reward, out[-8000:]


def tool_definitions() -> list[dict[str, Any]]:
    return [
        {
            "name": "bash",
            "description": "Run a bash command in /testbed inside the task Docker container.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to run."},
                },
                "required": ["command"],
            },
        },
        {
            "name": "read_file",
            "description": "Read a text file under /testbed (max 200 lines from offset).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "offset": {"type": "integer", "default": 1},
                    "limit": {"type": "integer", "default": 200},
                },
                "required": ["path"],
            },
        },
        {
            "name": "write_file",
            "description": "Write or overwrite a file under /testbed.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
        {
            "name": "spawn_subagent",
            "description": (
                "Delegate a focused exploration subtask to a subagent (read-only bash/grep). "
                "Use for mapping code across subsystems before editing."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "objective": {
                        "type": "string",
                        "description": "What the subagent should investigate and report.",
                    },
                },
                "required": ["objective"],
            },
        },
        {
            "name": "submit",
            "description": "Signal that you are done editing and ready for grading.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                },
                "required": ["summary"],
            },
        },
    ]


@dataclass
class PilotResult:
    slug: str
    model: str
    attempt: int
    passed: bool
    reward: int
    turns: int
    env_failure: bool
    trajectory_path: str
    notes: str = ""


def run_subagent(client: Any, session: DockerSession, objective: str, api_key: str) -> str:
    """Short read-only exploration subagent."""
    sub_tools = [
        {
            "name": "bash",
            "description": "Read-only exploration: grep, find, head, cat, ls in /testbed.",
            "input_schema": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
    ]
    system = (
        "You are a read-only code exploration subagent. Only run non-destructive commands "
        "(grep, find, head, cat, ls, sed -n). Work in /testbed. Summarize findings concisely."
    )
    messages: list[dict[str, Any]] = [{"role": "user", "content": objective}]
    for _ in range(12):
        resp = client.messages.create(
            model=MODEL_IDS["claude-sonnet-4.6"],
            max_tokens=4096,
            system=system,
            tools=sub_tools,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": resp.content})
        if resp.stop_reason != "tool_use":
            texts = [b.text for b in resp.content if hasattr(b, "text")]
            return "\n".join(texts) if texts else "(no summary)"
        tool_results = []
        for block in resp.content:
            if block.type != "tool_use":
                continue
            cmd = block.input.get("command", "")
            if any(x in cmd for x in ("rm ", "mv ", ">", "tee ", "git apply", "patch")):
                out = "BLOCKED: destructive command not allowed in subagent"
            else:
                _, out = session.exec(f"cd /testbed && {cmd}", timeout=120)
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": out,
                }
            )
        messages.append({"role": "user", "content": tool_results})
    return "(subagent turn limit reached)"


def run_attempt(
    slug: str,
    model_label: str,
    attempt: int,
    max_turns: int,
    use_subagents: bool,
) -> PilotResult:
    import anthropic

    api_key = load_api_key()
    client = anthropic.Anthropic(api_key=api_key)
    model_id = MODEL_IDS[model_label]

    instruction = (DELIV / slug / "test-assets" / slug / "instruction.md").read_text().strip()
    traj_dir = PILOT_RUNS / slug / model_label.replace(".", "_")
    traj_dir.mkdir(parents=True, exist_ok=True)
    traj_path = traj_dir / f"attempt_{attempt}.jsonl"

    session = DockerSession.start(slug)
    env_failure = False
    turns = 0
    submitted = False
    trajectory: list[dict[str, Any]] = []

    system = f"""You are a software engineer fixing a bug in a real open-source repository.

Task instruction:
{instruction}

Environment:
- Code is at /testbed inside Docker.
- Edit source files to satisfy the instruction.
- Use spawn_subagent for cross-directory exploration before large edits.
- When done, call submit() — we will run the Harbor verifier.

Constraints:
- Do not modify test files added by the verifier patch.
- Prefer shared helpers over duplicating logic.
- Run targeted tests when helpful (pytest/npm test scoped to your area).
"""

    messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": "Fix the task per the instruction. Explore the codebase, implement the fix, then submit.",
        }
    ]

    try:
        for turn in range(max_turns):
            turns = turn + 1
            resp = client.messages.create(
                model=model_id,
                max_tokens=8192,
                system=system,
                tools=tool_definitions(),
                messages=messages,
            )
            trajectory.append({"turn": turns, "response": resp.model_dump()})
            messages.append({"role": "assistant", "content": resp.content})

            if resp.stop_reason == "end_turn":
                messages.append(
                    {
                        "role": "user",
                        "content": "Continue working or call submit when the fix is complete.",
                    }
                )
                continue

            if resp.stop_reason != "tool_use":
                break

            tool_results = []
            for block in resp.content:
                if block.type != "tool_use":
                    continue
                name = block.name
                inp = block.input
                if name == "bash":
                    code, out = session.exec(f"cd /testbed && {inp['command']}", timeout=600)
                    content = f"exit={code}\n{out}"
                elif name == "read_file":
                    path = inp["path"].lstrip("/")
                    off = int(inp.get("offset", 1))
                    lim = int(inp.get("limit", 200))
                    code, out = session.exec(
                        f"sed -n '{off},{off + lim - 1}p' /testbed/{path} 2>&1 | head -c 50000",
                        timeout=60,
                    )
                    content = out if code == 0 else f"read error exit={code}\n{out}"
                elif name == "write_file":
                    path = inp["path"].lstrip("/")
                    content_raw = inp["content"]
                    escaped = content_raw.replace("'", "'\"'\"'")
                    code, out = session.exec(
                        f"mkdir -p \"$(dirname /testbed/{path})\" && "
                        f"printf '%s' '{escaped}' > /testbed/{path}",
                        timeout=60,
                    )
                    content = f"write exit={code}\n{out}"
                elif name == "spawn_subagent" and use_subagents:
                    content = run_subagent(client, session, inp["objective"], api_key)
                elif name == "spawn_subagent":
                    content = "Subagents disabled for this run."
                elif name == "submit":
                    submitted = True
                    content = "Submitted. Awaiting verifier."
                else:
                    content = f"Unknown tool {name}"
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": content}
                )
            messages.append({"role": "user", "content": tool_results})
            if submitted:
                break
    except Exception as e:
        env_failure = True
        trajectory.append({"error": str(e)})
    finally:
        with traj_path.open("w") as f:
            for row in trajectory:
                f.write(json.dumps(row, default=str) + "\n")

        try:
            reward, grade_out = session.grade()
        except Exception as e:
            env_failure = True
            reward = 0
            grade_out = str(e)
        session.stop()

    passed = reward == 1 and not env_failure
    notes = "" if not env_failure else f"env_failure: {grade_out[:500]}"
    return PilotResult(
        slug=slug,
        model=model_label,
        attempt=attempt,
        passed=passed,
        reward=reward,
        turns=turns,
        env_failure=env_failure,
        trajectory_path=str(traj_path.relative_to(ROOT)),
        notes=notes,
    )


def merge_model_runs(slug: str, results: list[PilotResult]) -> None:
    runs_path = DELIV / slug / "test-assets" / slug / "runs" / "model_runs.json"
    data = json.loads(runs_path.read_text())
    data.setdefault("models", {})
    data["fixed_agent_setup"] = {
        "agent": "scripts/run_anthropic_pilot.py (Anthropic tool-use loop in Docker)",
        "subagents": "spawn_subagent tool (claude-sonnet-4.6, read-only exploration)",
        "same_tools_for_all_models": True,
    }

    by_model: dict[str, list[PilotResult]] = {}
    for r in results:
        by_model.setdefault(r.model, []).append(r)

    for model, attempts in by_model.items():
        existing = {e["attempt"]: e for e in data["models"].get(model, {}).get("attempts", [])}
        for r in sorted(attempts, key=lambda x: x.attempt):
            existing[r.attempt] = {
                "attempt": r.attempt,
                "passed": r.passed,
                "turns": r.turns,
                "env_failure": r.env_failure,
                "trajectory_path": r.trajectory_path,
                "reward": r.reward,
                "notes": r.notes,
            }
        entries = [existing[k] for k in sorted(existing)]
        pass_rate = sum(1 for e in entries if e["passed"]) / len(entries) if entries else 0.0
        mean_turns = sum(e["turns"] for e in entries) / len(entries) if entries else 0.0
        data["models"][model] = {
            "attempts": entries,
            "pass_rate": round(pass_rate, 3),
            "mean_turns": round(mean_turns, 1),
        }

    if data["models"]:
        data["status"] = "ANTHROPIC_PARTIAL"
    anthropic_models = {"claude-opus-4.6", "claude-sonnet-4.6"}
    if anthropic_models.issubset(data["models"].keys()):
        all_have_5 = all(len(data["models"][m].get("attempts", [])) >= 5 for m in anthropic_models)
        if all_have_5:
            data["status"] = "ANTHROPIC_COMPLETE"
    data["note"] = (
        "Anthropic pilots via run_anthropic_pilot.py. "
        "Qwen/GLM still NEEDS_REAL_MODEL_RUNS for full Alibaba acceptance."
    )
    runs_path.write_text(json.dumps(data, indent=2) + "\n")


def main() -> None:
    p = argparse.ArgumentParser(description="Run Harbor Anthropic pilots")
    p.add_argument("slug", help="Task slug")
    p.add_argument("--model", default="claude-opus-4.6", choices=list(MODEL_IDS))
    p.add_argument("--attempts", type=int, default=1, help="Last attempt number to run (inclusive)")
    p.add_argument("--start-attempt", type=int, default=1)
    p.add_argument("--max-turns", type=int, default=60)
    p.add_argument("--no-subagents", action="store_true")
    args = p.parse_args()

    results: list[PilotResult] = []
    for i in range(args.start_attempt, args.attempts + 1):
        print(f"=== {args.slug} {args.model} attempt {i}/{args.attempts} ===", flush=True)
        t0 = time.time()
        r = run_attempt(
            args.slug,
            args.model,
            i,
            max_turns=args.max_turns,
            use_subagents=not args.no_subagents,
        )
        elapsed = time.time() - t0
        print(
            f"  passed={r.passed} reward={r.reward} turns={r.turns} "
            f"env_failure={r.env_failure} elapsed={elapsed:.0f}s",
            flush=True,
        )
        results.append(r)
        merge_model_runs(args.slug, results)


if __name__ == "__main__":
    main()

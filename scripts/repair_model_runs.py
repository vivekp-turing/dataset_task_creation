#!/usr/bin/env python3
"""Repair attempt-1 rows in model_runs.json from known smoke pilot results."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DELIV = ROOT / "deliverables"

# Smoke pilots (pre-hardening bundles) on 2026-06-30
ATTEMPT1 = {
    "stylelint": {
        "claude-opus-4.6": {"passed": True, "turns": 45, "reward": 1},
        "claude-sonnet-4.6": {"passed": True, "turns": 45, "reward": 1},
    },
    "recharts": {
        "claude-opus-4.6": {"passed": True, "turns": 39, "reward": 1},
        "claude-sonnet-4.6": {"passed": True, "turns": 43, "reward": 1},
    },
}


def repair(slug: str) -> None:
    if slug not in ATTEMPT1:
        return
    path = DELIV / slug / "test-assets" / slug / "runs" / "model_runs.json"
    data = json.loads(path.read_text())
    for model, a1 in ATTEMPT1[slug].items():
        model_key = model.replace(".", "_")
        attempts = data.get("models", {}).get(model, {}).get("attempts", [])
        by_num = {a["attempt"]: a for a in attempts}
        by_num[1] = {
            "attempt": 1,
            "passed": a1["passed"],
            "turns": a1["turns"],
            "env_failure": False,
            "trajectory_path": f"pilot_runs/{slug}/{model_key}/attempt_1.jsonl",
            "reward": a1["reward"],
            "notes": "smoke pilot on pre-hardening bundle",
        }
        entries = [by_num[k] for k in sorted(by_num)]
        passed = sum(1 for e in entries if e["passed"])
        data["models"][model] = {
            "attempts": entries,
            "pass_rate": round(passed / len(entries), 3),
            "mean_turns": round(sum(e["turns"] for e in entries) / len(entries), 1),
        }
    path.write_text(json.dumps(data, indent=2) + "\n")
    print(f"repaired {slug}")


if __name__ == "__main__":
    for s in ATTEMPT1:
        repair(s)

#!/bin/bash
# Alibaba acceptance gate checklist.
#
# Usage: acceptance_check.sh <slug>
#   ROOT=<task-set-dir>

set -uo pipefail

ROOT="${ROOT:-$(pwd)}"
SLUG="${1:?slug required}"
RUNS="$ROOT/deliverables/$SLUG/test-assets/$SLUG/runs/model_runs.json"

[ -f "$RUNS" ] || { echo "MISSING $RUNS"; exit 1; }

python3 << PY
import json, sys
from pathlib import Path

runs = json.loads(Path("$RUNS").read_text())
if runs.get("status") != "COMPLETE":
    print(f"status: {runs.get('status')} — pilot runs not complete")
    sys.exit(1)

models = runs.get("models", {})
required = ["claude-opus-4.6", "claude-sonnet-4.6", "qwen-3.7-max", "glm-5.1"]
failures = []

for m in required:
    if m not in models or not models[m].get("attempts"):
        failures.append(f"Missing attempts for {m}")
        continue
    attempts = models[m]["attempts"]
    if len(attempts) < 5:
        failures.append(f"{m}: only {len(attempts)}/5 attempts")

opus = models.get("claude-opus-4.6", {})
qwen = models.get("qwen-3.7-max", {})
sonnet = models.get("claude-sonnet-4.6", {})

opus_rate = opus.get("pass_rate")
qwen_rate = qwen.get("pass_rate")
sonnet_rate = sonnet.get("pass_rate")
opus_turns = opus.get("mean_turns")

checks = [
    (opus_rate is not None and opus_rate <= 0.60, f"opus pass rate {opus_rate} > 60%"),
    (opus_rate is not None and qwen_rate is not None and (opus_rate - qwen_rate) >= 0.20,
     f"qwen gap {opus_rate - qwen_rate if opus_rate and qwen_rate else 'N/A'} < 20%"),
    (opus_rate is not None and sonnet_rate is not None and (opus_rate - sonnet_rate) >= 0.20,
     f"sonnet gap {opus_rate - sonnet_rate if opus_rate and sonnet_rate else 'N/A'} < 20%"),
    (opus_turns is not None and opus_turns >= 20, f"mean turns {opus_turns} < 20"),
]

for ok, msg in checks:
    if ok:
        print(f"PASS: {msg.split()[0] if 'gap' not in msg else msg}")
    else:
        print(f"FAIL: {msg}")
        failures.append(msg)

if failures:
    print(f"\nRESULT: FAIL ({len(failures)} issue(s))")
    sys.exit(1)
print("\nRESULT: ACCEPTANCE PASS")
PY

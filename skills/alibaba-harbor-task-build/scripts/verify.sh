#!/bin/bash
# Verify Alibaba Harbor bundles.
#
# Usage: verify.sh <slug> [<slug> ...]
#   ROOT=<task-set-dir>  (contains deliverables/, clones/, tasks/)

set -uo pipefail

ROOT="${ROOT:-$(pwd)}"
CLONES="$ROOT/clones"
DELIV="$ROOT/deliverables"

verify_one() {
  local s=$1
  local bundle="$DELIV/$s"
  local assets="$bundle/test-assets/$s"
  local clone="$CLONES/$s"
  local errors=0

  echo "===== $s ====="

  # Required files
  local required=(
    "test/${s}.json"
    "test-assets/${s}/instruction.md"
    "test-assets/${s}/task.toml"
    "test-assets/${s}/environment/Dockerfile"
    "test-assets/${s}/environment/workspace.tar.gz"
    "test-assets/${s}/tests/test.sh"
    "test-assets/${s}/tests/test_outputs.py"
    "test-assets/${s}/solution/solve.sh"
    "test-assets/${s}/rubric.md"
    "test-assets/${s}/metadata/author_self_assessment.json"
    "test-assets/${s}/runs/model_runs.json"
    "test-assets/${s}/scoring/scoring_summary.json"
  )
  for f in "${required[@]}"; do
    if [ ! -f "$bundle/$f" ]; then
      echo "  MISSING $f"
      errors=$((errors + 1))
    fi
  done

  local n
  n=$(find "$bundle" -type f 2>/dev/null | wc -l | tr -d ' ')
  echo "files: $n"

  # Query JSON description matches instruction.md
  if [ -f "$bundle/test/${s}.json" ] && [ -f "$assets/instruction.md" ]; then
    if python3 -c "
import json, sys
from pathlib import Path
j = json.loads(Path('$bundle/test/${s}.json').read_text())
inst = Path('$assets/instruction.md').read_text().strip()
desc = j.get('description', '').strip()
sys.exit(0 if desc == inst else 1)
" 2>/dev/null; then
      echo "query/instruction match: OK"
    else
      echo "query/instruction match: FAIL"
      errors=$((errors + 1))
    fi
  fi

  # Extract embedded patches and verify apply @ base SHA
  local sha
  sha=$(grep -E '^base_commit' "$assets/task.toml" 2>/dev/null | head -1 | sed -E 's/.*"([0-9a-f]+)".*/\1/')
  echo "base_commit: ${sha:0:12}"

  if [ -d "$clone" ] && [ -n "$sha" ]; then
    local wt="$clone"
    local tmpwt=""
    local head
    head=$(git -C "$clone" rev-parse HEAD 2>/dev/null || echo "")
    if [ "$sha" != "$head" ] && git -C "$clone" cat-file -t "$sha" >/dev/null 2>&1; then
      tmpwt="/tmp/wt_verify_$s"
      rm -rf "$tmpwt"
      git -C "$clone" worktree add --detach "$tmpwt" "$sha" >/dev/null 2>&1 && wt="$tmpwt" || echo "  WARN: worktree failed"
    fi

    local gold="/tmp/gold_$s.diff"
    local test="/tmp/test_$s.diff"
    if [ -f "$assets/solution/solve.sh" ]; then
      sed -n "/^cat > .*gold_patch.diff <<'/,\$p" "$assets/solution/solve.sh" | \
        sed '1d;$d' | sed '/^__ALIBABA_GOLD_PATCH__$/d' > "$gold" 2>/dev/null || true
      if [ -s "$gold" ]; then
        git -C "$wt" apply --check "$gold" 2>/dev/null && echo "GOLD ok" || { echo "GOLD FAIL"; errors=$((errors + 1)); }
        grep -E "^\+\+\+ b/.*([Tt]est|spec|__tests__)" "$gold" >/dev/null && echo "WARN: gold may touch tests" || echo "gold=source-only ok"
      fi
    fi
    if [ -f "$assets/tests/test.sh" ]; then
      sed -n "/^cat > .*test_patch.diff <<'/,\$p" "$assets/tests/test.sh" | \
        sed '1d;$d' | sed '/^__ALIBABA_TEST_PATCH__$/d' > "$test" 2>/dev/null || true
      if [ -s "$test" ]; then
        git -C "$wt" apply --check "$test" 2>/dev/null && echo "TEST ok" || { echo "TEST FAIL"; errors=$((errors + 1)); }
      fi
      if [ -s "$gold" ] && [ -s "$test" ]; then
        git -C "$wt" apply --check "$gold" "$test" 2>/dev/null && echo "BOTH ok" || { echo "BOTH FAIL"; errors=$((errors + 1)); }
      fi
    fi

    [ -n "$tmpwt" ] && { git -C "$clone" worktree remove --force "$tmpwt" >/dev/null 2>&1; rm -rf "$tmpwt"; }
    local dirty
    dirty=$(git -C "$clone" status --porcelain 2>/dev/null | wc -l | tr -d ' ')
    echo "clone dirty lines: $dirty"
  else
    echo "SKIP patch apply (no clone or SHA)"
  fi

  # Executable scripts
  for script in "$assets/tests/test.sh" "$assets/solution/solve.sh"; do
    [ -x "$script" ] 2>/dev/null && echo "$(basename "$script"): executable" || echo "$(basename "$script"): NOT executable"
  done

  # Rubric mentions verifier alignment
  if [ -f "$assets/rubric.md" ]; then
    grep -qi "verifier\|automated" "$assets/rubric.md" && echo "rubric/verifier note: present" || echo "rubric/verifier note: missing (add alignment statement)"
  fi

  [ "$errors" -eq 0 ] && echo "RESULT: PASS" || echo "RESULT: FAIL ($errors errors)"
}

for s in "$@"; do verify_one "$s"; done

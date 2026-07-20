#!/bin/bash
# Usage: verify.sh <slug> [<slug> ...]
#   Set ROOT to the task set's initial_task_list dir (containing harbor_tasks/
#   and clones/). Defaults below; override via env: ROOT=/path verify.sh <slug>
#
# Verifies each task's patches apply against the task's OWN base_commit (not the
# clone HEAD, which may differ when a task pins a specific base SHA), checks
# source/test separation, and confirms the clone is left clean.
ROOT="${ROOT:-/path/to/your/task_set/initial_task_list}"

verify(){ s=$1; echo "===== $s ====="
  T="$ROOT/harbor_tasks/$s"; C="$ROOT/clones/$s"
  [ -d "$T" ] || { echo "MISSING TASK FOLDER"; return; }
  n=$(find "$T" -type f | wc -l | tr -d ' '); echo "files: $n"
  for f in instruction.md task.toml environment/Dockerfile environment/problem_statement.md solution/golden.patch solution/solve.sh tests/test.sh; do
    [ -f "$T/$f" ] || echo "  MISSING $f"
  done
  # Extract the test-only patch embedded in tests/test.sh (heredoc markers).
  TP="/tmp/tp_$s.diff"
  awk "flag && /^__TEST_PATCH_EOF__\$/ {exit} flag {print} /<< '__TEST_PATCH_EOF__'/ {flag=1}" \
    "$T/tests/test.sh" > "$TP" 2>/dev/null
  [ -s "$TP" ] || echo "  WARN: no embedded test patch found in tests/test.sh"
  # base_commit from task.toml (fallback to Dockerfile REPO_SHA)
  SHA=$(grep -E '^base_commit' "$T/task.toml" 2>/dev/null | head -1 | sed -E 's/.*"([0-9a-f]+)".*/\1/')
  [ -z "$SHA" ] && SHA=$(grep -E 'REPO_SHA=' "$T/environment/Dockerfile" 2>/dev/null | head -1 | sed -E 's/.*REPO_SHA=([0-9a-f]+).*/\1/')
  echo "base_commit: ${SHA:0:12}"
  HEAD=$(git -C "$C" rev-parse HEAD 2>/dev/null)
  WT="$C"
  TMPWT=""
  if [ -n "$SHA" ] && [ "$SHA" != "$HEAD" ]; then
    if git -C "$C" cat-file -t "$SHA" >/dev/null 2>&1; then
      TMPWT="/tmp/wt_$s"; rm -rf "$TMPWT"
      git -C "$C" worktree add --detach "$TMPWT" "$SHA" >/dev/null 2>&1 && WT="$TMPWT" || echo "  WARN: worktree add failed; using HEAD"
    else
      echo "  WARN: base_commit not in clone; verifying against HEAD"
    fi
  fi
  git -C "$WT" apply --check "$T/solution/golden.patch" 2>/dev/null && echo "GOLD ok" || echo "GOLD FAIL"
  if [ -s "$TP" ]; then
    git -C "$WT" apply --check "$TP" 2>/dev/null && echo "TEST ok" || echo "TEST FAIL"
    git -C "$WT" apply --check "$T/solution/golden.patch" "$TP" 2>/dev/null && echo "BOTH ok" || echo "BOTH FAIL"
  else
    echo "TEST skip (no embedded patch)"; echo "BOTH skip"
  fi
  grep -E "^\+\+\+ b/.*([Tt]est|spec|__tests__)" "$T/solution/golden.patch" >/dev/null && echo "WARN: gold may touch tests" || echo "gold=source-only ok"
  # task.toml must carry the graded F2P node IDs (persisted downstream as
  # RelevantPR.fail_to_pass); count quoted entries in the array, skipping comments,
  # and sanity-check against num_f2p_tests.
  F2P_N=$(awk '/^fail_to_pass *= *\[/{f=1;next} f&&/^[[:space:]]*\]/{f=0} f&&/^[[:space:]]*#/{next} f&&/"/{c++} END{print c+0}' "$T/task.toml" 2>/dev/null)
  NUM_F2P=$(grep -E '^num_f2p_tests' "$T/task.toml" 2>/dev/null | head -1 | sed -E 's/^[^=]*=[[:space:]]*([0-9]+).*/\1/')
  if [ "${F2P_N:-0}" -eq 0 ]; then
    echo "  WARN: task.toml fail_to_pass is empty — emit the graded F2P node IDs"
  elif [ -n "$NUM_F2P" ] && [ "$F2P_N" -ne "$NUM_F2P" ]; then
    echo "  WARN: fail_to_pass count ($F2P_N) != num_f2p_tests ($NUM_F2P)"
  else
    echo "fail_to_pass: $F2P_N ids ok"
  fi
  rm -f "$TP"
  [ -n "$TMPWT" ] && { git -C "$C" worktree remove --force "$TMPWT" >/dev/null 2>&1; rm -rf "$TMPWT"; }
  c=$(git -C "$C" status --porcelain 2>/dev/null | wc -l | tr -d ' '); echo "clone dirty lines: $c"
}
for s in "$@"; do verify "$s"; done

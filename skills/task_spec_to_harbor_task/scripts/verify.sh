#!/bin/bash
# Usage: verify.sh <slug> [<slug> ...]
#   Set ROOT to the task set's initial_task_list dir (containing harbor_tasks/
#   and clones/). Defaults below; override via env: ROOT=/path verify.sh <slug>
#
# Verifies each task's patches apply against the task's OWN base_commit (not the
# clone HEAD, which may differ for pre-fix-parent tasks), checks source/test
# separation, and confirms the clone is left clean.
ROOT="${ROOT:-/path/to/your/task_set/initial_task_list}"

verify(){ s=$1; echo "===== $s ====="
  T="$ROOT/harbor_tasks/$s"; C="$ROOT/clones/$s"
  [ -d "$T" ] || { echo "MISSING TASK FOLDER"; return; }
  n=$(find "$T" -type f | wc -l | tr -d ' '); echo "files: $n"
  for f in instruction.md task.toml environment/Dockerfile solution/gold_patch.diff solution/solve.sh tests/test_patch.diff tests/test.sh; do
    [ -f "$T/$f" ] || echo "  MISSING $f"
  done
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
  git -C "$WT" apply --check "$T/solution/gold_patch.diff" 2>/dev/null && echo "GOLD ok" || echo "GOLD FAIL"
  git -C "$WT" apply --check "$T/tests/test_patch.diff" 2>/dev/null && echo "TEST ok" || echo "TEST FAIL"
  git -C "$WT" apply --check "$T/solution/gold_patch.diff" "$T/tests/test_patch.diff" 2>/dev/null && echo "BOTH ok" || echo "BOTH FAIL"
  grep -E "^\+\+\+ b/.*([Tt]est|spec|__tests__)" "$T/solution/gold_patch.diff" >/dev/null && echo "WARN: gold may touch tests" || echo "gold=source-only ok"
  [ -n "$TMPWT" ] && { git -C "$C" worktree remove --force "$TMPWT" >/dev/null 2>&1; rm -rf "$TMPWT"; }
  c=$(git -C "$C" status --porcelain 2>/dev/null | wc -l | tr -d ' '); echo "clone dirty lines: $c"
}
for s in "$@"; do verify "$s"; done

#!/bin/bash
# Pack a pinned clone into workspace.tar.gz for Alibaba Harbor bundles.
#
# Usage: pack_workspace.sh <slug> [<slug> ...]
#   ROOT=<task-set-dir>  (contains clones/ and deliverables/)
#
# Exports clones/<slug> at the base_commit from task_spec.md or task.toml.
# Writes deliverables/<slug>/test-assets/<slug>/environment/workspace.tar.gz

set -euo pipefail

ROOT="${ROOT:-$(pwd)}"
CLONES="$ROOT/clones"
DELIV="$ROOT/deliverables"

pack_one() {
  local s=$1
  local clone="$CLONES/$s"
  local spec="$ROOT/tasks/$s/task_spec.md"
  local toml="$DELIV/$s/test-assets/$s/task.toml"
  local outdir="$DELIV/$s/test-assets/$s/environment"
  local outfile="$outdir/workspace.tar.gz"

  [ -d "$clone" ] || { echo "MISSING clone: $clone"; return 1; }
  mkdir -p "$outdir"

  # Resolve base SHA
  local sha=""
  if [ -f "$toml" ]; then
    sha=$(grep -E '^base_commit' "$toml" 2>/dev/null | head -1 | sed -E 's/.*"([0-9a-f]+)".*/\1/')
  fi
  if [ -z "$sha" ] && [ -f "$spec" ]; then
    sha=$(grep -Ei 'SHA|commit' "$spec" 2>/dev/null | grep -Eo '[0-9a-f]{40}' | head -1)
  fi
  if [ -z "$sha" ]; then
    sha=$(git -C "$clone" rev-parse HEAD 2>/dev/null)
  fi
  echo "===== pack $s @ ${sha:0:12} ====="

  local tmpwt
  tmpwt=$(mktemp -d)
  trap 'rm -rf "$tmpwt"' RETURN

  if git -C "$clone" cat-file -t "$sha" >/dev/null 2>&1; then
    git -C "$clone" archive "$sha" | tar -x -C "$tmpwt"
  else
    echo "WARN: SHA not in clone; archiving working tree"
    tar -C "$clone" -cf - . | tar -x -C "$tmpwt"
  fi

  # Remove .git from tarball (clean workspace snapshot)
  rm -rf "$tmpwt/.git"

  tar -czf "$outfile" -C "$tmpwt" .
  echo "Wrote $outfile ($(du -h "$outfile" | cut -f1))"
}

for s in "$@"; do pack_one "$s"; done

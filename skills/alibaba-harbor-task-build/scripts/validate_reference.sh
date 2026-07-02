#!/bin/bash
# Compare a deliverable bundle structure against harbor_case + sample10 references.
#
# Usage: validate_reference.sh [<slug>]
# Default slug: rou3-repeated-regex-modifier-constraints

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
SLUG="${1:-rou3-repeated-regex-modifier-constraints}"
BUNDLE="$ROOT/deliverables/$SLUG"

echo "=== Structure validation: $SLUG ==="

# harbor_case core files (under test-assets/<id>/)
harbor_core=(
  instruction.md
  task.toml
  environment/Dockerfile
  environment/workspace.tar.gz
  tests/test.sh
  tests/test_outputs.py
)

# Alibaba extensions (from sample10)
alibaba_ext=(
  solution/solve.sh
  rubric.md
  metadata/author_self_assessment.json
  runs/model_runs.json
  scoring/scoring_summary.json
)

# Harbor query layer
harbor_query="test/${SLUG}.json"

missing=0
for f in "${harbor_core[@]}" "${alibaba_ext[@]}"; do
  path="$BUNDLE/test-assets/$SLUG/$f"
  if [ -f "$path" ]; then
    echo "  OK  test-assets/$SLUG/$f"
  else
    echo "  MISS test-assets/$SLUG/$f"
    missing=$((missing + 1))
  fi
done

if [ -f "$BUNDLE/$harbor_query" ]; then
  echo "  OK  $harbor_query"
else
  echo "  MISS $harbor_query"
  missing=$((missing + 1))
fi

# Compare against docs/alibaba/harbor_case (core only)
echo ""
echo "=== harbor_case reference (core verifier pattern) ==="
ref="$ROOT/docs/alibaba/harbor_case/00044c57e6253cc6_q0"
for f in instruction.md task.toml environment/Dockerfile tests/test.sh tests/test_outputs.py; do
  [ -f "$ref/$f" ] && echo "  ref has $f"
done
[ -f "$ROOT/docs/alibaba/harbor_case/00044c57e6253cc6_q0.json" ] && echo "  ref has test/<id>.json pattern"

echo ""
echo "=== sample10 reference (Alibaba extensions) ==="
sample="$ROOT/docs/alibaba/sample_task/$SLUG"
for f in rubric.md solution/solve.sh runs/model_runs.json; do
  [ -f "$sample/$f" ] && echo "  sample has $f"
done

echo ""
if [ "$missing" -eq 0 ]; then
  echo "RESULT: bundle matches harbor_case + sample10 layout"
  exit 0
else
  echo "RESULT: $missing missing file(s)"
  exit 1
fi

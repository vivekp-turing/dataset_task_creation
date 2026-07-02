#!/bin/bash
# Rubric / exec verifier alignment check.
#
# Usage: check_rubric_alignment.sh <slug>
#   ROOT=<task-set-dir>

set -uo pipefail

ROOT="${ROOT:-$(pwd)}"
SLUG="${1:?slug required}"
ASSETS="$ROOT/deliverables/$SLUG/test-assets/$SLUG"

[ -f "$ASSETS/rubric.md" ] || { echo "MISSING rubric.md"; exit 1; }
[ -f "$ASSETS/tests/test.sh" ] || { echo "MISSING tests/test.sh"; exit 1; }

errors=0

# Must state verifier alignment
if grep -qi "automated verifier\|exec.*verifier\|same correctness target" "$ASSETS/rubric.md"; then
  echo "alignment statement: OK"
else
  echo "alignment statement: MISSING (add note that verifier and rubric share correctness target)"
  errors=$((errors + 1))
fi

# Correctness section present
if grep -qi "^## Correctness" "$ASSETS/rubric.md"; then
  echo "correctness section: OK"
else
  echo "correctness section: MISSING"
  errors=$((errors + 1))
fi

# Embedded test patch present in test.sh
if grep -q "__ALIBABA_TEST_PATCH__" "$ASSETS/tests/test.sh"; then
  echo "embedded test patch: OK"
else
  echo "embedded test patch: MISSING or different pattern"
  errors=$((errors + 1))
fi

# Task-specific scoring points
if grep -qi "^### Correctness" "$ASSETS/rubric.md"; then
  echo "task-specific correctness: OK"
else
  echo "task-specific correctness: MISSING"
  errors=$((errors + 1))
fi

# scoring summary flag
summary="$ASSETS/scoring/scoring_summary.json"
if [ -f "$summary" ]; then
  if python3 -c "import json; d=json.load(open('$summary')); exit(0 if d.get('rubric_test_alignment') else 1)" 2>/dev/null; then
    echo "scoring rubric_test_alignment: true"
  else
    echo "scoring rubric_test_alignment: not true (set after manual review)"
  fi
fi

[ "$errors" -eq 0 ] && { echo "RESULT: PASS"; exit 0; } || { echo "RESULT: FAIL ($errors)"; exit 1; }

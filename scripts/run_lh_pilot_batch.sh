#!/bin/bash
# Run Anthropic pilots on the five long-horizon tasks.
# Requires ANTHROPIC_API_KEY in env or .env.pilot at repo root.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ -f "$ROOT/.env.pilot" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env.pilot"
  set +a
fi

if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo "ERROR: set ANTHROPIC_API_KEY or create $ROOT/.env.pilot"
  exit 1
fi

SLUGS=(albumentations stylelint recharts vercel-ai darts)
MODELS=(claude-opus-4.6 claude-sonnet-4.6)
ATTEMPTS="${ATTEMPTS:-2}"
MAX_TURNS="${MAX_TURNS:-45}"

echo "Batch pilots: attempts=$ATTEMPTS max_turns=$MAX_TURNS"

for slug in "${SLUGS[@]}"; do
  for model in "${MODELS[@]}"; do
    python3 "$ROOT/scripts/run_anthropic_pilot.py" "$slug" \
      --model "$model" \
      --attempts "$ATTEMPTS" \
      --max-turns "$MAX_TURNS" \
      || echo "WARN: pilot failed for $slug $model"
  done
done

echo "Done. Results in deliverables/*/test-assets/*/runs/model_runs.json and pilot_runs/"

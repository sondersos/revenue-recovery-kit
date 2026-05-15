#!/usr/bin/env bash
# demo.sh — end-to-end pipeline demonstration
# Usage: bash scripts/demo.sh [API_BASE]
# Requires: curl, jq
set -euo pipefail

API="${1:-http://localhost:8000}"

echo "=== revenue-recovery-kit demo ==="
echo "API: $API"
echo ""

# 1. Health check
echo "--- 1. Health ---"
curl -sf "$API/health" | jq .
echo ""

# 2. Trigger a detection run
echo "--- 2. Run detection ---"
DETECTION=$(curl -sf -X POST "$API/v1/detection/run" \
  -H "Content-Type: application/json" \
  -d '{"window_days": 30}')
echo "$DETECTION" | jq .
RUN_ID=$(echo "$DETECTION" | jq -r '.detection_run_id')
echo "Detection run id: $RUN_ID"
echo ""

# 3. Fetch the run detail
echo "--- 3. Detection run detail ---"
curl -sf "$API/v1/detection/runs/$RUN_ID" | jq .
echo ""

# 4. Generate Claude insight (requires ANTHROPIC_API_KEY to be set)
if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo "--- 4. Claude insight --- SKIPPED (ANTHROPIC_API_KEY not set)"
else
  echo "--- 4. Generate Claude insight ---"
  curl -sf -X POST "$API/v1/insights" \
    -H "Content-Type: application/json" \
    -d "{\"detection_run_id\": \"$RUN_ID\"}" | jq .
fi

echo ""
echo "=== Demo complete ==="

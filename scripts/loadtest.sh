#!/usr/bin/env bash
# loadtest.sh — Apache Bench smoke test for hot-path endpoints
# Usage: bash scripts/loadtest.sh [API_BASE]
# Requires: ab (apache2-utils / httpd-tools), jq, python3 + PyJWT
set -euo pipefail

API="${1:-http://localhost:8000}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v ab &>/dev/null; then
  echo "ERROR: 'ab' not found. Install with: brew install httpd  OR  apt install apache2-utils"
  exit 1
fi

# Resolve bearer token
if [ -n "${DEMO_JWT_TOKEN:-}" ]; then
  TOKEN="$DEMO_JWT_TOKEN"
else
  TOKEN=$(python3 "$SCRIPT_DIR/gen_demo_token.py")
fi

echo "=== revenue-recovery-kit load test ==="
echo "API: $API"
echo ""

run_ab() {
  local name="$1" path="$2" requests="${3:-1000}" concurrency="${4:-20}"
  echo "--- $name ---"
  ab -n "$requests" -c "$concurrency" \
     -H "Authorization: Bearer $TOKEN" \
     "$API$path" 2>&1 \
  | grep -E "Requests per second|50%|95%|99%|Time per request.*mean\)"
  echo ""
}

run_ab "GET /v1/detection/runs/latest" "/v1/detection/runs/latest"
run_ab "GET /v1/insights/latest"       "/v1/insights/latest"
run_ab "GET /v1/insights/cost-summary" "/v1/insights/cost-summary"

echo "=== Load test complete. Record p50/p95/p99 in docs/PERFORMANCE.md ==="

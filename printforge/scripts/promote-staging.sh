#!/bin/bash
###############################################################################
# promote-staging.sh — ask production to atomically activate the verified
# staging build and retain the prior release for rollback.
#
# Use when you've verified a feature on staging (:8001) and want to "apply it
# to the real PrintForge." This replaces the usual `deploy-pi` round trip —
# no rebuild, no re-SCP, just an rsync on the Pi + restart.
#
# The production API owns the operation and checks its real controller. Active
# prints and unverifiable controller state are always rejected; there is no
# force bypass.
#
# Usage (from your laptop):
#   PRINTFORGE_PROMOTION_TOKEN=... bash printforge/scripts/promote-staging.sh
#   PRINTFORGE_PROMOTION_TOKEN=... bash printforge/scripts/promote-staging.sh --rollback
# Add PRINTFORGE_API_KEY when ordinary production API authentication is enabled.
###############################################################################

set -euo pipefail

PI_HOST="${PRINTFORGE_PI_HOST:-100.108.194.105}"
API_KEY="${PRINTFORGE_API_KEY:-}"
PROMOTION_TOKEN="${PRINTFORGE_PROMOTION_TOKEN:-}"
ACTION="${1:-}"

if [ -z "$PROMOTION_TOKEN" ]; then
    echo "✗ PRINTFORGE_PROMOTION_TOKEN is required. Promotion is fail-closed."
    exit 1
fi

case "$ACTION" in
    "") ENDPOINT="promote"; LABEL="promote staging → production"; EXPECTED_STATUS="promoted" ;;
    "--rollback") ENDPOINT="promote/rollback"; LABEL="rollback production release"; EXPECTED_STATUS="rolled_back" ;;
    *) echo "Usage: $0 [--rollback]"; exit 2 ;;
esac

echo "── $LABEL on $PI_HOST ──"

CURL_ARGS=(
    -sS --connect-timeout 5 --max-time 45 -X POST -w $'\n%{http_code}'
    -H "X-PrintForge-Promotion-Token: $PROMOTION_TOKEN"
    "http://$PI_HOST:8000/api/system/$ENDPOINT"
)
if [ -n "$API_KEY" ]; then
    CURL_ARGS+=(-H "Authorization: Bearer $API_KEY")
fi

if ! RESPONSE=$(curl "${CURL_ARGS[@]}"); then
    echo "✗ production was unreachable or timed out; no success was assumed"
    exit 1
fi
HTTP_CODE=$(printf '%s\n' "$RESPONSE" | tail -n 1)
BODY=$(printf '%s\n' "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    if ! PRINTFORGE_RESPONSE_BODY="$BODY" PRINTFORGE_EXPECTED_STATUS="$EXPECTED_STATUS" \
        python3 -c 'import json, os, sys; body=json.loads(os.environ["PRINTFORGE_RESPONSE_BODY"]); sys.exit(0 if isinstance(body, dict) and body.get("status") == os.environ["PRINTFORGE_EXPECTED_STATUS"] else 1)' 2>/dev/null
    then
        echo "✗ production returned a malformed or unexpected success response"
        echo "$BODY"
        exit 1
    fi
    echo "$BODY"
    echo "✓ production accepted the operation and scheduled its restart"
else
    echo "✗ operation refused (HTTP $HTTP_CODE)"
    echo "$BODY"
    if [ "$HTTP_CODE" = "401" ]; then
        echo "  Set PRINTFORGE_API_KEY to the production API key and retry."
    elif [ "$HTTP_CODE" = "403" ]; then
        echo "  Check PRINTFORGE_PROMOTION_TOKEN and retry."
    fi
    exit 1
fi

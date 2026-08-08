#!/bin/bash
###############################################################################
# promote-staging.sh — copy whatever's in /opt/printforge-staging/ onto
# production (/opt/printforge/) and restart the production service.
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
#   bash printforge/scripts/promote-staging.sh
#   PRINTFORGE_API_KEY=pf_... bash printforge/scripts/promote-staging.sh
###############################################################################

set -e

PI_HOST="${PRINTFORGE_PI_HOST:-100.108.194.105}"
API_KEY="${PRINTFORGE_API_KEY:-}"

echo "── promote staging → production on $PI_HOST ──"

CURL_ARGS=(-sS --max-time 30 -X POST -w $'\n%{http_code}' "http://$PI_HOST:8000/api/system/promote")
if [ -n "$API_KEY" ]; then
    CURL_ARGS+=(-H "Authorization: Bearer $API_KEY")
fi

RESPONSE=$(curl "${CURL_ARGS[@]}" || true)
HTTP_CODE=$(printf '%s\n' "$RESPONSE" | tail -n 1)
BODY=$(printf '%s\n' "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    echo "$BODY"
    echo "✓ production accepted the promotion and scheduled its restart"
else
    echo "✗ promotion refused (HTTP $HTTP_CODE)"
    echo "$BODY"
    if [ "$HTTP_CODE" = "401" ]; then
        echo "  Set PRINTFORGE_API_KEY to the production API key and retry."
    fi
    exit 1
fi

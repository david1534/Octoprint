#!/bin/bash
###############################################################################
# promote-staging.sh — copy whatever's in /opt/printforge-staging/ onto
# production (/opt/printforge/) and restart the production service.
#
# Use when you've verified a feature on staging (:8001) and want to "apply it
# to the real PrintForge." This replaces the usual `deploy-pi` round trip —
# no rebuild, no re-SCP, just an rsync on the Pi + restart.
#
# WARNING: If a print is in progress, production will be interrupted by the
# restart. The script will refuse to proceed in that case unless you pass
# --force.
#
# Usage (from your laptop):
#   bash printforge/scripts/promote-staging.sh           # safe: refuses if printing
#   bash printforge/scripts/promote-staging.sh --force   # restart even if printing
###############################################################################

set -e

PI_USER="${PRINTFORGE_PI_USER:-david1534}"
PI_HOST="${PRINTFORGE_PI_HOST:-100.108.194.105}"
TARGET="$PI_USER@$PI_HOST"
FORCE="${1:-}"

echo "── promote staging → production on $TARGET ──"

# Pi reachable?
if ! ssh -o ConnectTimeout=5 "$TARGET" "echo OK" > /dev/null 2>&1; then
    echo "✗ Pi unreachable. Check 'tailscale status'."
    exit 1
fi

# Print-in-progress guard
STATUS_JSON=$(curl -s --max-time 5 "http://$PI_HOST:8000/api/printer/status" || echo '{}')
if echo "$STATUS_JSON" | grep -q '"status"[[:space:]]*:[[:space:]]*"printing"'; then
    if [ "$FORCE" != "--force" ]; then
        echo "✗ A print is in progress on production. Aborting."
        echo "  Wait for it to finish, or re-run with --force to proceed anyway."
        exit 1
    fi
    echo "! print in progress — proceeding because --force was passed"
fi

# Sync staging → production code. Keep production's venv, data, config untouched.
echo "→ rsync /opt/printforge-staging/app → /opt/printforge/app"
ssh "$TARGET" "rsync -a --delete /opt/printforge-staging/app/ /opt/printforge/app/"

if ssh "$TARGET" "[ -d /opt/printforge-staging/frontend/build ]"; then
    echo "→ rsync /opt/printforge-staging/frontend/build → /opt/printforge/frontend/build"
    ssh "$TARGET" "mkdir -p /opt/printforge/frontend && rsync -a --delete /opt/printforge-staging/frontend/build/ /opt/printforge/frontend/build/"
fi

echo "→ restarting printforge (production)"
ssh "$TARGET" "sudo systemctl restart printforge"
sleep 3

STATUS=$(ssh "$TARGET" "sudo systemctl is-active printforge" || true)
if [ "$STATUS" = "active" ]; then
    echo "✓ production is live at http://$PI_HOST:8000"
else
    echo "✗ production is $STATUS after restart. Recent logs:"
    ssh "$TARGET" "journalctl -u printforge -n 40 --no-pager"
    exit 1
fi

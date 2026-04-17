#!/bin/bash
###############################################################################
# deploy-staging.sh — push WIP code to the Pi's staging instance (port 8001).
#
# Safe to run during an active print — the staging instance is in mock-serial
# mode and never touches the real printer or production's data.
#
# Usage (from your laptop, repo root):
#   bash printforge/scripts/deploy-staging.sh              # backend + frontend
#   bash printforge/scripts/deploy-staging.sh backend       # backend only
#   bash printforge/scripts/deploy-staging.sh frontend      # frontend only
###############################################################################

set -e

PI_USER="${PRINTFORGE_PI_USER:-david1534}"
PI_HOST="${PRINTFORGE_PI_HOST:-100.108.194.105}"
TARGET="$PI_USER@$PI_HOST"
REMOTE_DIR="/opt/printforge-staging"
MODE="${1:-full}"

cd "$(dirname "$0")/../.."   # repo root

echo "── staging deploy → $TARGET:$REMOTE_DIR  (mode: $MODE) ──"

# Pre-flight: Pi reachable?
if ! ssh -o ConnectTimeout=5 "$TARGET" "echo OK" > /dev/null 2>&1; then
    echo "✗ Pi unreachable via Tailscale. Check 'tailscale status'."
    exit 1
fi

# Backend
if [ "$MODE" = "full" ] || [ "$MODE" = "backend" ]; then
    echo "→ syncing backend"
    scp -rq printforge/backend/app "$TARGET:$REMOTE_DIR/"
    ssh "$TARGET" "chmod -R u+w $REMOTE_DIR/app"
fi

# Frontend — build locally, ship the build output
if [ "$MODE" = "full" ] || [ "$MODE" = "frontend" ]; then
    echo "→ building frontend locally"
    (cd printforge/frontend && npm run build > /dev/null) || {
        echo "✗ frontend build failed — aborting deploy"
        exit 1
    }
    echo "→ syncing frontend build"
    ssh "$TARGET" "mkdir -p $REMOTE_DIR/frontend"
    scp -rq printforge/frontend/build "$TARGET:$REMOTE_DIR/frontend/"
    ssh "$TARGET" "chmod -R u+w $REMOTE_DIR/frontend/build"
fi

echo "→ restarting printforge-staging"
ssh "$TARGET" "sudo systemctl restart printforge-staging"
sleep 3

STATUS=$(ssh "$TARGET" "sudo systemctl is-active printforge-staging" || true)
if [ "$STATUS" = "active" ]; then
    echo "✓ staging live at http://$PI_HOST:8001"
    echo "  logs: ssh $TARGET 'journalctl -u printforge-staging -n 30 --no-pager'"
else
    echo "✗ staging service is $STATUS. Recent logs:"
    ssh "$TARGET" "journalctl -u printforge-staging -n 30 --no-pager"
    exit 1
fi

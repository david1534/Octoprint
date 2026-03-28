#!/bin/bash
###############################################################################
# PrintForge Auto-Update
# Run on the Pi to pull latest changes from GitHub and deploy them.
#
# Usage:
#   ssh david1534@100.108.194.105 "bash ~/Octoprint/printforge/scripts/update.sh"
#
# Or as a one-liner from your laptop:
#   ssh david1534@100.108.194.105 "cd ~/Octoprint && git pull && bash printforge/scripts/update.sh"
###############################################################################

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

REPO_DIR="$HOME/Octoprint"
INSTALL_DIR="/opt/printforge"
FRONTEND_SRC="$INSTALL_DIR/frontend-src"

if [ ! -d "$REPO_DIR/.git" ]; then
    echo -e "${RED}Error:${NC} $REPO_DIR is not a git repo."
    echo "Clone it first: git clone https://github.com/david1534/Octoprint.git ~/Octoprint"
    exit 1
fi

cd "$REPO_DIR"

echo -e "${BOLD}PrintForge Update${NC}"
echo "────────────────────────"

# ── Pull latest changes ─────────────────────────────────────────
echo -e "${YELLOW}[1/4]${NC} Fetching latest from GitHub..."
git fetch origin main

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
    echo -e "${GREEN}✓${NC} Already up to date (${LOCAL:0:7})"
    exit 0
fi

# Show what's new
echo ""
echo -e "${BOLD}New commits:${NC}"
git log --oneline HEAD..origin/main
echo ""

# Get list of changed files
CHANGED=$(git diff --name-only HEAD..origin/main)

# Pull the changes
git pull origin main --ff-only
echo -e "${GREEN}✓${NC} Updated to $(git rev-parse --short HEAD)"

# ── Detect what needs updating ──────────────────────────────────
BACKEND_CHANGED=false
FRONTEND_CHANGED=false

if echo "$CHANGED" | grep -q "^printforge/backend/"; then
    BACKEND_CHANGED=true
fi

if echo "$CHANGED" | grep -q "^printforge/frontend/"; then
    FRONTEND_CHANGED=true
fi

echo ""
echo -e "${BOLD}Changes detected:${NC}"
echo -e "  Backend:  $([ "$BACKEND_CHANGED" = true ] && echo -e "${YELLOW}changed${NC}" || echo -e "${GREEN}no changes${NC}")"
echo -e "  Frontend: $([ "$FRONTEND_CHANGED" = true ] && echo -e "${YELLOW}changed${NC}" || echo -e "${GREEN}no changes${NC}")"
echo ""

# ── Deploy backend ──────────────────────────────────────────────
if [ "$BACKEND_CHANGED" = true ]; then
    echo -e "${YELLOW}[2/4]${NC} Deploying backend..."
    cp -r "$REPO_DIR/printforge/backend/app/" "$INSTALL_DIR/app/"
    chmod -R u+w "$INSTALL_DIR/app/"

    # Install any new Python dependencies
    if echo "$CHANGED" | grep -q "requirements.txt"; then
        echo "  Installing updated dependencies..."
        "$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt" -q
    fi

    echo -e "${GREEN}✓${NC} Backend deployed"
else
    echo -e "${GREEN}[2/4]${NC} Backend unchanged, skipping"
fi

# ── Deploy frontend ─────────────────────────────────────────────
if [ "$FRONTEND_CHANGED" = true ]; then
    echo -e "${YELLOW}[3/4]${NC} Rebuilding frontend (this may take a few minutes)..."
    mkdir -p "$FRONTEND_SRC"
    cp -r "$REPO_DIR/printforge/frontend/src" "$FRONTEND_SRC/src"
    cp "$REPO_DIR/printforge/frontend/package.json" "$FRONTEND_SRC/"
    cp "$REPO_DIR/printforge/frontend/svelte.config.js" "$FRONTEND_SRC/" 2>/dev/null || true
    cp "$REPO_DIR/printforge/frontend/vite.config.ts" "$FRONTEND_SRC/" 2>/dev/null || true
    cp "$REPO_DIR/printforge/frontend/tsconfig.json" "$FRONTEND_SRC/" 2>/dev/null || true
    cp "$REPO_DIR/printforge/frontend/tailwind.config.js" "$FRONTEND_SRC/" 2>/dev/null || true
    cp "$REPO_DIR/printforge/frontend/postcss.config.js" "$FRONTEND_SRC/" 2>/dev/null || true

    cd "$FRONTEND_SRC"
    npm install --silent 2>&1 | tail -3
    npm run build 2>&1 | tail -3

    mkdir -p "$INSTALL_DIR/frontend"
    rm -rf "$INSTALL_DIR/frontend/build"
    cp -r build/ "$INSTALL_DIR/frontend/build/"
    cd "$REPO_DIR"

    echo -e "${GREEN}✓${NC} Frontend rebuilt and deployed"
else
    echo -e "${GREEN}[3/4]${NC} Frontend unchanged, skipping"
fi

# ── Restart services ────────────────────────────────────────────
if [ "$BACKEND_CHANGED" = true ] || [ "$FRONTEND_CHANGED" = true ]; then
    echo -e "${YELLOW}[4/4]${NC} Restarting services..."
    sudo systemctl restart printforge
    sleep 2

    # Health check
    if curl -sf --max-time 10 "http://localhost:8000/api/system/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} Health check passed"
    else
        echo -e "${RED}⚠${NC}  Health check failed — check logs:"
        echo "  sudo journalctl -u printforge -n 20 --no-pager"
    fi
else
    echo -e "${GREEN}[4/4]${NC} No restart needed"
fi

echo ""
echo -e "${GREEN}${BOLD}Update complete!${NC}"
echo -e "  Version: $(git rev-parse --short HEAD)"
echo -e "  Open: ${BOLD}http://$(hostname -I | awk '{print $1}'):8000${NC}"
echo ""

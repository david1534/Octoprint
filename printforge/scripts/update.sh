#!/usr/bin/env bash
###############################################################################
# PrintForge Auto-Update
# Run on the Pi to pull latest changes from GitHub and deploy them.
#
# Usage (on the Pi):
#   bash ~/Octoprint/printforge/scripts/update.sh
#
# Usage (from your laptop):
#   ssh david1534@100.108.194.105 "bash ~/Octoprint/printforge/scripts/update.sh"
###############################################################################

# Auto-fix Windows line endings (CRLF -> LF) so the script works
# even if Git on Windows converted the line endings.
if grep -qP '\r' "$0" 2>/dev/null; then
    sed -i 's/\r$//' "$0"
    exec bash "$0" "$@"
fi

set -e

REPO_DIR="$HOME/Octoprint"
INSTALL_DIR="/opt/printforge"
FRONTEND_SRC="$INSTALL_DIR/frontend-src"

info()  { printf "  %s\n" "$1"; }
ok()    { printf "  [OK] %s\n" "$1"; }
warn()  { printf "  [!!] %s\n" "$1"; }
step()  { printf "\n[%s/4] %s\n" "$1" "$2"; }

# ── Sanity check ────────────────────────────────────────────────
if [ ! -d "$REPO_DIR/.git" ]; then
    printf "Error: %s is not a git repo.\n" "$REPO_DIR"
    printf "Clone it first:\n  git clone https://github.com/david1534/Octoprint.git ~/Octoprint\n"
    exit 1
fi

cd "$REPO_DIR"

printf "\nPrintForge Update\n"
printf "========================\n"

# ── 1. Pull latest changes ──────────────────────────────────────
step 1 "Fetching latest from GitHub..."
git fetch origin main

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
    ok "Already up to date ($(echo "$LOCAL" | cut -c1-7))"
    exit 0
fi

printf "\nNew commits:\n"
git log --oneline HEAD..origin/main
printf "\n"

# Get list of changed files before pulling
CHANGED=$(git diff --name-only HEAD..origin/main)

# Pull
git pull origin main --ff-only
ok "Updated to $(git rev-parse --short HEAD)"

# ── Detect what needs updating ──────────────────────────────────
BACKEND_CHANGED=false
FRONTEND_CHANGED=false

if echo "$CHANGED" | grep -q "^printforge/backend/"; then
    BACKEND_CHANGED=true
fi

if echo "$CHANGED" | grep -q "^printforge/frontend/"; then
    FRONTEND_CHANGED=true
fi

printf "\nChanges detected:\n"
if [ "$BACKEND_CHANGED" = true ]; then
    info "Backend:  CHANGED"
else
    info "Backend:  no changes"
fi
if [ "$FRONTEND_CHANGED" = true ]; then
    info "Frontend: CHANGED"
else
    info "Frontend: no changes"
fi

# ── 2. Deploy backend ───────────────────────────────────────────
if [ "$BACKEND_CHANGED" = true ]; then
    step 2 "Deploying backend..."
    cp -r "$REPO_DIR/printforge/backend/app/" "$INSTALL_DIR/app/"
    chmod -R u+w "$INSTALL_DIR/app/"

    # Install any new Python dependencies
    if echo "$CHANGED" | grep -q "requirements.txt"; then
        info "Installing updated dependencies..."
        "$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt" -q
    fi

    ok "Backend deployed"
else
    step 2 "Backend unchanged, skipping"
fi

# ── 3. Deploy frontend ──────────────────────────────────────────
if [ "$FRONTEND_CHANGED" = true ]; then
    step 3 "Rebuilding frontend (this may take a few minutes)..."
    mkdir -p "$FRONTEND_SRC"
    cp -r "$REPO_DIR/printforge/frontend/src" "$FRONTEND_SRC/src"
    for f in package.json svelte.config.js vite.config.ts tsconfig.json tailwind.config.js postcss.config.js; do
        cp "$REPO_DIR/printforge/frontend/$f" "$FRONTEND_SRC/" 2>/dev/null || true
    done

    cd "$FRONTEND_SRC"
    npm install --silent 2>&1 | tail -3
    npm run build 2>&1 | tail -3

    mkdir -p "$INSTALL_DIR/frontend"
    rm -rf "$INSTALL_DIR/frontend/build"
    cp -r build/ "$INSTALL_DIR/frontend/build/"
    cd "$REPO_DIR"

    ok "Frontend rebuilt and deployed"
else
    step 3 "Frontend unchanged, skipping"
fi

# ── 4. Restart services ─────────────────────────────────────────
if [ "$BACKEND_CHANGED" = true ] || [ "$FRONTEND_CHANGED" = true ]; then
    step 4 "Restarting services..."
    sudo systemctl restart printforge
    sleep 2

    if curl -sf --max-time 10 "http://localhost:8000/api/system/health" > /dev/null 2>&1; then
        ok "Health check passed"
    else
        warn "Health check failed -- check logs:"
        info "sudo journalctl -u printforge -n 20 --no-pager"
    fi
else
    step 4 "No restart needed"
fi

printf "\nUpdate complete!\n"
printf "  Version: %s\n" "$(git rev-parse --short HEAD)"
PI_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
printf "  Open: http://%s:8000\n\n" "${PI_IP:-<pi-ip>}"

#!/bin/bash
###############################################################################
# PrintForge Quick Deploy
# Updates backend + frontend on the Pi via Tailscale SSH
#
# Usage:
#   bash scripts/deploy.sh
###############################################################################

set -e

PI_HOST="100.108.194.105"
PI_USER="david1534"
INSTALL_DIR="/opt/printforge"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${BOLD}PrintForge Deploy${NC}"
echo "────────────────────────"

# 1. Copy backend files
echo -e "${YELLOW}[1/4]${NC} Uploading backend..."
scp -r "$PROJECT_DIR/backend/app/" "${PI_USER}@${PI_HOST}:${INSTALL_DIR}/app/"
echo -e "${GREEN}✓${NC} Backend uploaded"

# 2. Fix permissions (OneDrive SCP strips write permissions)
echo -e "${YELLOW}[2/4]${NC} Fixing permissions..."
ssh "${PI_USER}@${PI_HOST}" "chmod -R u+w ${INSTALL_DIR}/app/"
echo -e "${GREEN}✓${NC} Permissions fixed"

# 3. Copy frontend source and rebuild on Pi
echo -e "${YELLOW}[3/4]${NC} Uploading frontend source..."
scp -r "$PROJECT_DIR/frontend/src/" "${PI_USER}@${PI_HOST}:/tmp/printforge-frontend-src/"
scp "$PROJECT_DIR/frontend/package.json" "${PI_USER}@${PI_HOST}:/tmp/printforge-frontend-src/"
scp "$PROJECT_DIR/frontend/svelte.config.js" "${PI_USER}@${PI_HOST}:/tmp/printforge-frontend-src/" 2>/dev/null || true
scp "$PROJECT_DIR/frontend/vite.config.ts" "${PI_USER}@${PI_HOST}:/tmp/printforge-frontend-src/" 2>/dev/null || true
scp "$PROJECT_DIR/frontend/tsconfig.json" "${PI_USER}@${PI_HOST}:/tmp/printforge-frontend-src/" 2>/dev/null || true
scp "$PROJECT_DIR/frontend/tailwind.config.js" "${PI_USER}@${PI_HOST}:/tmp/printforge-frontend-src/" 2>/dev/null || true
scp "$PROJECT_DIR/frontend/postcss.config.js" "${PI_USER}@${PI_HOST}:/tmp/printforge-frontend-src/" 2>/dev/null || true
scp "$PROJECT_DIR/frontend/app.html" "${PI_USER}@${PI_HOST}:/tmp/printforge-frontend-src/" 2>/dev/null || true

echo "  Building frontend on Pi (this may take a few minutes)..."
ssh "${PI_USER}@${PI_HOST}" bash -s << 'REMOTE'
    set -e
    cd /tmp/printforge-frontend-src
    # Copy src files to the actual frontend dir for build
    FRONTEND_DIR="/opt/printforge/frontend-src"
    mkdir -p "$FRONTEND_DIR"
    cp -r /tmp/printforge-frontend-src/* "$FRONTEND_DIR/"
    cd "$FRONTEND_DIR"
    npm install --silent 2>&1 | tail -3
    npm run build 2>&1 | tail -3
    # Deploy the build
    mkdir -p /opt/printforge/frontend
    rm -rf /opt/printforge/frontend/build
    cp -r build/ /opt/printforge/frontend/build/
    # Clean up
    rm -rf /tmp/printforge-frontend-src
    echo "Frontend built and deployed"
REMOTE
echo -e "${GREEN}✓${NC} Frontend built and deployed"

# 4. Restart service
echo -e "${YELLOW}[4/4]${NC} Restarting PrintForge service..."
ssh "${PI_USER}@${PI_HOST}" "sudo systemctl restart printforge"
echo -e "${GREEN}✓${NC} Service restarted"

echo ""
echo -e "${GREEN}${BOLD}Deploy complete!${NC}"
echo -e "  Open: ${BOLD}http://${PI_HOST}:8000${NC}"
echo ""

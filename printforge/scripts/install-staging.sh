#!/bin/bash
###############################################################################
# install-staging.sh — one-time bootstrap for the PrintForge staging service.
#
# Run this ONCE on the Pi (not on your laptop) after the main `install.sh`.
# It creates a second, isolated instance on port 8001 that runs in mock-serial
# mode, so you can test new features without ever affecting an active print
# on the production instance at :8000.
#
# Usage (on the Pi):
#   cd ~/printforge-src/printforge/scripts
#   bash install-staging.sh
#
# Or from your laptop (SCP + SSH):
#   scp printforge/scripts/{install-staging.sh,printforge-staging.service} \
#       david1534@100.108.194.105:/tmp/
#   ssh david1534@100.108.194.105 "bash /tmp/install-staging.sh"
###############################################################################

set -e

STAGING_DIR="/opt/printforge-staging"
STAGING_DATA="$HOME/printforge-staging"
CURRENT_USER="$(whoami)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BOLD='\033[1m'; NC='\033[0m'

echo -e "${BOLD}PrintForge staging installer${NC}"
echo "────────────────────────────────────────"

# Sanity checks — production must already be installed
if [ ! -d /opt/printforge/venv ]; then
    echo -e "${YELLOW}!${NC} /opt/printforge/venv not found. Run install.sh first (production must exist)."
    exit 1
fi

# Create staging install dir (empty — populate via deploy-staging.sh)
sudo mkdir -p "$STAGING_DIR"
sudo chown "$CURRENT_USER:$CURRENT_USER" "$STAGING_DIR"
echo -e "${GREEN}✓${NC} created $STAGING_DIR"

# Create staging data dirs (fully isolated from production's ~/printforge/)
mkdir -p "$STAGING_DATA/gcodes" "$STAGING_DATA/data" "$STAGING_DATA/logs"
echo -e "${GREEN}✓${NC} created $STAGING_DATA/{gcodes,data,logs}"

# Seed staging with current production code so the service has something to run
if [ -d /opt/printforge/app ]; then
    rsync -a --delete /opt/printforge/app/ "$STAGING_DIR/app/"
    if [ -d /opt/printforge/frontend/build ]; then
        mkdir -p "$STAGING_DIR/frontend"
        rsync -a --delete /opt/printforge/frontend/build/ "$STAGING_DIR/frontend/build/"
    fi
    echo -e "${GREEN}✓${NC} seeded $STAGING_DIR with production code (identical until deploy-staging.sh runs)"
fi

# Provision authentication before exposing staging on 0.0.0.0. Reuse the
# production key when one exists; otherwise preserve an existing staging key
# or create a new one and show it exactly once.
PRINTFORGE_PROD_DB="$HOME/printforge/data/printforge.db" \
PRINTFORGE_STAGE_DB="$STAGING_DATA/data/printforge.db" \
python3 - <<'PY'
import hashlib
import os
import secrets
import sqlite3

prod_path = os.environ["PRINTFORGE_PROD_DB"]
stage_path = os.environ["PRINTFORGE_STAGE_DB"]


def read_hash(path):
    if not os.path.exists(path):
        return ""
    conn = sqlite3.connect(path)
    try:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = 'api_key_hash'"
        ).fetchone()
        return row[0] if row and row[0] else ""
    except sqlite3.OperationalError:
        return ""
    finally:
        conn.close()


prod_hash = read_hash(prod_path)
stage_hash = read_hash(stage_path)
raw_key = ""

if prod_hash:
    selected_hash = prod_hash
    source = "production API key"
elif stage_hash:
    selected_hash = stage_hash
    source = "existing staging API key"
else:
    raw_key = "pf_" + secrets.token_urlsafe(32)
    selected_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    source = "new staging-only API key"

stage = sqlite3.connect(stage_path)
stage.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
stage.execute(
    "INSERT OR REPLACE INTO settings (key, value) VALUES ('api_key_hash', ?)",
    (selected_hash,),
)
stage.commit()
stage.close()

print(f"Staging authentication: {source}")
if raw_key:
    print("Save this key now; it cannot be recovered later:")
    print(raw_key)
PY

# Install the systemd unit, substituting the real user (template ships with User=pi)
sed -e "s|^User=.*|User=$CURRENT_USER|" \
    -e "s|^Group=.*|Group=$CURRENT_USER|" \
    -e "s|/home/pi/printforge-staging|$STAGING_DATA|g" \
    "$SCRIPT_DIR/printforge-staging.service" \
    | sudo tee /etc/systemd/system/printforge-staging.service > /dev/null
echo -e "${GREEN}✓${NC} installed /etc/systemd/system/printforge-staging.service"

sudo systemctl daemon-reload
sudo systemctl enable printforge-staging > /dev/null 2>&1 || true
sudo systemctl start printforge-staging
sleep 3

if sudo systemctl is-active --quiet printforge-staging; then
    PI_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
    echo ""
    echo -e "${GREEN}${BOLD}Staging service is up.${NC}"
    echo -e "  URL:         http://${PI_IP:-<pi>}:8001"
    echo -e "  Logs:        journalctl -u printforge-staging -f"
    echo -e "  Stop:        sudo systemctl stop printforge-staging"
    echo -e "  Deploy WIP:  bash deploy-staging.sh   (run from your laptop)"
    echo -e "  Promote:     bash promote-staging.sh  (staging → production)"
else
    echo -e "${YELLOW}!${NC} staging service did not come up cleanly. Check:"
    echo "   sudo journalctl -u printforge-staging -n 50 --no-pager"
    exit 1
fi

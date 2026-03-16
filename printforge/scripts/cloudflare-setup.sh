#!/bin/bash
# Cloudflare Tunnel Setup for PrintForge
# Provides free remote access to your printer from anywhere
#
# Prerequisites:
# 1. A Cloudflare account (free)
# 2. A domain name added to Cloudflare DNS
#
# Run as: bash cloudflare-setup.sh

set -e

echo "============================================"
echo "  PrintForge - Cloudflare Tunnel Setup"
echo "============================================"
echo ""
echo "This will set up a Cloudflare Tunnel so you"
echo "can access your printer from anywhere."
echo ""

# Step 1: Install cloudflared
echo "[1/4] Installing cloudflared..."
ARCH=$(uname -m)
if [ "$ARCH" = "aarch64" ]; then
    CF_ARCH="arm64"
elif [ "$ARCH" = "armv7l" ]; then
    CF_ARCH="arm"
else
    CF_ARCH="amd64"
fi

curl -L -o /tmp/cloudflared "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${CF_ARCH}"
sudo install -m 755 /tmp/cloudflared /usr/local/bin/cloudflared
rm /tmp/cloudflared
echo "  cloudflared installed: $(cloudflared --version)"

# Step 2: Authenticate
echo ""
echo "[2/4] Authenticating with Cloudflare..."
echo "  A browser window will open. Log in to your Cloudflare account"
echo "  and authorize cloudflared."
echo ""
cloudflared tunnel login

# Step 3: Create tunnel
echo ""
echo "[3/4] Creating tunnel..."
read -p "Enter a name for your tunnel (e.g., 'printforge'): " TUNNEL_NAME
TUNNEL_NAME=${TUNNEL_NAME:-printforge}
cloudflared tunnel create "$TUNNEL_NAME"

# Get tunnel ID
TUNNEL_ID=$(cloudflared tunnel list | grep "$TUNNEL_NAME" | awk '{print $1}')
echo "  Tunnel created: $TUNNEL_ID"

# Step 4: Configure route
echo ""
echo "[4/4] Configuring DNS route..."
read -p "Enter your domain (e.g., 'printer.yourdomain.com'): " HOSTNAME

# Create config
sudo mkdir -p /etc/cloudflared
cat << EOF | sudo tee /etc/cloudflared/config.yml > /dev/null
tunnel: $TUNNEL_ID
credentials-file: /home/$USER/.cloudflared/$TUNNEL_ID.json

ingress:
  - hostname: $HOSTNAME
    service: http://localhost:8000
  - service: http_status:404
EOF

# Create DNS record
cloudflared tunnel route dns "$TUNNEL_NAME" "$HOSTNAME"

# Install as service
sudo cloudflared service install
sudo systemctl enable cloudflared
sudo systemctl start cloudflared

echo ""
echo "============================================"
echo "  Cloudflare Tunnel configured!"
echo "============================================"
echo ""
echo "  Your printer is now accessible at:"
echo "  https://$HOSTNAME"
echo ""
echo "  Manage tunnel:  cloudflared tunnel list"
echo "  View logs:      sudo journalctl -u cloudflared -f"
echo ""
echo "  RECOMMENDED: Set up Cloudflare Access for"
echo "  authentication at dash.cloudflare.com"
echo "  under Zero Trust > Access > Applications"
echo "============================================"

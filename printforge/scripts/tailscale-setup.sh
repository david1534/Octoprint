#!/bin/bash
# Tailscale Setup for PrintForge
# Provides free remote access via VPN mesh network
# No domain name needed - simpler than Cloudflare Tunnel
#
# Run as: bash tailscale-setup.sh

set -e

echo "============================================"
echo "  PrintForge - Tailscale Setup"
echo "============================================"
echo ""
echo "This will set up Tailscale for remote access."
echo "You'll need the Tailscale app on any device"
echo "you want to access the printer from."
echo ""

# Step 1: Install Tailscale
echo "[1/2] Installing Tailscale..."
curl -fsSL https://tailscale.com/install.sh | sh

# Step 2: Connect
echo ""
echo "[2/2] Connecting to Tailscale..."
echo "  A URL will appear. Open it in your browser to authenticate."
echo ""
sudo tailscale up

# Get IP
TAILSCALE_IP=$(tailscale ip -4)

echo ""
echo "============================================"
echo "  Tailscale configured!"
echo "============================================"
echo ""
echo "  Your printer is accessible at:"
echo "  http://$TAILSCALE_IP:8000"
echo ""
echo "  Install Tailscale on your phone/computer:"
echo "  https://tailscale.com/download"
echo ""
echo "  Status: tailscale status"
echo "============================================"

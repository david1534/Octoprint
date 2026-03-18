#!/bin/bash
###############################################################################
# PrintForge Installer
# One-command setup for Raspberry Pi (including OctoPi images)
#
# Usage:
#   bash install.sh
#
# What this script does:
#   1. Detects and safely stops OctoPrint & OctoEverywhere (if present)
#   2. Installs system dependencies (Python, Node.js for frontend build)
#   3. Sets up the Python backend with a virtual environment
#   4. Builds the SvelteKit frontend
#   5. Downloads go2rtc for camera streaming
#   6. Auto-detects your printer's serial port and camera
#   7. Installs systemd services for auto-start on boot
#   8. Creates a restore script so you can switch back to OctoPrint
###############################################################################

set -e

# Colors for clear output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

INSTALL_DIR="/opt/printforge"
DATA_DIR="$HOME/printforge"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CURRENT_USER="$(whoami)"

# Track what we change so the restore script can undo it
OCTOPRINT_WAS_RUNNING=false
OCTOEVERYWHERE_WAS_RUNNING=false
DETECTED_SERIAL_PORT=""
DETECTED_CAMERA=""

step() {
    echo ""
    echo -e "${BLUE}${BOLD}[$1/$TOTAL_STEPS] $2${NC}"
    echo "────────────────────────────────────────────"
}

success() {
    echo -e "  ${GREEN}✓${NC} $1"
}

warn() {
    echo -e "  ${YELLOW}!${NC} $1"
}

fail() {
    echo -e "  ${RED}✗${NC} $1"
}

TOTAL_STEPS=9

###############################################################################
echo ""
echo -e "${BOLD}╔══════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║         PrintForge Installer             ║${NC}"
echo -e "${BOLD}║   3D Printer Control System for RPi      ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════╝${NC}"
echo ""

###############################################################################
step 1 "Checking system & handling existing services"
###############################################################################

# Detect Raspberry Pi
if grep -q "Raspberry\|BCM" /proc/cpuinfo 2>/dev/null; then
    success "Raspberry Pi detected"
else
    warn "Not a Raspberry Pi — installation may still work"
fi

# Detect and handle OctoPrint
if systemctl is-active --quiet octoprint 2>/dev/null; then
    OCTOPRINT_WAS_RUNNING=true
    warn "OctoPrint is currently running"
    echo ""
    echo -e "  PrintForge needs exclusive access to the serial port."
    echo -e "  OctoPrint will be ${YELLOW}stopped and disabled${NC} (not uninstalled)."
    echo -e "  A restore script will be created to switch back anytime."
    echo ""
    read -p "  Proceed? [Y/n] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        echo "Installation cancelled."
        exit 0
    fi
    echo "  Stopping OctoPrint..."
    sudo systemctl stop octoprint
    sudo systemctl disable octoprint 2>/dev/null || true
    success "OctoPrint stopped and disabled"
elif systemctl is-enabled --quiet octoprint 2>/dev/null; then
    OCTOPRINT_WAS_RUNNING=true
    sudo systemctl disable octoprint 2>/dev/null || true
    success "OctoPrint was enabled but not running — disabled it"
else
    success "No OctoPrint service detected"
fi

# Detect and handle OctoEverywhere
if systemctl is-active --quiet octoeverywhere 2>/dev/null; then
    OCTOEVERYWHERE_WAS_RUNNING=true
    sudo systemctl stop octoeverywhere
    sudo systemctl disable octoeverywhere 2>/dev/null || true
    success "OctoEverywhere stopped (PrintForge replaces this too)"
elif systemctl list-unit-files 2>/dev/null | grep -q "octoeverywhere"; then
    OCTOEVERYWHERE_WAS_RUNNING=true
    sudo systemctl disable octoeverywhere 2>/dev/null || true
    success "OctoEverywhere disabled"
else
    success "No OctoEverywhere service detected"
fi

# Check for haproxy (OctoPi uses this on port 80)
if systemctl is-active --quiet haproxy 2>/dev/null; then
    sudo systemctl stop haproxy
    sudo systemctl disable haproxy 2>/dev/null || true
    success "Stopped haproxy (OctoPi reverse proxy — no longer needed)"
fi

# Check for webcamd (OctoPi's camera streamer)
if systemctl is-active --quiet webcamd 2>/dev/null; then
    sudo systemctl stop webcamd
    sudo systemctl disable webcamd 2>/dev/null || true
    success "Stopped webcamd (go2rtc replaces this)"
fi

###############################################################################
step 2 "Installing system dependencies"
###############################################################################

sudo apt-get update -qq
sudo apt-get install -y -qq python3-pip python3-venv python3-dev curl git > /dev/null 2>&1
success "Python 3 + build tools"

# Install Node.js for frontend build
# NodeSource doesn't support armhf, so install from nodejs.org tarball on armv7l
if ! command -v node &> /dev/null || [[ "$(node -v | cut -d. -f1 | tr -d v)" -lt 18 ]]; then
    echo "  Installing Node.js 20 LTS..."
    ARCH=$(uname -m)
    if [ "$ARCH" = "armv7l" ]; then
        NODE_VERSION="v20.18.1"
        NODE_TAR="node-${NODE_VERSION}-linux-armv7l.tar.xz"
        curl -fsSL "https://nodejs.org/dist/${NODE_VERSION}/${NODE_TAR}" -o "/tmp/${NODE_TAR}"
        sudo tar -xJf "/tmp/${NODE_TAR}" -C /usr/local --strip-components=1
        rm -f "/tmp/${NODE_TAR}"
    else
        curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - > /dev/null 2>&1
        sudo apt-get install -y -qq nodejs > /dev/null 2>&1
    fi
    success "Node.js $(node -v) installed"
else
    success "Node.js $(node -v) already installed"
fi

###############################################################################
step 3 "Setting up PrintForge backend"
###############################################################################

sudo mkdir -p "$INSTALL_DIR"
sudo chown "$CURRENT_USER:$CURRENT_USER" "$INSTALL_DIR"

# Copy backend
cp -r "$PROJECT_DIR/backend/"* "$INSTALL_DIR/"
success "Backend files copied to $INSTALL_DIR"

# Python virtual environment
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip -q
"$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt" -q
success "Python dependencies installed"

###############################################################################
step 4 "Building frontend"
###############################################################################

cd "$PROJECT_DIR/frontend"
npm install --silent 2>&1 | tail -1
success "Node dependencies installed"

npm run build 2>&1 | tail -1
success "SvelteKit frontend built"

# Copy build to install directory
mkdir -p "$INSTALL_DIR/frontend"
cp -r build/ "$INSTALL_DIR/frontend/build/"
success "Frontend deployed to $INSTALL_DIR/frontend/build/"

cd "$PROJECT_DIR"

###############################################################################
step 5 "Creating data directories"
###############################################################################

mkdir -p "$DATA_DIR/gcodes"
mkdir -p "$DATA_DIR/data"
mkdir -p "$DATA_DIR/logs"
success "Created $DATA_DIR/{gcodes,data,logs}"

# If OctoPrint had G-code files, offer to copy them
OCTOPRINT_UPLOADS="$HOME/.octoprint/uploads"
if [ -d "$OCTOPRINT_UPLOADS" ]; then
    GCODE_COUNT=$(find "$OCTOPRINT_UPLOADS" -name "*.gcode" -o -name "*.g" -o -name "*.gc" 2>/dev/null | wc -l)
    if [ "$GCODE_COUNT" -gt 0 ]; then
        echo ""
        echo -e "  Found ${BOLD}$GCODE_COUNT G-code files${NC} from OctoPrint."
        read -p "  Copy them to PrintForge? [Y/n] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            cp "$OCTOPRINT_UPLOADS"/*.gcode "$DATA_DIR/gcodes/" 2>/dev/null || true
            cp "$OCTOPRINT_UPLOADS"/*.g "$DATA_DIR/gcodes/" 2>/dev/null || true
            cp "$OCTOPRINT_UPLOADS"/*.gc "$DATA_DIR/gcodes/" 2>/dev/null || true
            success "Copied G-code files to $DATA_DIR/gcodes/"
        fi
    fi
fi

###############################################################################
step 6 "Installing go2rtc (camera streaming)"
###############################################################################

ARCH=$(uname -m)
case "$ARCH" in
    aarch64) GO2RTC_ARCH="arm64" ;;
    armv7l)  GO2RTC_ARCH="arm" ;;
    *)       GO2RTC_ARCH="amd64" ;;
esac

curl -L -s -o "$INSTALL_DIR/go2rtc" \
    "https://github.com/AlexxIT/go2rtc/releases/latest/download/go2rtc_linux_${GO2RTC_ARCH}"
chmod +x "$INSTALL_DIR/go2rtc"
success "go2rtc downloaded ($GO2RTC_ARCH)"

# Auto-detect camera
DETECTED_CAMERA=""
for dev in /dev/video0 /dev/video1 /dev/video2; do
    if [ -e "$dev" ]; then
        DETECTED_CAMERA="$dev"
        break
    fi
done

# Generate go2rtc config with detected camera
# Use exec:ffmpeg source (go2rtc 1.9+ with old ffmpeg 4.x doesn't support ffmpeg:device=)
CAM_DEV="${DETECTED_CAMERA:-/dev/video0}"
cat > "$INSTALL_DIR/go2rtc.yaml" << YAML
streams:
  printer_cam:
    - exec:ffmpeg -f v4l2 -input_format mjpeg -video_size 1280x720 -framerate 30 -i ${CAM_DEV} -pix_fmt yuv420p -c:v h264_v4l2m2m -b:v 2M -g 30 -f h264 -

api:
  listen: ":1984"

webrtc:
  listen: ":8555"
  ice_servers:
    - urls: [stun:stun.l.google.com:19302]
YAML

if [ -n "$DETECTED_CAMERA" ]; then
    success "Camera detected at $DETECTED_CAMERA"
else
    warn "No camera detected — plug one in and restart go2rtc"
fi

###############################################################################
step 7 "Auto-detecting printer serial port"
###############################################################################

DETECTED_SERIAL_PORT=""
DETECTED_BAUD="115200"

# Check for common 3D printer serial devices
for dev in /dev/ttyUSB0 /dev/ttyACM0 /dev/ttyUSB1 /dev/ttyACM1; do
    if [ -e "$dev" ]; then
        DETECTED_SERIAL_PORT="$dev"
        break
    fi
done

# Check if our udev symlink exists
if [ -e "/dev/printforge" ]; then
    DETECTED_SERIAL_PORT="/dev/printforge"
fi

if [ -n "$DETECTED_SERIAL_PORT" ]; then
    success "Printer serial port detected: $DETECTED_SERIAL_PORT"
else
    warn "No serial port found — make sure your printer is connected via USB"
    DETECTED_SERIAL_PORT="/dev/ttyUSB0"
fi

# Install udev rules for stable naming
sudo cp "$SCRIPT_DIR/udev/99-printforge.rules" /etc/udev/rules.d/
sudo udevadm control --reload-rules 2>/dev/null || true
sudo udevadm trigger 2>/dev/null || true
success "udev rules installed (creates /dev/printforge symlink)"

# Add user to required groups
sudo usermod -aG dialout "$CURRENT_USER" 2>/dev/null || true
sudo usermod -aG video "$CURRENT_USER" 2>/dev/null || true
success "User added to dialout + video groups"

# Add sudoers entry for power controls (shutdown, reboot, service restart)
echo "$CURRENT_USER ALL=(ALL) NOPASSWD: /sbin/shutdown, /bin/systemctl restart printforge" | sudo tee /etc/sudoers.d/printforge > /dev/null
sudo chmod 440 /etc/sudoers.d/printforge
success "Sudoers entry for power controls"

###############################################################################
step 8 "Installing systemd services"
###############################################################################

# Generate printforge service with detected settings
cat << EOF | sudo tee /etc/systemd/system/printforge.service > /dev/null
[Unit]
Description=PrintForge 3D Printer Control System
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
Group=$CURRENT_USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
Environment=PRINTFORGE_SERIAL_PORT=$DETECTED_SERIAL_PORT
Environment=PRINTFORGE_SERIAL_BAUDRATE=$DETECTED_BAUD
Environment=PRINTFORGE_GCODE_DIR=$DATA_DIR/gcodes
Environment=PRINTFORGE_DATA_DIR=$DATA_DIR/data
Environment=PRINTFORGE_LOG_LEVEL=INFO

[Install]
WantedBy=multi-user.target
EOF
success "PrintForge service created"

# Generate go2rtc service
cat << EOF | sudo tee /etc/systemd/system/go2rtc.service > /dev/null
[Unit]
Description=go2rtc Camera Streaming for PrintForge
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
Group=$CURRENT_USER
ExecStart=$INSTALL_DIR/go2rtc -config $INSTALL_DIR/go2rtc.yaml
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
success "go2rtc service created"

sudo systemctl daemon-reload
sudo systemctl enable printforge go2rtc
sudo systemctl start go2rtc
sudo systemctl start printforge
success "Services enabled and started"

###############################################################################
step 9 "Creating restore script (switch back to OctoPrint)"
###############################################################################

cat > "$DATA_DIR/restore-octoprint.sh" << 'RESTORE'
#!/bin/bash
# Restore OctoPrint and disable PrintForge
# Run: bash ~/printforge/restore-octoprint.sh

echo "Restoring OctoPrint..."

sudo systemctl stop printforge 2>/dev/null
sudo systemctl stop go2rtc 2>/dev/null
sudo systemctl disable printforge 2>/dev/null
sudo systemctl disable go2rtc 2>/dev/null

if systemctl list-unit-files | grep -q octoprint; then
    sudo systemctl enable octoprint
    sudo systemctl start octoprint
    echo "✓ OctoPrint restored and started"
else
    echo "! OctoPrint service not found — it may not have been installed as a service"
fi

if systemctl list-unit-files | grep -q octoeverywhere; then
    sudo systemctl enable octoeverywhere
    sudo systemctl start octoeverywhere
    echo "✓ OctoEverywhere restored"
fi

if systemctl list-unit-files | grep -q haproxy; then
    sudo systemctl enable haproxy
    sudo systemctl start haproxy
fi

if systemctl list-unit-files | grep -q webcamd; then
    sudo systemctl enable webcamd
    sudo systemctl start webcamd
fi

echo ""
echo "OctoPrint should be available at http://$(hostname -I | awk '{print $1}')"
echo "To switch back to PrintForge: sudo systemctl stop octoprint && sudo systemctl start printforge"
RESTORE
chmod +x "$DATA_DIR/restore-octoprint.sh"
success "Created ~/printforge/restore-octoprint.sh"

###############################################################################
# Done!
###############################################################################
PI_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
PI_IP=${PI_IP:-"<your-pi-ip>"}

echo ""
echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}${BOLD}║         PrintForge installed!                ║${NC}"
echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BOLD}Open in your browser:${NC}"
echo -e "  ${BLUE}http://${PI_IP}:8000${NC}"
echo ""
echo -e "  ${BOLD}What to do next:${NC}"
echo -e "  1. Open the URL above on your phone or computer"
echo -e "  2. Go to ${BOLD}Settings${NC} and click ${BOLD}Connect${NC}"
echo -e "     Serial port: ${BOLD}${DETECTED_SERIAL_PORT}${NC}"
echo -e "     Baud rate:   ${BOLD}${DETECTED_BAUD}${NC}"
echo -e "  3. Try the ${BOLD}Terminal${NC} tab — send G28 to home your printer"
echo ""
if [ -n "$DETECTED_CAMERA" ]; then
    echo -e "  ${GREEN}✓${NC} Camera: streaming from $DETECTED_CAMERA"
else
    echo -e "  ${YELLOW}!${NC} Camera: no webcam detected — plug one in and run:"
    echo -e "    sudo systemctl restart go2rtc"
fi
echo ""
echo -e "  ${BOLD}Useful commands:${NC}"
echo -e "  View logs:         sudo journalctl -u printforge -f"
echo -e "  Restart:           sudo systemctl restart printforge"
echo -e "  Switch to OctoPrint: bash ~/printforge/restore-octoprint.sh"
echo ""
if $OCTOPRINT_WAS_RUNNING; then
    echo -e "  ${YELLOW}NOTE:${NC} OctoPrint was disabled but NOT uninstalled."
    echo -e "  Your OctoPrint config and files are untouched."
    echo -e "  Run the restore script anytime to switch back."
    echo ""
fi
echo -e "  ${RED}${BOLD}IMPORTANT:${NC} Make sure you've taped over the 5V pin"
echo -e "  on the USB cable between Pi and printer!"
echo -e "  See: docs/USB_POWER_WARNING.md"
echo ""
# Check if user needs to re-login for group access
if ! groups | grep -q dialout; then
    echo -e "  ${YELLOW}ACTION NEEDED:${NC} Log out and back in for serial port access:"
    echo -e "  Type ${BOLD}exit${NC} then SSH back in"
    echo ""
fi

# PrintForge Setup Guide

Complete guide to setting up PrintForge on your Raspberry Pi with an Ender 3 S1 Pro.

## What You'll End Up With

- Full printer control from any browser on your local network
- Live camera feed of your prints
- File upload, print management, temperature control, and G-code terminal
- Free remote access from anywhere (optional — Cloudflare Tunnel or Tailscale)
- A one-command restore script to switch back to OctoPrint at any time

## Prerequisites

| Item | Details |
|------|---------|
| **Raspberry Pi** | Pi 4 (2GB+ RAM). Currently running OctoPi or Raspberry Pi OS — either works. |
| **Printer** | Ender 3 S1 Pro with stock Marlin firmware |
| **USB Cable** | Type-A to Type-C or Micro-B (depends on your printer's port) |
| **Webcam** | USB webcam for print monitoring (optional but recommended) |
| **Network** | Pi connected to your local network (Ethernet or Wi-Fi) |
| **SSH Access** | You can SSH into your Pi from your computer |

> **Already running OctoPrint/OctoPi?** Perfect — the installer handles everything automatically. It will safely stop OctoPrint, set up PrintForge, and create a restore script so you can switch back at any time. Nothing gets uninstalled.

---

## Step 0: Block the USB 5V Pin (CRITICAL)

> **Do this BEFORE connecting the USB cable between your Pi and printer.**

The USB cable carries 5V power through pin 1. This can damage your Pi or printer's control board by back-feeding power. You **must** block it.

### Option A — Electrical Tape (Recommended)

1. Look at the USB-A connector (the flat rectangular end that plugs into the Pi)
2. With the contacts facing you, the 5V pin is the **rightmost** pin
3. Put a small piece of **electrical tape** over just that one pin
4. Make sure the other 3 pins are uncovered
5. Plug in the cable

### Option B — USB Power Blocker Dongle

Buy a "USB power blocker" or "USB data-only adapter" — a few dollars on Amazon. Plug it between the cable and the Pi.

### Option C — Cut the Red Wire (Permanent)

If you have a dedicated USB cable for the printer: open the sheath, cut the **red wire** (5V), leave black/white/green intact, tape it up.

### How to Verify It Worked

1. Turn off the printer (power switch off)
2. Connect the USB cable to the Pi
3. The printer screen should stay **OFF**
4. If the screen lights up → the 5V is still getting through, re-check your fix

See [USB_POWER_WARNING.md](USB_POWER_WARNING.md) for more details.

---

## Step 1: Get the Code onto Your Pi

SSH into your Raspberry Pi:

```bash
ssh pi@<your-pi-ip>
```

> **Don't know your Pi's IP?** Check your router's connected devices page, or if you're on OctoPi, try `ssh pi@octopi.local`.

Clone the repository:

```bash
git clone <your-repo-url> ~/printforge-src
cd ~/printforge-src/printforge
```

---

## Step 2: Run the Installer

This is the only command you need. Everything else is automatic:

```bash
bash scripts/install.sh
```

The installer will walk you through **9 steps** with clear progress output:

| Step | What It Does |
|------|-------------|
| **1** | Detects your system. If OctoPrint, OctoEverywhere, haproxy, or webcamd are running, it asks permission then safely stops and disables them. |
| **2** | Installs system dependencies — Python 3, Node.js 20 LTS (for building the frontend), and build tools. |
| **3** | Sets up the PrintForge backend — copies files to `/opt/printforge`, creates a Python virtual environment, installs all pip packages. |
| **4** | Builds the SvelteKit frontend on the Pi — runs `npm install` and `npm run build`, deploys the compiled static files. |
| **5** | Creates data directories at `~/printforge/` (gcodes, data, logs). If you had G-code files in OctoPrint, it offers to copy them over. |
| **6** | Downloads go2rtc (lightweight camera streamer) and auto-detects your USB webcam. |
| **7** | Auto-detects your printer's serial port, installs udev rules for a stable `/dev/printforge` symlink, and adds your user to the `dialout` and `video` groups. |
| **8** | Creates and installs systemd services so PrintForge and go2rtc start automatically on boot. |
| **9** | Generates a restore script at `~/printforge/restore-octoprint.sh` so you can switch back to OctoPrint at any time. |

### What to Expect

- **Duration**: 5-15 minutes depending on your Pi and internet speed (Node.js install + frontend build are the slowest parts)
- **Prompts**: You'll be asked 1-2 questions:
  - If OctoPrint is running: "Proceed? [Y/n]"
  - If OctoPrint had G-code files: "Copy them to PrintForge? [Y/n]"
- **Errors**: If anything fails, the script stops immediately with a clear error message (thanks to `set -e`)

### After the Installer Finishes

You'll see a summary with your Pi's IP address and next steps. **Important**:

```
⚠ ACTION NEEDED: Log out and back in for serial port access
```

If you see this message, you need to log out and SSH back in for the `dialout` group to take effect:

```bash
exit
ssh pi@<your-pi-ip>
```

---

## Step 3: Verify Installation

### Check Services Are Running

```bash
sudo systemctl status printforge
sudo systemctl status go2rtc
```

Both should show **active (running)** in green.

### Open the Web UI

On any device on your local network, open a browser and go to:

```
http://<your-pi-ip>:8000
```

You should see the PrintForge dashboard with a dark theme.

> **Tip**: Bookmark this on your phone for quick access.

---

## Step 4: Connect to Your Printer

1. Make sure the USB cable is connected (with 5V pin blocked!) and the printer is powered on
2. In the PrintForge web UI, go to **Settings** (gear icon)
3. The serial port should be auto-detected (usually `/dev/ttyUSB0` or `/dev/printforge`)
4. Baud rate should be **115200** (default for Ender 3 S1 Pro)
5. Click **Connect**

You should see the status change to **Idle** and the firmware name appear.

### If Connection Fails

- **Port not found**: Run `ls /dev/tty*` in SSH to see available ports
- **Permission denied**: Make sure you logged out and back in after install (for `dialout` group)
- **No response**: Try baud rate **250000** instead of 115200
- **Still nothing**: Check the USB cable and the 5V pin block

---

## Step 5: Test Basic Functions

1. Go to the **Terminal** page
2. Type `G28` and press Enter — this homes all axes (the printer will move!)
3. Type `M105` and press Enter — this reports current temperatures
4. Go to the **Control** page and try the jog buttons to move the print head

If all of this works, your serial communication is solid.

---

## Step 6: Check the Camera

If you have a USB webcam plugged in:

1. The camera feed should appear on the **Dashboard** page
2. If it doesn't, check the go2rtc logs:

```bash
sudo journalctl -u go2rtc -f
```

3. If the camera isn't detected, try a different USB port (avoid USB hubs) and restart:

```bash
sudo systemctl restart go2rtc
```

4. If you need to change the camera device or resolution:

```bash
sudo nano /opt/printforge/go2rtc.yaml
```

Change `/dev/video0` to your camera's device path (check with `ls /dev/video*`), then restart go2rtc.

---

## Step 7: Your First Print

1. Slice a model in your slicer (PrusaSlicer, Cura, etc.) as normal
2. In PrintForge, go to the **Files** page
3. Drag and drop the `.gcode` file onto the upload zone (or click to browse)
4. The file will appear in the list with metadata (estimated time, layers, filament usage)
5. Click **Print** on the file
6. Monitor progress on the **Dashboard** — you'll see temperature charts, progress bar, ETA, and camera feed

### During a Print

- **Pause**: Retracts filament, lifts Z, parks the nozzle safely in the corner
- **Resume**: Returns to position, primes filament, continues printing
- **Cancel**: Turns off heaters and fan, homes X and Y

---

## Step 8: Remote Access (Optional)

Choose one of these options to access PrintForge from outside your local network:

### Option A — Tailscale (Simplest, 100% Free)

Best if you just want it to work with no fuss. Requires installing the Tailscale app on each device you want to access the printer from.

```bash
bash ~/printforge-src/printforge/scripts/tailscale-setup.sh
```

This will:
1. Install Tailscale on your Pi
2. Give you a URL to authenticate in your browser
3. Show you the Tailscale IP to access PrintForge

Then install Tailscale on your phone/computer from [tailscale.com/download](https://tailscale.com/download) and access your printer at `http://<tailscale-ip>:8000`.

### Option B — Cloudflare Tunnel (More Polished)

Best if you want a clean URL like `printer.yourdomain.com`. Requires a Cloudflare account (free) and a domain name (~$10/year for a cheap `.xyz` domain).

```bash
bash ~/printforge-src/printforge/scripts/cloudflare-setup.sh
```

This will walk you through:
1. Installing cloudflared
2. Authenticating with your Cloudflare account
3. Creating a tunnel and DNS route
4. Installing as a systemd service

After setup, access your printer at `https://printer.yourdomain.com`.

> **Recommended**: Set up Cloudflare Access (Zero Trust) for email-based authentication so only you can access it. Go to the Cloudflare dashboard → Zero Trust → Access → Applications.

---

## Useful Commands Reference

### Service Management

```bash
# View live logs
sudo journalctl -u printforge -f
sudo journalctl -u go2rtc -f

# Restart services
sudo systemctl restart printforge
sudo systemctl restart go2rtc

# Stop services
sudo systemctl stop printforge
sudo systemctl stop go2rtc

# Disable auto-start on boot
sudo systemctl disable printforge
```

### Switching Back to OctoPrint

If you want to go back to OctoPrint at any time:

```bash
bash ~/printforge/restore-octoprint.sh
```

This stops PrintForge, re-enables and starts OctoPrint (and OctoEverywhere/haproxy/webcamd if they were previously running). Your OctoPrint configuration and files are untouched — nothing was uninstalled.

To switch back to PrintForge later:

```bash
sudo systemctl stop octoprint
sudo systemctl start printforge go2rtc
```

### Configuration

The main settings are environment variables in the systemd service file:

```bash
sudo nano /etc/systemd/system/printforge.service
```

| Variable | Default | Description |
|----------|---------|-------------|
| `PRINTFORGE_SERIAL_PORT` | Auto-detected | Serial port path (`/dev/ttyUSB0`, `/dev/printforge`, etc.) |
| `PRINTFORGE_SERIAL_BAUDRATE` | `115200` | Baud rate for your printer |
| `PRINTFORGE_GCODE_DIR` | `~/printforge/gcodes` | Where uploaded G-code files are stored |
| `PRINTFORGE_DATA_DIR` | `~/printforge/data` | Database and settings storage |
| `PRINTFORGE_LOG_LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`) |

After editing, reload and restart:

```bash
sudo systemctl daemon-reload
sudo systemctl restart printforge
```

---

## Troubleshooting

### Printer Won't Connect

| Check | How |
|-------|-----|
| USB cable plugged in, 5V blocked | Printer screen should stay off when printer is powered down but USB is connected |
| Serial port exists | `ls /dev/tty*` — look for `ttyUSB0`, `ttyACM0`, or `printforge` |
| User has permission | `groups` — output should include `dialout`. If not, log out and back in |
| Try different baud rate | 115200 (default), 250000, or 57600 |
| OctoPrint not hogging the port | `sudo systemctl status octoprint` — should be inactive |

### Camera Not Showing

| Check | How |
|-------|-----|
| Webcam detected | `ls /dev/video*` — should list at least one device |
| go2rtc running | `sudo systemctl status go2rtc` |
| go2rtc logs | `sudo journalctl -u go2rtc -f` |
| Try different port | Move camera to a different USB port (avoid hubs) |
| Config mismatch | Check `/opt/printforge/go2rtc.yaml` — device path should match `ls /dev/video*` |

### Serial Communication Errors During Printing

- Use a **short, high-quality, shielded USB cable**
- Don't power the Pi from the printer's USB (use a proper 5V/3A power supply)
- Keep the Pi physically away from stepper motor cables (electromagnetic interference)
- Make sure the 5V pin is properly blocked

### Out of Memory

- Check usage: `free -h`
- PrintForge uses ~115MB total (backend ~60MB + go2rtc ~25MB + overhead ~30MB)
- Your Pi 4 with 2GB+ has plenty of headroom
- If tight for some reason, reduce go2rtc resolution in the YAML config

### Web UI Not Loading

| Check | How |
|-------|-----|
| Service running | `sudo systemctl status printforge` |
| Port open | `curl http://localhost:8000` from the Pi itself |
| Firewall | `sudo ufw status` — port 8000 should be allowed (or ufw should be inactive) |
| View error logs | `sudo journalctl -u printforge --no-pager -n 50` |

---

## Data Locations

| What | Where |
|------|-------|
| Application files | `/opt/printforge/` |
| G-code uploads | `~/printforge/gcodes/` |
| Database + settings | `~/printforge/data/` |
| Logs | `~/printforge/logs/` |
| Systemd service | `/etc/systemd/system/printforge.service` |
| go2rtc service | `/etc/systemd/system/go2rtc.service` |
| go2rtc config | `/opt/printforge/go2rtc.yaml` |
| Camera streaming | `/opt/printforge/go2rtc` (binary) |
| udev rules | `/etc/udev/rules.d/99-printforge.rules` |
| Restore script | `~/printforge/restore-octoprint.sh` |

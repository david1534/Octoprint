# PrintForge — Complete Setup & Deploy Guide

## Prerequisites

- Raspberry Pi (3B+/4/5) with Raspberry Pi OS
- 3D printer connected via USB
- USB webcam (optional, for camera feed)
- Another computer on the same network (for setup)

> **USB Power Warning:** Tape over the 5V pin on the USB cable between the Pi
> and your printer to prevent the Pi from back-powering the printer's logic board.

---

## Fresh Install (first time)

### 1. Clone the repo on the Pi

```bash
ssh david1534@100.108.194.105
git clone https://github.com/david1534/Octoprint.git ~/Octoprint
```

### 2. Run the installer

```bash
cd ~/Octoprint/printforge
bash scripts/install.sh
```

This handles everything automatically:
- Detects and safely stops OctoPrint (if present)
- Installs Python 3, Node.js, ffmpeg
- Sets up a Python venv with all backend dependencies
- Builds the SvelteKit frontend
- Auto-detects your printer serial port and camera
- Installs systemd services (`printforge`, `ustreamer`)
- Creates a restore script to switch back to OctoPrint

### 3. Install ustreamer (camera)

ustreamer needs to be built from source on the Pi:

```bash
sudo apt-get install -y libevent-dev libjpeg-dev libbsd-dev
git clone --depth 1 https://github.com/pikvm/ustreamer.git /tmp/ustreamer
cd /tmp/ustreamer && make -j$(nproc)
sudo install -m 755 ustreamer /usr/local/bin/ustreamer
```

Copy the service file and enable it:

```bash
sudo cp ~/Octoprint/printforge/scripts/ustreamer.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ustreamer
```

### 4. Open PrintForge

```
http://100.108.194.105:8000
```

Go to **Settings > Connect** to connect to your printer.

---

## Deploying Updates (after code changes)

### Option A: Run the update script on the Pi (recommended)

SSH into the Pi and run the update script. It pulls the latest code from
GitHub, detects what changed, and only rebuilds/restarts what's needed.

```bash
ssh david1534@100.108.194.105
bash ~/Octoprint/printforge/scripts/update.sh
```

Or as a one-liner from your laptop:

```bash
ssh david1534@100.108.194.105 "bash ~/Octoprint/printforge/scripts/update.sh"
```

> **Windows users:** If you get syntax errors, Git may have converted line
> endings to CRLF. Fix with: `git config --global core.autocrlf input`
> then re-clone, or run `sed -i 's/\r$//' ~/Octoprint/printforge/scripts/update.sh`
> on the Pi before running the script. The script also auto-fixes this on its own.

### Option B: Full deploy from your dev machine

Pushes files from your local machine to the Pi via SCP (doesn't need the
repo cloned on the Pi):

```bash
cd ~/Desktop/Octoprint/printforge
SKIP_CHECKS=true bash scripts/deploy.sh
```

### Option C: Manual quick deploy

If you just want to copy specific files:

```bash
# Backend only
scp -r printforge/backend/app/ david1534@100.108.194.105:/opt/printforge/app/
ssh david1534@100.108.194.105 "sudo systemctl restart printforge"

# Single file
scp printforge/backend/app/serial/protocol.py \
    david1534@100.108.194.105:/opt/printforge/app/serial/
ssh david1534@100.108.194.105 "sudo systemctl restart printforge"
```

---

## Remote Access (optional)

### Tailscale (easiest — no domain needed)

```bash
ssh david1534@100.108.194.105
bash ~/Octoprint/printforge/scripts/tailscale-setup.sh
```

Install Tailscale on your phone/laptop too. Access the printer via the Tailscale IP.

### Cloudflare Tunnel (requires a domain)

```bash
ssh david1534@100.108.194.105
bash ~/Octoprint/printforge/scripts/cloudflare-setup.sh
```

Gives you a public HTTPS URL like `https://printer.yourdomain.com`.

---

## Services & Logs

| Service | What it does | Port |
|---|---|---|
| `printforge` | Backend API + frontend | 8000 |
| `ustreamer` | Camera MJPEG streaming | 8080 |

```bash
# View logs
sudo journalctl -u printforge -f
sudo journalctl -u ustreamer -f

# Restart
sudo systemctl restart printforge
sudo systemctl restart ustreamer

# Status
sudo systemctl status printforge ustreamer
```

---

## Project Structure

```
printforge/
├── backend/app/           # FastAPI backend (Python)
│   ├── api/               # REST endpoints (printer, files, system, etc.)
│   ├── serial/            # Serial protocol, command queue, temp parsing
│   ├── printer/           # Controller, state machine, G-code parser
│   ├── services/          # Camera, timelapse
│   └── storage/           # SQLite database, models
├── frontend/src/          # SvelteKit frontend (Svelte 5 + Tailwind v3)
│   ├── lib/components/    # UI components (18 total)
│   ├── lib/stores/        # Svelte stores (printer state, temp history)
│   └── routes/            # File-based routing (pages)
└── scripts/               # Install, deploy, service files
```

---

## Key Paths on the Pi

| What | Path |
|---|---|
| Backend code | `/opt/printforge/app/` |
| Python venv | `/opt/printforge/venv/` |
| Frontend build | `/opt/printforge/frontend/build/` |
| G-code files | `~/printforge/gcodes/` |
| Database | `~/printforge/data/printforge.db` |
| Timelapse | `~/printforge/data/timelapse/` |
| Logs | `sudo journalctl -u printforge` |

---

## Troubleshooting

### PrintForge won't start
```bash
sudo journalctl -u printforge -n 50 --no-pager
```

### Can't connect to printer
- Check the USB cable is plugged in
- Verify the serial port: `ls /dev/ttyUSB* /dev/ttyACM*`
- Make sure user is in `dialout` group: `groups`
- Tape the 5V USB pin if you haven't already

### Camera not showing
- Check ustreamer: `sudo systemctl status ustreamer`
- Verify device exists: `ls /dev/video*`
- Test directly: `curl http://localhost:8080/snapshot -o test.jpg`

### Temperature readings stuck at 0
Fixed in commit `353312a`. Deploy the latest backend code — the fix drains
unsolicited serial data (M155 auto-reports) during idle periods.

### Switch back to OctoPrint
```bash
bash ~/printforge/restore-octoprint.sh
```

---

## Development (local machine)

```bash
cd printforge

# Backend
cd backend && pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Frontend
cd frontend && bun install && bun run dev

# Both at once
make dev

# Tests
make test

# Lint + typecheck + test
make check
```

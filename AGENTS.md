# AGENTS.md

## Project Overview

**PrintForge** — A self-hosted 3D printer control system (modern OctoPrint replacement). Runs on a Raspberry Pi, connects via USB serial to Marlin-based printers (Ender 3 S1 Pro primary target).

**Stack:** SvelteKit (Svelte 5) + FastAPI (Python) + SQLite + pyserial-asyncio + go2rtc (camera)

## Architecture

```
Octoprint/
├── .claude/
│   ├── settings.local.json           # Permissions for SSH/SCP deploy commands
│   └── skills/
│       ├── frontend-component/        # Build Svelte 5 components with design system
│       ├── frontend-page/             # Add SvelteKit routes with nav integration
│       ├── add-api-endpoint/          # Add FastAPI endpoints with full patterns
│       ├── add-printer-command/       # Full-stack G-code command flow
│       └── debug-printer/             # Serial/printer diagnostic workflow
├── printforge/
│   ├── Makefile                       # dev-backend, dev-frontend, build, install
│   ├── docs/
│   │   ├── SETUP_GUIDE.md            # Raspberry Pi setup instructions
│   │   └── USB_POWER_WARNING.md      # Critical USB 5V pin safety guide
│   ├── scripts/
│   │   ├── install.sh                # One-command Pi installer
│   │   ├── deploy.sh                 # Deployment script
│   │   ├── printforge.service        # systemd service template
│   │   ├── go2rtc.service            # Camera streaming service
│   │   ├── go2rtc.yaml               # go2rtc camera config
│   │   ├── tailscale-setup.sh        # Remote access via Tailscale
│   │   ├── cloudflare-setup.sh       # Remote access via Cloudflare Tunnel
│   │   └── udev/99-printforge.rules  # USB device symlink rules
│   ├── tools/                         # Desktop auto-slicer (Windows, CuraEngine)
│   ├── frontend/
│   │   ├── package.json               # Svelte 5, SvelteKit 2, Tailwind 3, Chart.js 4
│   │   ├── svelte.config.js           # adapter-static, SPA fallback
│   │   ├── vite.config.ts             # /api → :8000, /ws → ws://:8000 proxy
│   │   ├── tailwind.config.js         # surface-* + accent color palette
│   │   └── src/
│   │       ├── app.html               # Dark mode shell, PWA meta, viewport-fit
│   │       ├── app.css                # Tailwind base + .card/.btn-*/.input/.badge-* components
│   │       ├── routes/
│   │       │   ├── +layout.svelte     # App shell: sidebar (desktop), bottom nav (mobile), top bar, E-STOP
│   │       │   ├── +page.svelte       # Dashboard: camera, temps, progress, quick actions
│   │       │   ├── +error.svelte      # Error page
│   │       │   ├── control/+page.svelte    # Jog pad, temp controls, extruder
│   │       │   ├── files/+page.svelte      # File manager with drag-drop, folders, search
│   │       │   ├── timelapse/+page.svelte  # Video gallery, recording settings
│   │       │   ├── mesh/+page.svelte       # Bed mesh visualization
│   │       │   ├── history/+page.svelte    # Print history with stats
│   │       │   ├── terminal/+page.svelte   # G-code terminal
│   │       │   └── settings/+page.svelte   # 6-tab settings panel
│   │       └── lib/
│   │           ├── api.ts             # Typed REST client (50+ methods, 15s timeout, auth)
│   │           ├── websocket.ts       # WebSocket with auto-reconnect, exponential backoff
│   │           ├── utils.ts           # formatFileSize, formatDuration, formatTemp, etc.
│   │           ├── stores/
│   │           │   ├── printer.ts     # WebSocket-driven printer state, derived: isConnected, isPrinting, etc.
│   │           │   ├── files.ts       # File/folder store with navigation
│   │           │   ├── temperature.ts # Rolling 300-point temp history buffer
│   │           │   ├── terminal.ts    # Terminal line buffer (1000 max)
│   │           │   ├── toast.ts       # Toast notifications (success/error/warning/info)
│   │           │   ├── confirm.ts     # Promise-based confirm dialog
│   │           │   └── history.ts     # Print history + aggregated stats
│   │           └── components/
│   │               ├── CameraFeed.svelte        # Snapshot/MJPEG/proxy modes, fullscreen, FPS
│   │               ├── TempChart.svelte          # Chart.js line chart (hotend+bed actual/target)
│   │               ├── TempGauge.svelte          # Progress bar gauge with heating/ready states
│   │               ├── PrintProgress.svelte      # SVG ring + stats grid
│   │               ├── ProgressRing.svelte       # Reusable SVG circular progress
│   │               ├── PreheatPresets.svelte      # PLA/PETG/ABS + custom presets
│   │               ├── PrintStartDialog.svelte    # Pre-print spool selection modal
│   │               ├── JogControls.svelte         # XY d-pad + Z + home, step/feed selectors
│   │               ├── TemperatureControls.svelte # Hotend/bed inputs + presets
│   │               ├── ExtruderControls.svelte    # Extrude/retract + fan + motors
│   │               ├── Terminal.svelte            # Full terminal with history + search
│   │               ├── FileUpload.svelte          # Drag-drop with XHR progress
│   │               ├── BedMesh.svelte             # Canvas bed mesh visualization
│   │               ├── ToastContainer.svelte      # Fly-animated toast stack
│   │               ├── ConfirmDialog.svelte       # Danger/primary confirm modal
│   │               ├── EmptyState.svelte          # Reusable empty placeholder
│   │               ├── LoadingSkeleton.svelte     # Animated skeleton loader
│   │               ├── StatusPill.svelte          # Colored status indicator
│   │               └── QuickStats.svelte          # Compact stats display
│   └── backend/
│       ├── pyproject.toml             # FastAPI, uvicorn, pyserial, aiosqlite, httpx, pydantic
│       ├── tests/                     # pytest: safety, protocol, gcode parser, command queue
│       └── app/
│           ├── main.py                # FastAPI app, CORS, routers, camera proxy, SPA static files
│           ├── config.py              # Pydantic settings (serial, server, storage, camera, safety)
│           ├── middleware/auth.py     # API key middleware (Bearer token, SHA-256)
│           ├── api/
│           │   ├── printer.py         # Printer CRUD: connect, home, jog, temp, print, pause, cancel, E-STOP
│           │   ├── files.py           # File CRUD: list, upload, delete, move, rename, folders
│           │   ├── websocket.py       # WebSocket: state broadcast (1Hz), terminal relay
│           │   ├── history.py         # Print history: paginated list, stats, delete
│           │   ├── timelapse.py       # Timelapse: list/serve/delete videos, recording settings
│           │   ├── settings.py        # Settings CRUD, API key management
│           │   ├── filament.py        # Spool CRUD, activate, deduct, warnings
│           │   └── system.py          # Health (CPU/memory/disk), serial ports, power controls
│           ├── printer/
│           │   ├── state.py           # PrinterState dataclass + PrinterStatus enum
│           │   ├── controller.py      # PrinterController: orchestrates serial, queue, safety, state
│           │   └── gcode_parser.py    # G-code metadata: time, filament, layers, slicer, cost
│           ├── serial/
│           │   ├── connection.py      # Async pyserial: connect/disconnect/send/read
│           │   ├── protocol.py        # MarlinProtocol: send-ack, checksums, resend, temp parsing
│           │   ├── command_queue.py   # Priority queue: SYSTEM > USER > PRINT
│           │   ├── gcode_sender.py    # Async file sender with layer detect, progress, pause
│           │   ├── temperature.py     # Temp parsing + rolling history
│           │   ├── safety.py          # Thermal runaway detection, serial watchdog
│           │   └── bed_mesh.py        # Bed mesh parsing (G29/M420)
│           ├── services/
│           │   └── timelapse.py       # Frame capture, FFmpeg assembly, settings
│           └── storage/
│               ├── database.py        # SQLite: print_jobs, settings, filament_spools
│               └── models.py          # DataStore: CRUD for settings, jobs, spools
```

## Setup Commands

### Development (local machine)
```bash
cd printforge

# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -e .
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Frontend
cd frontend
bun install
bun dev    # http://localhost:5173 (proxies /api to :8000)
```

### Production (Raspberry Pi)
```bash
# One-command install
bash scripts/install.sh

# Or manual
make build    # builds frontend
make install  # full Pi setup
```

### Deployment
```bash
# Via Tailscale (IP: 100.108.194.105)
scp -r printforge/frontend/src david1534@100.108.194.105:~/printforge/frontend/
ssh david1534@100.108.194.105 "cd ~/printforge/frontend && npm run build"
ssh david1534@100.108.194.105 "sudo systemctl restart printforge"
```

## Key Patterns

### Svelte 5 Runes (CRITICAL)
This project uses **Svelte 5** with runes. Never use Svelte 4 syntax:
```
$state()      NOT  let x = value (for reactive state)
$derived()    NOT  $: x = computed
$effect()     NOT  $: { sideEffect() }
$props()      NOT  export let prop
$bindable()   NOT  export let prop (for two-way binding)
onclick={}    NOT  on:click={}
{@render children()}  NOT  <slot />
```

### Data Flow: Real-Time State
```
Printer (serial) → MarlinProtocol (parse) → PrinterState (update)
→ WebSocket broadcast (1Hz) → printerState store → All components reactively update
```

### Data Flow: User Command
```
UI button click → api.home() → POST /api/printer/home
→ printer_controller.home() → protocol.send_command("G28")
→ Serial write → Wait for "ok" → Response back through chain
```

### Authentication
- API key stored in `localStorage` as `printforge:apiKey`
- Sent as `Authorization: Bearer <key>` header
- Backend compares SHA-256 hash
- Key generated/revoked via settings page

### WebSocket
- Single connection at `/ws?api_key=<key>`
- Auto-reconnect with exponential backoff (1s → 30s max)
- Message types: `state` (printer state), `terminal` (serial lines), `ping`/`pong`
- State broadcast rate: 1Hz

## Code Style

### Frontend (Svelte 5 + TypeScript)
- Tailwind CSS v3 utility classes
- Dark-only theme using `surface-*` scale + `accent` blue
- Component classes in `app.css` (`@layer components`)
- Heroicons (outline, inline SVG) for all icons
- `tabular-nums` class on all numerical displays
- `focus-visible:ring-2 focus-visible:ring-accent/50` on all interactive elements
- `transition-all duration-200` on interactive elements

### Backend (Python 3.11+)
- Async throughout (FastAPI + pyserial-asyncio + aiosqlite)
- Type hints on all function signatures
- Pydantic BaseModel for request bodies
- `logger = logging.getLogger(__name__)` per module
- PrinterController singleton pattern
- Priority command queue for serial

## Design System

### Colors (Dark Theme)
- **Background:** `surface-950` (#020617)
- **Cards/Sidebar:** `surface-900` (#0f172a)
- **Inputs/Hover:** `surface-800` (#1e293b)
- **Borders:** `surface-700` (#334155)
- **Accent:** `accent` (#3b82f6 blue-500)
- **Danger:** red-600
- **Success:** emerald-600
- **Warning:** amber-500
- **Hotend color:** orange-400
- **Bed color:** blue-400

### Typography
- **Body:** Inter + system fallback
- **Code:** Tailwind `font-mono` (system monospace)
- **Antialiasing:** `antialiased` globally

### Component Classes
- `.card` — rounded-xl, surface-900, border, hover lift+shadow
- `.btn` / `.btn-primary` / `.btn-secondary` / `.btn-danger` / `.btn-success` — with press scale + glow
- `.btn-icon` — icon-only button with hover background
- `.input` — surface-800, border, focus ring
- `.badge-*` — idle/printing/paused/error/disconnected states

### Layout
- **Desktop:** Fixed sidebar (icon-only at md, full at lg) + main content
- **Mobile:** Full-width content + fixed bottom nav bar with backdrop blur
- **Top bar:** Status badge, live temps, print progress, E-STOP button

## Installed Skills

| Skill | Location | Purpose |
|---|---|---|
| `frontend-component` | `.claude/skills/frontend-component/SKILL.md` | Build Svelte 5 components with PrintForge design system |
| `frontend-page` | `.claude/skills/frontend-page/SKILL.md` | Add SvelteKit routes with nav link and API integration |
| `add-api-endpoint` | `.claude/skills/add-api-endpoint/SKILL.md` | Add FastAPI endpoints with models, controller, and registration |
| `add-printer-command` | `.claude/skills/add-printer-command/SKILL.md` | Full-stack G-code command: controller → API → frontend → UI |
| `debug-printer` | `.claude/skills/debug-printer/SKILL.md` | 7-stage diagnostic for serial/printer/WebSocket issues |

## Deployment

### Target Hardware
- **Host:** Raspberry Pi (SSH user: `david1534`)
- **LAN IP:** `172.20.233.244`
- **Tailscale IP:** `100.108.194.105`
- **Install path:** `/opt/printforge/`
- **Service:** `printforge.service` (systemd)
- **Camera:** go2rtc at `localhost:1984`

### Printer
- **Model:** Ender 3 S1 Pro (Marlin firmware)
- **Serial:** `/dev/ttyUSB0` at 115200 baud (or `/dev/printforge` via udev)
- **Safety:** Tape USB pin 1 to prevent 5V backfeed (see `docs/USB_POWER_WARNING.md`)

## Testing

```bash
# Backend tests
cd printforge/backend
python -m pytest tests/

# Frontend build check
cd printforge/frontend
bun run build
```

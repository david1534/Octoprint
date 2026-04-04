# CLAUDE.md — PrintForge Working Memory

## Quick Reference

| What | Where |
|---|---|
| Frontend source | `printforge/frontend/src/` |
| Backend source | `printforge/backend/app/` |
| Design tokens | `printforge/frontend/tailwind.config.js` + `src/app.css` |
| API client | `printforge/frontend/src/lib/api.ts` (50+ methods) |
| WebSocket | `printforge/frontend/src/lib/websocket.ts` |
| Printer state | `printforge/frontend/src/lib/stores/printer.ts` |
| Routes | `printforge/frontend/src/routes/` (file-based) |
| Components | `printforge/frontend/src/lib/components/` (18 components) |
| Controller | `printforge/backend/app/printer/controller.py` (846 lines, singleton) |
| OctoPrint shim | `printforge/backend/app/api/octoprint_compat.py` (OrcaSlicer + Cura) |
| Serial protocol | `printforge/backend/app/serial/protocol.py` |
| Skills | `.claude/skills/` (5 skills) |

## Gotchas and Hard-Won Knowledge

### Svelte 5 — DO NOT use Svelte 4 syntax
This is the most common source of bugs. The project uses **Svelte 5 runes**:
- `$state()` not `let x = value`
- `$derived()` not `$: x = computed`
- `$effect()` not `$: { sideEffect() }`
- `$props()` not `export let`
- `onclick={}` not `on:click={}`
- `{@render children()}` not `<slot />`
- `$bindable()` for two-way binding props

### Tailwind v3 — NOT v4
The frontend uses Tailwind CSS v3 (utility-first with `@apply`). Tailwind v4 has breaking changes. Specifically:
- Use `@apply` in `@layer components` blocks (v3 pattern)
- `duration-250` does NOT exist — use `duration-200` or `duration-300`
- Color classes use the `surface-*` custom scale from `tailwind.config.js`
- `darkMode: 'class'` is always active (dark only)

### Dark Theme Only
This is a dark-themed industrial app. Never use light background colors. The surface scale goes from `surface-950` (page bg, near black) to `surface-50` (brightest, used as text-surface-50).

### Package Manager
The frontend uses **bun** for install/dev but `npm run build` in the Makefile/deploy scripts. Both work. Use `bun` locally.

### Serial Port Quirks
- USB serial resets the printer on connect (2-3 second delay required)
- Marlin expects send-acknowledge flow (wait for `ok` before next command)
- Line numbering + checksums are only used during print jobs, not manual commands
- Some Marlin firmwares echo back garbage on USB connect — the protocol handles this

### Deploy Flow
1. Build frontend: `cd printforge/frontend && bun run build`
2. SCP files to Pi: `scp -r ... david1534@100.108.194.105:...`
3. Install new deps (if any): `ssh david1534@... "~/printforge/venv/bin/pip install -r ~/printforge/requirements.txt"`
4. Restart service: `ssh david1534@100.108.194.105 "sudo systemctl restart printforge"`
5. Check: `curl http://100.108.194.105:8000`

### Environment Variables
All are optional with sensible defaults. Set via systemd unit (`/etc/systemd/system/printforge.service`) or shell env.
- `PRINTFORGE_SERIAL_PORT` — Serial device path (default: `/dev/ttyUSB0`)
- `PRINTFORGE_SERIAL_BAUDRATE` — Baud rate (default: `115200`)
- `PRINTFORGE_GCODE_DIR` — G-code storage path (default: `~/printforge/gcodes`)
- `PRINTFORGE_DATA_DIR` — Database/data path (default: `~/printforge/data`)
- `PRINTFORGE_CAMERA_URL` — ustreamer base URL (default: `http://localhost:8080`)
- `PRINTFORGE_LOG_LEVEL` — Logging level (default: `INFO`)
- `PRINTFORGE_CORS_ORIGINS` — Comma-separated allowed CORS origins (default: `*`). Set to the Pi's actual address(es) in production to prevent cross-site printer control, e.g. `http://100.108.194.105:8000,http://printforge.local:8000`

### Camera System
- ustreamer runs as a separate service at `localhost:8080`
- Browser connects directly to ustreamer for MJPEG (`http://host:8080/stream`) — no proxy
- Fallback chain: direct MJPEG → proxied MJPEG (`/api/camera/mjpeg`) → snapshot polling
- Snapshot mode uses `<canvas>` for rendering (~10-15 FPS)
- Snapshots fetched from ustreamer's `/snapshot` endpoint (<50ms)

### Slicer Compatibility (OrcaSlicer + Cura)
The OctoPrint-compatible API shim (`printforge/backend/app/api/octoprint_compat.py`) supports both OrcaSlicer and Cura. Key differences handled:
- **File upload**: Cura sends `print`/`select` as multipart form fields; OrcaSlicer sends them as query params. The endpoint checks both.
- **Temperature parsing**: OrcaSlicer embeds authoritative temps in config comments at EOF (`; nozzle_temperature = 215`). Cura auto-injects M104/M109/M140/M190 at the top of the file. The G-code parser handles both paths.
- **Layer markers**: Cura uses `;LAYER:N` (numbered), OrcaSlicer uses `;LAYER_CHANGE` (unnumbered). Both are handled in `gcode_sender.py`.
- **Preamble skipping**: When PrintForge provides start gcode, ALL slicer commands before the first layer marker are skipped. Works for both slicers.
- **API surface**: Settings, login, printer profiles, raw G-code commands, and connection management endpoints are implemented for Cura's OctoPrint plugin.

### API Key Auth
- Stored in `localStorage` as `printforge:apiKey`
- Backend at `/opt/printforge/data/printforge.db` (SQLite)
- SHA-256 hashed for comparison
- WebSocket passes key as `?api_key=` query param

### File System
- G-codes stored at `~/printforge/gcodes/` on the Pi
- Database at `~/printforge/data/printforge.db`
- Timelapse frames/videos in `~/printforge/data/timelapse/`

## When Adding Features

### New component?
Use the `frontend-component` skill. Key things to remember:
- Put it in `printforge/frontend/src/lib/components/`
- Use `$props()` for props, `$state()` for local state
- Apply `.card`, `.btn-*`, `.input` classes from app.css
- Add `focus-visible` ring and `transition` on interactive elements

### New page?
Use the `frontend-page` skill. Don't forget:
- Create `printforge/frontend/src/routes/<name>/+page.svelte`
- Add nav entry to `navItems[]` in `+layout.svelte`
- Nav drives BOTH desktop sidebar AND mobile bottom bar
- Add `<svelte:head><title>` tag

### New API endpoint?
Use the `add-api-endpoint` skill:
- Create router in `printforge/backend/app/api/`
- Register in `main.py` via `app.include_router()`
- Add frontend method in `api.ts`
- Access printer via `printer_controller` singleton, never serial directly

### New printer command?
Use the `add-printer-command` skill:
- Add method to `PrinterController` in `controller.py`
- Add API endpoint in `printer.py` router
- Add frontend `api.method()` call
- Add UI with loading state and toast feedback

### Debugging serial issues?
Use the `debug-printer` skill. Check USB power warning first.

## Verification Commands

```bash
# Frontend builds clean
cd printforge/frontend && bun run build

# Backend imports clean
cd printforge/backend && python -c "from app.main import app; print('OK')"

# Backend tests
cd printforge/backend && python -m pytest tests/

# Check Pi is reachable
ssh -o ConnectTimeout=5 david1534@100.108.194.105 "echo OK"
```

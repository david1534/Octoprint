# Skill: Optimize Performance

Guide for diagnosing and fixing performance issues in PrintForge on Raspberry Pi.

## When to Use
User reports slow UI, high CPU, laggy WebSocket updates, slow file uploads, or memory issues.

## Architecture Bottlenecks

### CPU-Bound Operations
1. **go2rtc ffmpeg transcoding** — H.264 encoding from USB cam uses significant CPU
   - Config: `scripts/go2rtc.yaml`
   - Fix: Reduce resolution (640x480), lower framerate (10-15fps), use `h264_v4l2m2m` hardware encoder
2. **Timelapse video assembly** — ffmpeg encodes MP4 from JPEG frames
   - Code: `backend/app/services/timelapse.py` `_assemble_video()`
   - Fix: Use `-preset ultrafast`, lower `-crf` quality, or assemble after print on idle
3. **G-code parsing** — `backend/app/printer/gcode_parser.py` reads entire file for metadata
   - Fix: Only parse first/last 500 lines for temps and time estimates

### I/O-Bound Operations
1. **Serial communication** — 115200 baud limits throughput
   - Code: `backend/app/serial/protocol.py`, `command_queue.py`
   - The queue processes one command at a time with acknowledgment
2. **SQLite writes** — History, settings, filament tracking all hit disk
   - Code: `backend/app/storage/database.py`
   - Fix: Use WAL mode (already set), batch writes where possible
3. **WebSocket broadcasts** — Every 1s tick serializes state to JSON
   - Code: `backend/app/api/websocket.py`, `printer/controller.py` `_safety_loop()`
   - Fix: Only broadcast when state actually changed (dirty flag)

### Memory
1. **Camera snapshot buffering** — Each JPEG frame is ~50-200KB in memory
   - `backend/app/services/camera.py`, `main.py` snapshot endpoint
2. **MJPEG proxy streaming** — httpx streams 8KB chunks, low memory
3. **G-code file reading** — Line-by-line streaming, not loaded into memory

### Frontend
1. **Snapshot polling** — `CameraFeed.svelte` fetches every 100-200ms
   - Uses `createImageBitmap()` for off-thread decode
   - `bitmap.close()` prevents memory leaks
2. **WebSocket reconnection** — `stores/printer.ts` reconnects on disconnect
3. **Svelte 5 reactivity** — `$state()` runes, `$derived()` for computed values

## Key Config Knobs
- `POLL_INTERVAL` in `CameraFeed.svelte` — ms between snapshot fetches (100-500)
- `_safety_loop` tick rate in `controller.py` — currently 1s
- `chunk_size` in `main.py` MJPEG proxy — currently 8192 bytes
- Timelapse `_render_fps` — lower = shorter assembly time
- go2rtc `-framerate` and `-video_size` in `go2rtc.yaml`

## Optimization Checklist
1. Read `/api/system/health` for CPU, memory, temperature
2. Check go2rtc settings in `scripts/go2rtc.yaml`
3. Check camera polling interval in `CameraFeed.svelte`
4. Review WebSocket broadcast frequency in `_safety_loop`
5. Check timelapse ffmpeg preset in `timelapse.py`
6. Verify SQLite WAL mode in `database.py`

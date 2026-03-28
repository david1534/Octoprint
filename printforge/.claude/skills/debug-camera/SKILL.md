# Skill: Debug Camera

Diagnose and fix camera/timelapse issues in PrintForge.

## When to Use
User reports camera feed not working, timelapse recording 0 frames, snapshot errors, or laggy video.

## Diagnostic Steps

### 1. Check Camera Health Endpoint
Read `backend/app/services/camera.py` and `backend/app/api/system.py` — the `/api/system/camera-health` endpoint reports:
- `ustreamer.available` — is ustreamer reachable?
- `ffmpeg.available` / `ffmpeg.path` — is ffmpeg installed?
- `device.path` / `device.exists` — was a V4L2 camera detected?
- `captureChain` — what fallback sources are active?

### 2. Check the Capture Fallback Chain
The `CameraService` in `backend/app/services/camera.py` tries sources in order:
1. **ustreamer** HTTP snapshot (`/snapshot` — instant, <50ms)
2. **ffmpeg** direct V4L2 capture (`ffmpeg -f v4l2 -i /dev/video0 ...`)
3. **fswebcam** (`fswebcam --no-banner -d /dev/video0 ...`)

If all three fail, `snapshot()` returns `None`.

### 3. Check ustreamer Service
```bash
systemctl status ustreamer
journalctl -u ustreamer -n 30
```
- Is the camera device path correct (`/dev/video0`)?
- Is it listening on port 8080?
- Test directly: `curl -s -o /dev/null -w '%{time_total}' http://localhost:8080/snapshot`

### 4. Check Timelapse Service
Read `backend/app/services/timelapse.py`:
- `_fetch_snapshot()` delegates to `CameraService.snapshot()`
- Frame files saved to `<output_dir>/frames/<name>_<timestamp>/frame_NNNNNN.jpg`
- If `has_ffmpeg` is False, frames saved as ZIP instead of MP4

### 5. Check Frontend Camera Feed
Read `frontend/src/lib/components/CameraFeed.svelte`:
- Default mode: direct MJPEG from ustreamer (`http://host:8080/stream`)
- Fallback 1: proxied MJPEG via `/api/camera/mjpeg`
- Fallback 2: snapshot polling via `fetch()` + `createImageBitmap()` + canvas
- Mode switcher: SNAP / MJPEG buttons in top-right

### 6. Common Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| "Camera unavailable" | ustreamer down + no camera device | Check USB cam plugged in, restart ustreamer |
| 0 timelapse frames | Camera unreachable during print | Check `/api/system/camera-health` |
| ZIP instead of MP4 | ffmpeg not installed | `sudo apt-get install ffmpeg` |
| Laggy feed | Large chunk size or network | Switch to SNAP mode in UI |
| Black frames | Wrong `/dev/video*` device | Check ustreamer service device path |
| "Assembling" stuck | ffmpeg crash or timeout (300s) | Check Pi CPU/memory, reduce frame count |

### 7. Key Files
- `backend/app/services/camera.py` — Capture fallback chain
- `backend/app/services/timelapse.py` — Frame capture + video assembly
- `backend/app/main.py` — Camera proxy endpoints (`/api/camera/*`)
- `backend/app/api/timelapse.py` — Timelapse API (recording status, settings)
- `backend/app/api/system.py` — Camera health endpoint
- `frontend/src/lib/components/CameraFeed.svelte` — Camera UI
- `frontend/src/routes/timelapse/+page.svelte` — Timelapse page
- `scripts/ustreamer.service` — ustreamer systemd service
- `docs/CAMERA_SETUP.md` — User-facing troubleshooting guide

# Skill: Debug Camera

Diagnose and fix camera/timelapse issues in PrintForge.

## When to Use
User reports camera feed not working, timelapse recording 0 frames, snapshot errors, or laggy video.

## Diagnostic Steps

### 1. Check Camera Health Endpoint
Read `backend/app/services/camera.py` and `backend/app/api/system.py` — the `/api/system/camera-health` endpoint reports:
- `go2rtc.available` — is go2rtc reachable?
- `ffmpeg.available` / `ffmpeg.path` — is ffmpeg installed?
- `device.path` / `device.exists` — was a V4L2 camera detected?
- `captureChain` — what fallback sources are active?

### 2. Check the Capture Fallback Chain
The `CameraService` in `backend/app/services/camera.py` tries sources in order:
1. **go2rtc** HTTP snapshot (`/api/frame.jpeg?src=printer_cam`)
2. **ffmpeg** direct V4L2 capture (`ffmpeg -f v4l2 -i /dev/video0 ...`)
3. **fswebcam** (`fswebcam --no-banner -d /dev/video0 ...`)

If all three fail, `snapshot()` returns `None`.

### 3. Check go2rtc Config
Read `scripts/go2rtc.yaml`:
- Is the camera device path correct (`/dev/video0`)?
- Is the stream named `printer_cam`?
- Is it using `exec:ffmpeg` or `exec:libcamera-vid`?

### 4. Check Timelapse Service
Read `backend/app/services/timelapse.py`:
- `_fetch_snapshot()` delegates to `CameraService.snapshot()`
- Frame files saved to `<output_dir>/frames/<name>_<timestamp>/frame_NNNNNN.jpg`
- If `has_ffmpeg` is False, frames saved as ZIP instead of MP4

### 5. Check Frontend Camera Feed
Read `frontend/src/lib/components/CameraFeed.svelte`:
- Default mode: snapshot polling via `fetch()` + `createImageBitmap()` + canvas
- Fallback: MJPEG stream via `<img>` tag
- Mode switcher: SNAP / MJPEG buttons in top-right

### 6. Common Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| "Camera unavailable" | go2rtc down + no camera device | Check USB cam plugged in, restart go2rtc |
| 0 timelapse frames | Camera unreachable during print | Check `/api/system/camera-health` |
| ZIP instead of MP4 | ffmpeg not installed | `sudo apt-get install ffmpeg` |
| Laggy feed | Large chunk size or network | Switch to SNAP mode in UI |
| Black frames | Wrong `/dev/video*` device | Check `go2rtc.yaml` device path |
| "Assembling" stuck | ffmpeg crash or timeout (300s) | Check Pi CPU/memory, reduce frame count |

### 7. Key Files
- `backend/app/services/camera.py` — Capture fallback chain
- `backend/app/services/timelapse.py` — Frame capture + video assembly
- `backend/app/main.py` — Camera proxy endpoints (`/api/camera/*`)
- `backend/app/api/timelapse.py` — Timelapse API (recording status, settings)
- `backend/app/api/system.py` — Camera health endpoint
- `frontend/src/lib/components/CameraFeed.svelte` — Camera UI
- `frontend/src/routes/timelapse/+page.svelte` — Timelapse page
- `scripts/go2rtc.yaml` — go2rtc camera config
- `docs/CAMERA_SETUP.md` — User-facing troubleshooting guide

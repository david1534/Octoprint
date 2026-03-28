# Camera & Timelapse Setup

PrintForge uses **ustreamer** for MJPEG camera streaming. The install script builds it from source and sets up a systemd service automatically.

## What happens automatically

- `install.sh` builds **ustreamer** from source and installs **ffmpeg**
- ustreamer streams MJPEG from the first detected USB camera on port 8080
- The browser connects directly to ustreamer for live video (`http://<pi-ip>:8080/stream`)
- The timelapse system captures snapshots from ustreamer's `/snapshot` endpoint (<50ms)
- A backend proxy at `/api/camera/mjpeg` is available as a fallback
- If ffmpeg is missing, timelapse frames are saved as a ZIP instead of video

## Verify camera works

Open your browser and go to:

```
http://<pi-ip>:8000/api/system/camera-health
```

This shows:
- Whether ustreamer is reachable
- Whether ffmpeg is installed
- Whether a camera device was detected at `/dev/video*`

You can also test a snapshot directly:

```
http://<pi-ip>:8080/snapshot
```

## Troubleshooting

### "Camera unavailable" on the dashboard

1. **Check the camera is plugged in:**
   ```bash
   ls /dev/video*
   ```
   You should see `/dev/video0` (or similar).

2. **Check ustreamer is running:**
   ```bash
   sudo systemctl status ustreamer
   ```
   If it's failed, check the logs:
   ```bash
   sudo journalctl -u ustreamer -n 30
   ```

3. **Restart ustreamer after plugging in a camera:**
   ```bash
   sudo systemctl restart ustreamer
   ```

4. **Test direct capture (bypasses ustreamer):**
   ```bash
   ffmpeg -f v4l2 -i /dev/video0 -frames:v 1 test.jpg
   ```
   If this works but ustreamer doesn't, check the service configuration.

### Timelapse records 0 frames

The camera must be reachable during the print. Check `/api/system/camera-health` — if no capture method is available, ustreamer may not be running.

### Timelapse saves ZIP instead of video

ffmpeg is not installed. Fix:
```bash
sudo apt-get install ffmpeg
sudo systemctl restart printforge
```

### Camera feed is laggy

- Switch to **SNAP** mode in the camera widget (top-right toggle). This polls individual frames and is more reliable than MJPEG streaming.
- If on Wi-Fi, try wired Ethernet — each snapshot is ~50-200KB.
- The default config is 640x480@30fps. Edit the service to adjust if needed.

## Camera types

| Camera | Status |
|--------|--------|
| USB webcam (UVC) | Fully supported, auto-detected |
| Raspberry Pi Camera Module | Supported — use `--device /dev/video0` (libcamera exposes as V4L2) |
| IP camera (RTSP) | Not directly supported by ustreamer — use ffmpeg to re-stream |

### Changing camera device or resolution

Edit the ustreamer service file:

```bash
sudo systemctl edit ustreamer --full
```

Change `--device`, `--resolution`, or `--desired-fps` as needed, then restart:

```bash
sudo systemctl restart ustreamer
```

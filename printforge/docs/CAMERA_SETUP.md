# Camera & Timelapse Setup

PrintForge auto-detects your camera and sets everything up during install. This doc covers what to check if something isn't working.

## What happens automatically

- `install.sh` installs **ffmpeg**, **fswebcam**, and **go2rtc**
- go2rtc is configured to stream from the first detected USB camera
- The timelapse system captures frames through a 3-level fallback chain:
  1. **go2rtc** HTTP snapshot (fastest, ~10ms)
  2. **ffmpeg** direct V4L2 capture (if go2rtc is down, ~300ms)
  3. **fswebcam** (last resort, ~500ms)
- If ffmpeg is missing, timelapse frames are saved as a ZIP instead of video

## Verify camera works

Open your browser and go to:

```
http://<pi-ip>:8000/api/system/camera-health
```

This shows:
- Whether go2rtc is reachable
- Whether ffmpeg is installed
- Whether a camera device was detected at `/dev/video*`
- The active capture fallback chain

You can also test a snapshot directly:

```
http://<pi-ip>:8000/api/camera/snapshot
```

## Troubleshooting

### "Camera unavailable" on the dashboard

1. **Check the camera is plugged in:**
   ```bash
   ls /dev/video*
   ```
   You should see `/dev/video0` (or similar).

2. **Check go2rtc is running:**
   ```bash
   sudo systemctl status go2rtc
   ```
   If it's failed, check the logs:
   ```bash
   sudo journalctl -u go2rtc -n 30
   ```

3. **Restart go2rtc after plugging in a camera:**
   ```bash
   sudo systemctl restart go2rtc
   ```

4. **Test direct capture (bypasses go2rtc):**
   ```bash
   ffmpeg -f v4l2 -i /dev/video0 -frames:v 1 test.jpg
   ```
   If this works but go2rtc doesn't, the issue is go2rtc config.

### Timelapse records 0 frames

The camera must be reachable during the print. Check `/api/system/camera-health` and look at the `captureChain` — if it says `["none"]`, no capture method is available.

### Timelapse saves ZIP instead of video

ffmpeg is not installed. Fix:
```bash
sudo apt-get install ffmpeg
sudo systemctl restart printforge
```

### Camera feed is laggy

- Switch to **SNAP** mode in the camera widget (top-right toggle). This polls individual frames and is more reliable than MJPEG streaming.
- If on Wi-Fi, try wired Ethernet — each snapshot is ~50-200KB.
- The go2rtc config at `/opt/printforge/go2rtc.yaml` defaults to 640x480@15fps. You can increase this if your Pi handles it.

## Camera types

| Camera | Status |
|--------|--------|
| USB webcam (UVC) | Fully supported, auto-detected |
| Raspberry Pi Camera Module | Supported — uncomment the `libcamera-vid` line in `go2rtc.yaml` |
| IP camera (RTSP) | Add the RTSP URL to `go2rtc.yaml` streams |

### Using Raspberry Pi Camera Module

Edit `/opt/printforge/go2rtc.yaml` and swap the stream source:

```yaml
streams:
  printer_cam:
    # Comment out the USB webcam line:
    # - exec:ffmpeg -f v4l2 ...
    # Uncomment the Pi camera line:
    - exec:libcamera-vid -t 0 --inline -o - --width 640 --height 480 --framerate 15
```

Then restart:
```bash
sudo systemctl restart go2rtc
```

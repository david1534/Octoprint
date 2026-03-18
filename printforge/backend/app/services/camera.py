"""Camera capture service with multi-source fallback.

Provides a single async ``snapshot()`` method that tries sources in order:
1. go2rtc HTTP snapshot  (fastest — already running, zero startup cost)
2. ffmpeg direct V4L2    (no go2rtc needed, ~0.3s per frame)
3. fswebcam              (last resort, ~0.5s per frame)

Also provides utilities for auto-detecting the camera device, checking
ffmpeg availability, and streaming MJPEG from go2rtc.
"""

import asyncio
import glob
import logging
import shutil
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class CameraService:
    """Unified camera interface with automatic fallback."""

    def __init__(self, go2rtc_url: str = "http://localhost:1984"):
        self._go2rtc_url = go2rtc_url
        self._camera_device: Optional[str] = None  # e.g. /dev/video0
        self._ffmpeg_path: Optional[str] = None
        self._fswebcam_path: Optional[str] = None
        self._go2rtc_ok: Optional[bool] = None  # None = untested
        self._client: Optional[httpx.AsyncClient] = None

    async def init(self) -> None:
        """Detect available tools and camera device at startup."""
        self._ffmpeg_path = shutil.which("ffmpeg")
        self._fswebcam_path = shutil.which("fswebcam")
        self._camera_device = self._detect_camera_device()
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(5.0))

        # Test go2rtc connectivity once
        self._go2rtc_ok = await self._test_go2rtc()

        logger.info(
            "Camera service initialized: go2rtc=%s ffmpeg=%s fswebcam=%s device=%s",
            "up" if self._go2rtc_ok else "down",
            self._ffmpeg_path or "not found",
            self._fswebcam_path or "not found",
            self._camera_device or "none",
        )

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def has_ffmpeg(self) -> bool:
        return self._ffmpeg_path is not None

    @property
    def has_camera_device(self) -> bool:
        return self._camera_device is not None

    @property
    def go2rtc_available(self) -> bool:
        return self._go2rtc_ok is True

    @property
    def camera_device(self) -> Optional[str]:
        return self._camera_device

    def health_dict(self) -> dict:
        """Return camera health status for the API."""
        return {
            "go2rtc": {
                "available": self._go2rtc_ok is True,
                "url": self._go2rtc_url,
            },
            "ffmpeg": {
                "available": self._ffmpeg_path is not None,
                "path": self._ffmpeg_path,
            },
            "fswebcam": {
                "available": self._fswebcam_path is not None,
            },
            "device": {
                "path": self._camera_device,
                "exists": self._camera_device is not None
                and Path(self._camera_device).exists(),
            },
            "captureChain": self._describe_chain(),
        }

    async def snapshot(self) -> Optional[bytes]:
        """Capture a single JPEG frame using the best available method.

        Tries sources in priority order and returns raw JPEG bytes,
        or None if all sources fail.
        """
        # 1. go2rtc (fastest, ~10ms)
        if self._go2rtc_ok is not False:
            jpg = await self._snapshot_go2rtc()
            if jpg:
                self._go2rtc_ok = True
                return jpg
            self._go2rtc_ok = False
            logger.debug("go2rtc snapshot failed, trying direct capture")

        # 2. ffmpeg direct V4L2 (~300ms)
        if self._ffmpeg_path and self._camera_device:
            jpg = await self._snapshot_ffmpeg()
            if jpg:
                return jpg

        # 3. fswebcam (~500ms)
        if self._fswebcam_path and self._camera_device:
            jpg = await self._snapshot_fswebcam()
            if jpg:
                return jpg

        return None

    async def refresh_go2rtc_status(self) -> bool:
        """Re-test go2rtc availability (called periodically)."""
        self._go2rtc_ok = await self._test_go2rtc()
        return self._go2rtc_ok

    # ── Private capture methods ──────────────────────────────────

    async def _snapshot_go2rtc(self) -> Optional[bytes]:
        """Fetch JPEG from go2rtc's HTTP snapshot API."""
        url = f"{self._go2rtc_url}/api/frame.jpeg?src=printer_cam"
        try:
            client = self._client or httpx.AsyncClient(timeout=httpx.Timeout(5.0))
            resp = await client.get(url)
            if resp.status_code == 200 and len(resp.content) > 100:
                return resp.content
        except (httpx.ConnectError, httpx.ReadTimeout):
            pass
        except Exception:
            logger.debug("go2rtc snapshot error", exc_info=True)
        return None

    async def _snapshot_ffmpeg(self) -> Optional[bytes]:
        """Capture one JPEG frame directly from the V4L2 device via ffmpeg.

        Runs: ffmpeg -f v4l2 -i /dev/video0 -frames:v 1 -f image2pipe -vcodec mjpeg -
        Outputs raw JPEG to stdout.
        """
        cmd = [
            self._ffmpeg_path,
            "-f",
            "v4l2",
            "-input_format",
            "mjpeg",
            "-video_size",
            "1280x720",
            "-i",
            self._camera_device,
            "-frames:v",
            "1",
            "-f",
            "image2pipe",
            "-vcodec",
            "mjpeg",
            "-q:v",
            "5",
            "-",
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
            if proc.returncode == 0 and len(stdout) > 100:
                return stdout
        except asyncio.TimeoutError:
            logger.debug("ffmpeg snapshot timed out")
        except Exception:
            logger.debug("ffmpeg snapshot error", exc_info=True)
        return None

    async def _snapshot_fswebcam(self) -> Optional[bytes]:
        """Capture one JPEG frame using fswebcam (writes to stdout)."""
        cmd = [
            self._fswebcam_path,
            "--no-banner",
            "-r",
            "1280x720",
            "-d",
            self._camera_device,
            "--jpeg",
            "85",
            "-",  # output to stdout
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
            if proc.returncode == 0 and len(stdout) > 100:
                return stdout
        except asyncio.TimeoutError:
            logger.debug("fswebcam snapshot timed out")
        except Exception:
            logger.debug("fswebcam snapshot error", exc_info=True)
        return None

    async def _test_go2rtc(self) -> bool:
        """Quick connectivity check against go2rtc's API."""
        try:
            client = self._client or httpx.AsyncClient(timeout=httpx.Timeout(2.0))
            resp = await client.get(f"{self._go2rtc_url}/api/streams")
            return resp.status_code == 200
        except Exception:
            return False

    @staticmethod
    def _detect_camera_device() -> Optional[str]:
        """Find the first available V4L2 video device."""
        for dev in sorted(glob.glob("/dev/video*")):
            try:
                # Only consider actual capture devices (even-numbered on most systems)
                idx = int(dev.replace("/dev/video", ""))
                if idx % 2 == 0 and Path(dev).exists():
                    return dev
            except ValueError:
                continue
        return None

    def _describe_chain(self) -> list[str]:
        """Describe the active fallback chain for diagnostics."""
        chain = []
        if self._go2rtc_ok is not False:
            chain.append("go2rtc")
        if self._ffmpeg_path and self._camera_device:
            chain.append(f"ffmpeg:{self._camera_device}")
        if self._fswebcam_path and self._camera_device:
            chain.append(f"fswebcam:{self._camera_device}")
        return chain or ["none"]

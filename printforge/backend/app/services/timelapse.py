"""Timelapse capture and video assembly service.

Captures JPEG frames from the camera snapshot endpoint during a print,
either on every layer change or at a timed interval. When the print
finishes the frames are stitched into an MP4 video using ffmpeg.
"""

import asyncio
import logging
import shutil
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .camera import CameraService


class TimelapseRecorder:
    """Records timelapse frames and assembles them into video."""

    def __init__(self, camera_service: "CameraService", output_dir: Path):
        self._camera = camera_service
        self._output_dir = output_dir
        self._frames_dir: Optional[Path] = None
        self._recording = False
        self._frame_count = 0
        self._print_filename = ""
        self._start_time: Optional[float] = None
        self._timer_task: Optional[asyncio.Task] = None
        self._assembling = False
        self._last_video: Optional[str] = None

        # Configurable settings (loaded from DB at start)
        self._enabled = True
        self._capture_mode = "on_layer"  # "on_layer" or "timed"
        self._capture_interval = 10.0  # seconds between captures in timed mode
        self._render_fps = 30  # output video framerate

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def is_assembling(self) -> bool:
        return self._assembling

    @property
    def frame_count(self) -> int:
        return self._frame_count

    @property
    def print_filename(self) -> str:
        return self._print_filename

    @property
    def last_video(self) -> Optional[str]:
        return self._last_video

    def status_dict(self) -> dict:
        """Current status for API/WebSocket."""
        return {
            "recording": self._recording,
            "assembling": self._assembling,
            "frameCount": self._frame_count,
            "printFile": self._print_filename,
            "captureMode": self._capture_mode,
            "captureInterval": self._capture_interval,
            "renderFps": self._render_fps,
            "enabled": self._enabled,
            "lastVideo": self._last_video,
            "elapsed": time.time() - self._start_time if self._start_time else 0,
        }

    async def load_settings(self) -> None:
        """Load timelapse settings from the database."""
        from ..storage.models import get_setting

        self._enabled = await get_setting("timelapse_enabled", "true") == "true"
        self._capture_mode = await get_setting("timelapse_capture_mode", "on_layer")
        try:
            self._capture_interval = float(await get_setting("timelapse_interval", "10"))
        except ValueError:
            self._capture_interval = 10.0
        try:
            self._render_fps = int(await get_setting("timelapse_fps", "30"))
        except ValueError:
            self._render_fps = 30

    async def update_settings(
        self,
        enabled: Optional[bool] = None,
        capture_mode: Optional[str] = None,
        capture_interval: Optional[float] = None,
        render_fps: Optional[int] = None,
    ) -> dict:
        """Update and persist timelapse settings."""
        from ..storage.models import set_setting

        if enabled is not None:
            self._enabled = enabled
            await set_setting("timelapse_enabled", "true" if enabled else "false")
        if capture_mode is not None and capture_mode in ("on_layer", "timed"):
            self._capture_mode = capture_mode
            await set_setting("timelapse_capture_mode", capture_mode)
        if capture_interval is not None and capture_interval >= 1.0:
            self._capture_interval = capture_interval
            await set_setting("timelapse_interval", str(capture_interval))
        if render_fps is not None and 1 <= render_fps <= 60:
            self._render_fps = render_fps
            await set_setting("timelapse_fps", str(render_fps))

        return self.status_dict()

    async def start_recording(self, print_filename: str) -> bool:
        """Begin capturing frames for a print job.

        Returns True if recording started, False if disabled or already recording.
        """
        if self._recording:
            logger.warning("Already recording, ignoring start request")
            return False

        # Reload settings from DB so we pick up any changes made via the API
        await self.load_settings()

        if not self._enabled:
            logger.info("Timelapse disabled, skipping recording")
            return False

        # Create a unique frames directory
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        safe_name = print_filename.replace("/", "_").replace(" ", "_")
        safe_name = safe_name.rsplit(".", 1)[0]  # strip .gcode extension
        self._frames_dir = self._output_dir / "frames" / f"{safe_name}_{timestamp}"
        self._frames_dir.mkdir(parents=True, exist_ok=True)

        self._recording = True
        self._frame_count = 0
        self._print_filename = print_filename
        self._start_time = time.time()
        self._last_video = None

        # Start timed capture loop if in timed mode
        if self._capture_mode == "timed":
            self._timer_task = asyncio.create_task(self._timed_capture_loop())

        logger.info(
            "Timelapse recording started: %s (mode=%s)",
            print_filename,
            self._capture_mode,
        )
        return True

    async def capture_frame(self) -> bool:
        """Capture a single JPEG frame from the camera.

        Called externally on layer change, or internally by the timer loop.
        Returns True if a frame was captured.
        """
        if not self._recording or not self._frames_dir:
            return False

        snapshot = await self._fetch_snapshot()
        if not snapshot:
            return False

        frame_path = self._frames_dir / f"frame_{self._frame_count:06d}.jpg"
        try:
            # Write in a thread to avoid blocking the event loop on slow
            # SD cards (Raspberry Pi)
            await asyncio.to_thread(frame_path.write_bytes, snapshot)
            self._frame_count += 1
            if self._frame_count % 10 == 0:
                logger.debug("Timelapse frame %d captured", self._frame_count)
            return True
        except Exception:
            logger.exception("Failed to write timelapse frame")
            return False

    async def stop_recording(self, success: bool = True) -> Optional[str]:
        """Stop recording and assemble frames into a video.

        Args:
            success: True if print completed, False if cancelled/failed.

        Returns the output video filename, or None if assembly failed.
        """
        if not self._recording:
            return None

        self._recording = False

        # Stop timed capture
        if self._timer_task:
            self._timer_task.cancel()
            try:
                await self._timer_task
            except asyncio.CancelledError:
                pass
            self._timer_task = None

        if self._frame_count < 2:
            logger.warning("Timelapse has %d frame(s), skipping assembly", self._frame_count)
            await asyncio.to_thread(self._cleanup_frames)
            return None

        # Assemble video (or ZIP fallback if ffmpeg is missing)
        self._assembling = True
        try:
            if self._camera.has_ffmpeg:
                video_filename = await self._assemble_video(success)
                if video_filename:
                    self._last_video = video_filename
                    await self._generate_thumbnail(video_filename)
                    logger.info(
                        "Timelapse video created: %s (%d frames)",
                        video_filename,
                        self._frame_count,
                    )
                return video_filename
            else:
                # ffmpeg not installed — save frames as ZIP instead
                zip_filename = await asyncio.to_thread(self._save_frames_as_zip, success)
                if zip_filename:
                    self._last_video = zip_filename
                    logger.info(
                        "ffmpeg not found — saved %d frames as %s. "
                        "Install ffmpeg for video assembly.",
                        self._frame_count,
                        zip_filename,
                    )
                return zip_filename
        except Exception:
            logger.exception("Failed to assemble timelapse")
            return None
        finally:
            self._assembling = False
            await asyncio.to_thread(self._cleanup_frames)

    async def _fetch_snapshot(self) -> Optional[bytes]:
        """Capture a JPEG frame via the camera service fallback chain."""
        return await self._camera.snapshot()

    async def _timed_capture_loop(self) -> None:
        """Periodically capture frames at the configured interval."""
        try:
            while self._recording:
                await self.capture_frame()
                await asyncio.sleep(self._capture_interval)
        except asyncio.CancelledError:
            pass

    async def _assemble_video(self, success: bool) -> Optional[str]:
        """Use ffmpeg to stitch JPEG frames into an MP4 video.

        Runs ffmpeg in a subprocess to avoid blocking the event loop.
        """
        if not self._frames_dir:
            return None

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        safe_name = self._print_filename.replace("/", "_").replace(" ", "_")
        safe_name = safe_name.rsplit(".", 1)[0]
        suffix = "" if success else "-fail"
        video_name = f"{safe_name}_{timestamp}{suffix}.mp4"
        video_path = self._output_dir / video_name

        # Ensure output dir exists
        self._output_dir.mkdir(parents=True, exist_ok=True)

        # ffmpeg command: input numbered JPEGs, output H.264 MP4
        cmd = [
            "ffmpeg",
            "-y",  # overwrite
            "-framerate",
            str(self._render_fps),
            "-i",
            str(self._frames_dir / "frame_%06d.jpg"),
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(video_path),
        ]

        logger.info(
            "Assembling timelapse: %s (%d frames @ %dfps)",
            video_name,
            self._frame_count,
            self._render_fps,
        )

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)

            if proc.returncode != 0:
                logger.error(
                    "ffmpeg failed (exit %d): %s",
                    proc.returncode,
                    stderr.decode(errors="replace")[-500:],
                )
                return None

            return video_name
        except asyncio.TimeoutError:
            logger.error("ffmpeg timed out after 300s")
            return None
        except FileNotFoundError:
            logger.error("ffmpeg not found. Install ffmpeg to enable timelapse assembly.")
            return None

    async def _generate_thumbnail(self, video_filename: str) -> None:
        """Extract a thumbnail from the assembled video."""
        video_path = self._output_dir / video_filename
        thumb_path = self._output_dir / f"{video_filename}.thumb.jpg"

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-vf",
            "thumbnail,scale=320:-1",
            "-frames:v",
            "1",
            str(thumb_path),
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=30)
            if proc.returncode == 0:
                logger.info("Thumbnail generated: %s", thumb_path.name)
            else:
                logger.warning("Thumbnail generation failed for %s", video_filename)
        except (asyncio.TimeoutError, FileNotFoundError):
            logger.warning("Could not generate thumbnail (ffmpeg issue)")

    def _save_frames_as_zip(self, success: bool) -> Optional[str]:
        """Fallback: save captured frames as a ZIP archive when ffmpeg is missing."""
        if not self._frames_dir:
            return None

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        safe_name = self._print_filename.replace("/", "_").replace(" ", "_")
        safe_name = safe_name.rsplit(".", 1)[0]
        suffix = "" if success else "-fail"
        zip_name = f"{safe_name}_{timestamp}{suffix}_frames.zip"
        zip_path = self._output_dir / zip_name

        self._output_dir.mkdir(parents=True, exist_ok=True)

        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED) as zf:
                for frame_file in sorted(self._frames_dir.glob("frame_*.jpg")):
                    zf.write(frame_file, frame_file.name)
            logger.info("Saved %d frames to %s", self._frame_count, zip_name)
            return zip_name
        except Exception:
            logger.exception("Failed to create frames ZIP")
            return None

    def _cleanup_frames(self) -> None:
        """Remove the temporary frames directory."""
        if self._frames_dir and self._frames_dir.exists():
            try:
                shutil.rmtree(self._frames_dir)
                logger.debug("Cleaned up frames dir: %s", self._frames_dir)
            except Exception:
                logger.warning("Failed to clean up frames dir", exc_info=True)
        self._frames_dir = None

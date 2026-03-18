"""Timelapse video API endpoints.

Serves completed timelapse videos and provides recording control.
"""

import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..config import settings

router = APIRouter(prefix="/api/timelapse", tags=["timelapse"])

TIMELAPSE_DIR = Path(settings.data_dir).parent / "timelapse"

# Reference to the controller's timelapse recorder (set at startup)
_recorder = None


def set_recorder(recorder) -> None:
    global _recorder
    _recorder = recorder


def _ensure_dir() -> None:
    TIMELAPSE_DIR.mkdir(parents=True, exist_ok=True)


# ── Video file endpoints ─────────────────────────────────────────


@router.get("/")
async def list_timelapses():
    """List all timelapse videos with thumbnails."""
    _ensure_dir()
    videos = []
    for f in sorted(
        TIMELAPSE_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True
    ):
        if f.suffix.lower() in (".mp4", ".mkv", ".webm") and not f.name.endswith(
            ".thumb.jpg"
        ):
            stat = f.stat()
            thumb_path = TIMELAPSE_DIR / (f.name + ".thumb.jpg")
            videos.append(
                {
                    "filename": f.name,
                    "size": stat.st_size,
                    "date": stat.st_mtime,
                    "hasThumbnail": thumb_path.exists(),
                }
            )
    return {"timelapses": videos}


@router.get("/video/{filename}")
async def get_video(filename: str):
    """Stream a timelapse video file."""
    filepath = (TIMELAPSE_DIR / filename).resolve()
    if not str(filepath).startswith(str(TIMELAPSE_DIR.resolve())):
        raise HTTPException(400, "Invalid filename")
    if not filepath.exists():
        raise HTTPException(404, "Video not found")
    return FileResponse(filepath, media_type="video/mp4")


@router.get("/thumbnail/{filename}")
async def get_thumbnail(filename: str):
    """Get a timelapse thumbnail image."""
    thumb_name = (
        filename + ".thumb.jpg" if not filename.endswith(".thumb.jpg") else filename
    )
    filepath = (TIMELAPSE_DIR / thumb_name).resolve()
    if not str(filepath).startswith(str(TIMELAPSE_DIR.resolve())):
        raise HTTPException(400, "Invalid filename")
    if not filepath.exists():
        raise HTTPException(404, "Thumbnail not found")
    return FileResponse(filepath, media_type="image/jpeg")


@router.delete("/{filename}")
async def delete_timelapse(filename: str):
    """Delete a timelapse video and its thumbnail."""
    filepath = (TIMELAPSE_DIR / filename).resolve()
    if not str(filepath).startswith(str(TIMELAPSE_DIR.resolve())):
        raise HTTPException(400, "Invalid filename")
    if not filepath.exists():
        raise HTTPException(404, "Video not found")

    filepath.unlink()
    # Also remove thumbnail
    thumb = TIMELAPSE_DIR / (filename + ".thumb.jpg")
    if thumb.exists():
        thumb.unlink()

    return {"ok": True, "deleted": filename}


# ── Recording control endpoints ──────────────────────────────────


@router.get("/recording/status")
async def recording_status():
    """Get current timelapse recording status."""
    if not _recorder:
        return {
            "recording": False,
            "enabled": False,
            "error": "Recorder not initialized",
        }
    return _recorder.status_dict()


class TimelapseSettings(BaseModel):
    enabled: Optional[bool] = None
    captureMode: Optional[str] = None
    captureInterval: Optional[float] = None
    renderFps: Optional[int] = None


@router.put("/recording/settings")
async def update_recording_settings(body: TimelapseSettings):
    """Update timelapse capture settings."""
    if not _recorder:
        raise HTTPException(503, "Recorder not initialized")

    result = await _recorder.update_settings(
        enabled=body.enabled,
        capture_mode=body.captureMode,
        capture_interval=body.captureInterval,
        render_fps=body.renderFps,
    )
    return result


@router.post("/recording/test-capture")
async def test_capture():
    """Capture a single test frame (for verifying camera works)."""
    if not _recorder:
        raise HTTPException(503, "Recorder not initialized")

    snapshot = await _recorder._fetch_snapshot()
    if snapshot:
        return {"ok": True, "size": len(snapshot)}
    raise HTTPException(503, "Could not capture frame from camera")

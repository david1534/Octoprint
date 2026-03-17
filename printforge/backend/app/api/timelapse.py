"""Timelapse video API endpoints."""

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from ..config import settings

router = APIRouter(prefix="/api/timelapse", tags=["timelapse"])

TIMELAPSE_DIR = Path(settings.data_dir).parent / "timelapse"


def _ensure_dir() -> None:
    TIMELAPSE_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/")
async def list_timelapses():
    """List all timelapse videos with thumbnails."""
    _ensure_dir()
    videos = []
    for f in sorted(TIMELAPSE_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if f.suffix.lower() in (".mp4", ".mkv", ".webm") and not f.name.endswith(".thumb.jpg"):
            stat = f.stat()
            thumb_path = TIMELAPSE_DIR / (f.name + ".thumb.jpg")
            videos.append({
                "filename": f.name,
                "size": stat.st_size,
                "date": stat.st_mtime,
                "hasThumbnail": thumb_path.exists(),
            })
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
    thumb_name = filename + ".thumb.jpg" if not filename.endswith(".thumb.jpg") else filename
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

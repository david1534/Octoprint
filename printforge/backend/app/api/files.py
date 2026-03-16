"""File management REST API endpoints."""

import os
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile

from ..printer.gcode_parser import parse_gcode_file

router = APIRouter(prefix="/api/files", tags=["files"])

GCODE_DIR = Path("/home/pi/printforge/gcodes")


def _ensure_gcode_dir() -> None:
    GCODE_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/")
async def list_files():
    """List all uploaded G-code files with metadata."""
    _ensure_gcode_dir()
    files = []
    for filepath in sorted(GCODE_DIR.glob("*.gcode")):
        try:
            metadata = parse_gcode_file(filepath)
            files.append(metadata.to_dict())
        except Exception:
            # If parsing fails, return basic info
            files.append({
                "filename": filepath.name,
                "fileSize": filepath.stat().st_size,
                "totalLines": 0,
                "printableLines": 0,
            })
    # Also check for .g and .gc extensions
    for ext in ("*.g", "*.gc"):
        for filepath in sorted(GCODE_DIR.glob(ext)):
            try:
                metadata = parse_gcode_file(filepath)
                files.append(metadata.to_dict())
            except Exception:
                files.append({
                    "filename": filepath.name,
                    "fileSize": filepath.stat().st_size,
                })
    return {"files": files}


@router.post("/upload")
async def upload_file(file: UploadFile):
    """Upload a G-code file."""
    _ensure_gcode_dir()

    if not file.filename:
        raise HTTPException(400, "No filename provided")

    # Validate extension
    allowed_extensions = {".gcode", ".g", ".gc"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_extensions:
        raise HTTPException(
            400, f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
        )

    # Sanitize filename
    safe_name = "".join(
        c for c in file.filename if c.isalnum() or c in "._- "
    ).strip()
    if not safe_name:
        raise HTTPException(400, "Invalid filename")

    filepath = GCODE_DIR / safe_name

    # Write file
    with open(filepath, "wb") as f:
        while chunk := await file.read(1024 * 64):  # 64KB chunks
            f.write(chunk)

    # Parse metadata
    try:
        metadata = parse_gcode_file(filepath)
        return {"ok": True, "file": metadata.to_dict()}
    except Exception:
        return {
            "ok": True,
            "file": {
                "filename": safe_name,
                "fileSize": filepath.stat().st_size,
            },
        }


@router.delete("/{filename}")
async def delete_file(filename: str):
    """Delete a G-code file."""
    filepath = GCODE_DIR / filename
    if not filepath.exists():
        raise HTTPException(404, f"File not found: {filename}")

    # Prevent path traversal
    if filepath.resolve().parent != GCODE_DIR.resolve():
        raise HTTPException(400, "Invalid filename")

    filepath.unlink()
    return {"ok": True, "deleted": filename}


@router.get("/{filename}/metadata")
async def get_file_metadata(filename: str):
    """Get detailed metadata for a G-code file."""
    filepath = GCODE_DIR / filename
    if not filepath.exists():
        raise HTTPException(404, f"File not found: {filename}")

    metadata = parse_gcode_file(filepath)
    return metadata.to_dict()


@router.get("/disk-usage")
async def disk_usage():
    """Get disk usage info for the G-code storage directory."""
    _ensure_gcode_dir()
    total_size = sum(
        f.stat().st_size for f in GCODE_DIR.iterdir() if f.is_file()
    )
    disk = shutil.disk_usage(GCODE_DIR)
    return {
        "gcodeBytes": total_size,
        "diskTotal": disk.total,
        "diskUsed": disk.used,
        "diskFree": disk.free,
    }

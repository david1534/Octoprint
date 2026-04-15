"""File management REST API endpoints with folder support."""

import re
import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, Query

from ..config import settings
from ..printer.gcode_parser import calculate_filament_cost, parse_gcode_file
from ..storage.models import get_setting

router = APIRouter(prefix="/api/files", tags=["files"])

GCODE_DIR = Path(settings.gcode_dir)
ALLOWED_EXTENSIONS = {".gcode", ".g", ".gc"}


def _ensure_gcode_dir() -> None:
    GCODE_DIR.mkdir(parents=True, exist_ok=True)


def _safe_resolve(subpath: str) -> Path:
    """Resolve a subpath within GCODE_DIR, preventing path traversal."""
    resolved = (GCODE_DIR / subpath).resolve()
    if not str(resolved).startswith(str(GCODE_DIR.resolve())):
        raise HTTPException(400, "Invalid path")
    return resolved


async def _file_info(filepath: Path) -> dict:
    """Get file info dict for a gcode file."""
    try:
        metadata = parse_gcode_file(filepath)
        info = metadata.to_dict()
        info["path"] = str(filepath.relative_to(GCODE_DIR)).replace("\\", "/")
        # Calculate cost if filament data available
        if metadata.filament_used_mm:
            cost_per_kg = float(await get_setting("filament_cost_per_kg", "18"))
            density = float(await get_setting("filament_density", "1.24"))
            info["estimatedCost"] = calculate_filament_cost(
                metadata.filament_used_mm, cost_per_kg, density
            )
        return info
    except Exception:
        return {
            "filename": filepath.name,
            "fileSize": filepath.stat().st_size,
            "totalLines": 0,
            "printableLines": 0,
            "path": str(filepath.relative_to(GCODE_DIR)).replace("\\", "/"),
        }


@router.get("/")
async def list_files(path: str = Query("", description="Subfolder path to list")):
    """List files and folders in a directory."""
    _ensure_gcode_dir()

    target_dir = _safe_resolve(path) if path else GCODE_DIR
    if not target_dir.exists() or not target_dir.is_dir():
        raise HTTPException(404, f"Directory not found: {path}")

    folders = []
    files = []

    for entry in sorted(target_dir.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
        if entry.name.startswith("."):
            continue

        if entry.is_dir():
            # Count files in subfolder recursively
            gcode_count = sum(
                1 for _ in entry.rglob("*")
                if _.is_file() and _.suffix.lower() in ALLOWED_EXTENSIONS
            )
            folders.append({
                "name": entry.name,
                "path": str(entry.relative_to(GCODE_DIR)).replace("\\", "/"),
                "fileCount": gcode_count,
            })
        elif entry.suffix.lower() in ALLOWED_EXTENSIONS:
            files.append(await _file_info(entry))

    return {
        "currentPath": path,
        "parentPath": str(Path(path).parent).replace("\\", "/") if path else None,
        "folders": folders,
        "files": files,
    }


@router.post("/folder")
async def create_folder(path: str = Query(..., description="Folder path to create")):
    """Create a new folder."""
    _ensure_gcode_dir()
    target = _safe_resolve(path)
    if target.exists():
        raise HTTPException(409, f"Folder already exists: {path}")
    target.mkdir(parents=True, exist_ok=True)
    return {"ok": True, "path": path}


@router.delete("/folder")
async def delete_folder(
    path: str = Query(..., description="Folder path to delete"),
    force: bool = Query(False, description="Recursively delete non-empty folder"),
):
    """Delete a folder. Use force=true to delete non-empty folders."""
    _ensure_gcode_dir()
    target = _safe_resolve(path)
    if not target.exists() or not target.is_dir():
        raise HTTPException(404, f"Folder not found: {path}")
    if target == GCODE_DIR.resolve():
        raise HTTPException(400, "Cannot delete root folder")
    if not force:
        contents = [f for f in target.iterdir() if f.name != ".metadata.json"]
        if contents:
            raise HTTPException(400, "Folder is not empty. Use force=true to delete recursively.")
    shutil.rmtree(target)
    return {"ok": True, "deleted": path}


@router.post("/upload")
async def upload_file(
    file: UploadFile,
    path: str = Query("", description="Subfolder to upload into"),
):
    """Upload a G-code file, optionally into a subfolder."""
    _ensure_gcode_dir()

    if not file.filename:
        raise HTTPException(400, "No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            400, f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Sanitize filename
    safe_name = "".join(
        c for c in file.filename if c.isalnum() or c in "._- ()"
    ).strip()
    if not safe_name:
        raise HTTPException(400, "Invalid filename")

    target_dir = _safe_resolve(path) if path else GCODE_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    filepath = target_dir / safe_name

    import aiofiles

    async with aiofiles.open(filepath, "wb") as f:
        while chunk := await file.read(1024 * 64):
            await f.write(chunk)

    try:
        metadata = parse_gcode_file(filepath)
        result = metadata.to_dict()
        result["path"] = str(filepath.relative_to(GCODE_DIR)).replace("\\", "/")
        return {"ok": True, "file": result}
    except Exception:
        return {
            "ok": True,
            "file": {
                "filename": safe_name,
                "fileSize": filepath.stat().st_size,
                "path": str(filepath.relative_to(GCODE_DIR)).replace("\\", "/"),
            },
        }


@router.post("/move")
async def move_file(
    src: str = Query(..., description="Source file path"),
    dest: str = Query(..., description="Destination folder path"),
):
    """Move a file to a different folder."""
    _ensure_gcode_dir()
    src_path = _safe_resolve(src)
    if not src_path.exists() or not src_path.is_file():
        raise HTTPException(404, f"File not found: {src}")

    dest_dir = _safe_resolve(dest) if dest else GCODE_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / src_path.name

    if dest_path.exists():
        raise HTTPException(409, f"File already exists at destination: {dest_path.name}")

    shutil.move(str(src_path), str(dest_path))
    return {
        "ok": True,
        "path": str(dest_path.relative_to(GCODE_DIR)).replace("\\", "/"),
    }


@router.post("/move-folder")
async def move_folder(
    src: str = Query(..., description="Source folder path"),
    dest: str = Query("", description="Destination folder path (empty = root)"),
):
    """Move a folder into another folder."""
    _ensure_gcode_dir()
    src_path = _safe_resolve(src)
    if not src_path.exists() or not src_path.is_dir():
        raise HTTPException(404, f"Folder not found: {src}")

    dest_dir = _safe_resolve(dest) if dest else GCODE_DIR
    if not dest_dir.exists() or not dest_dir.is_dir():
        raise HTTPException(404, f"Destination not found: {dest}")

    # Prevent moving a folder into itself or any of its descendants
    src_resolved = src_path.resolve()
    dest_resolved = dest_dir.resolve()
    if dest_resolved == src_resolved or str(dest_resolved).startswith(str(src_resolved) + "/"):
        raise HTTPException(400, "Cannot move a folder into itself or its subdirectory")

    dest_path = dest_dir / src_path.name
    if dest_path.exists():
        raise HTTPException(409, f"A folder named '{src_path.name}' already exists at the destination")

    shutil.move(str(src_path), str(dest_path))
    return {
        "ok": True,
        "path": str(dest_path.relative_to(GCODE_DIR)).replace("\\", "/"),
    }


@router.get("/all-folders")
async def list_all_folders():
    """List all folders recursively (for move/pick dialogs)."""
    _ensure_gcode_dir()
    result = []

    def _collect(dir_path: Path) -> None:
        for entry in sorted(dir_path.iterdir(), key=lambda e: e.name.lower()):
            if entry.is_dir() and not entry.name.startswith("."):
                rel = str(entry.relative_to(GCODE_DIR)).replace("\\", "/")
                result.append({
                    "name": entry.name,
                    "path": rel,
                    "depth": rel.count("/"),
                })
                _collect(entry)

    _collect(GCODE_DIR)
    return {"folders": result}


@router.post("/rename")
async def rename_file(
    src: str = Query(..., description="Source file path"),
    name: str = Query(..., description="New filename"),
):
    """Rename a file (keeps it in the same folder)."""
    _ensure_gcode_dir()
    src_path = _safe_resolve(src)
    if not src_path.exists() or not src_path.is_file():
        raise HTTPException(404, f"File not found: {src}")

    safe_name = re.sub(r"[^\w.\-() ]", "_", name.strip())
    if not safe_name:
        raise HTTPException(400, "Invalid filename")
    # Ensure gcode extension
    if not any(safe_name.lower().endswith(ext) for ext in ALLOWED_EXTENSIONS):
        safe_name += src_path.suffix

    dest_path = src_path.parent / safe_name
    if dest_path.exists() and dest_path != src_path:
        raise HTTPException(409, f"File already exists: {safe_name}")

    src_path.rename(dest_path)
    return {
        "ok": True,
        "path": str(dest_path.relative_to(GCODE_DIR)).replace("\\", "/"),
        "filename": safe_name,
    }


@router.post("/rename-folder")
async def rename_folder(
    src: str = Query(..., description="Source folder path"),
    name: str = Query(..., description="New folder name"),
):
    """Rename a folder."""
    _ensure_gcode_dir()
    src_path = _safe_resolve(src)
    if not src_path.exists() or not src_path.is_dir():
        raise HTTPException(404, f"Folder not found: {src}")

    safe_name = re.sub(r"[^\w.\-() ]", "_", name.strip())
    if not safe_name:
        raise HTTPException(400, "Invalid folder name")

    dest_path = src_path.parent / safe_name
    if dest_path.exists() and dest_path != src_path:
        raise HTTPException(409, f"Folder already exists: {safe_name}")

    src_path.rename(dest_path)
    return {
        "ok": True,
        "path": str(dest_path.relative_to(GCODE_DIR)).replace("\\", "/"),
        "name": safe_name,
    }


@router.delete("/{filename:path}")
async def delete_file(filename: str):
    """Delete a G-code file by its path."""
    filepath = _safe_resolve(filename)
    if not filepath.exists() or not filepath.is_file():
        raise HTTPException(404, f"File not found: {filename}")

    filepath.unlink()
    return {"ok": True, "deleted": filename}


@router.get("/{filename:path}/metadata")
async def get_file_metadata(filename: str):
    """Get detailed metadata for a G-code file."""
    filepath = _safe_resolve(filename)
    if not filepath.exists() or not filepath.is_file():
        raise HTTPException(404, f"File not found: {filename}")

    metadata = parse_gcode_file(filepath)
    result = metadata.to_dict()
    result["path"] = filename
    if metadata.filament_used_mm:
        cost_per_kg = float(await get_setting("filament_cost_per_kg", "18"))
        density = float(await get_setting("filament_density", "1.24"))
        result["estimatedCost"] = calculate_filament_cost(
            metadata.filament_used_mm, cost_per_kg, density
        )
    return result


@router.get("/disk-usage")
async def disk_usage():
    """Get disk usage info for the G-code storage directory."""
    _ensure_gcode_dir()
    total_size = sum(
        f.stat().st_size
        for f in GCODE_DIR.rglob("*")
        if f.is_file() and f.suffix.lower() in ALLOWED_EXTENSIONS
    )
    disk = shutil.disk_usage(GCODE_DIR)
    return {
        "gcodeBytes": total_size,
        "diskTotal": disk.total,
        "diskUsed": disk.used,
        "diskFree": disk.free,
    }

"""G-code file storage management."""

from pathlib import Path

GCODE_DIR = Path("/home/pi/printforge/gcodes")


def ensure_gcode_dir() -> None:
    """Create the G-code storage directory if it doesn't exist."""
    GCODE_DIR.mkdir(parents=True, exist_ok=True)


def get_gcode_path(filename: str) -> Path:
    """Get the full path for a G-code file, with path traversal protection."""
    safe_path = (GCODE_DIR / filename).resolve()
    if not str(safe_path).startswith(str(GCODE_DIR.resolve())):
        raise ValueError("Invalid filename: path traversal detected")
    return safe_path


def list_gcode_files() -> list[Path]:
    """List all G-code files in the storage directory."""
    ensure_gcode_dir()
    extensions = ("*.gcode", "*.g", "*.gc")
    files = []
    for ext in extensions:
        files.extend(GCODE_DIR.glob(ext))
    return sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)

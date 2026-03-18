"""
Auto-Slice & Upload: Watches for new STL files, slices with CuraEngine,
and uploads G-code to PrintForge automatically.

Usage:
    python auto_slice.py              # Start background watcher
    python auto_slice.py --once       # Process unsliced STLs and exit
    python auto_slice.py --help       # Show all options
"""

import argparse
import logging
import sys
import time
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent

from slicer import slice as slice_stl
from uploader import upload
from notifier import pick_profile, show_toast

# Set up logging
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
LOG_DATE = "%Y-%m-%d %H:%M:%S"


def load_config() -> dict:
    config_path = Path(__file__).parent / "config.toml"
    with open(config_path, "rb") as f:
        return tomllib.load(f)


def find_unsliced_stls(watch_dir: Path) -> list[Path]:
    """Find all STL files that don't have a corresponding gcode file."""
    unsliced = []
    for stl in watch_dir.rglob("*.stl"):
        # Check if ANY gcode file exists with matching stem
        gcodes = list(stl.parent.glob(f"{stl.stem}*.gcode"))
        if not gcodes:
            unsliced.append(stl)
    return sorted(unsliced)


def process_stl(stl_path: Path, config: dict, profile_override: str | None = None) -> bool:
    """
    Process a single STL file: pick profile, slice, upload.

    Returns True if successfully sliced and uploaded.
    """
    logger = logging.getLogger("auto_slice")
    stl_path = Path(stl_path).resolve()

    logger.info(f"Processing: {stl_path.name}")

    # Determine profile
    if profile_override:
        profile = profile_override
        logger.info(f"  Using profile override: {profile}")
    else:
        default_profile = config.get("slicing", {}).get("default_profile", "functional")
        profile = pick_profile(
            filename=stl_path.name,
            default=default_profile,
            timeout_seconds=60,
        )
        if profile is None:
            logger.info(f"  Skipped by user")
            return False

    logger.info(f"  Profile: {profile}")

    # Slice
    result = slice_stl(
        stl_path=stl_path,
        profile_name=profile,
        config=config,
    )

    if not result.success:
        logger.error(f"  Slicing failed: {result.error}")
        show_toast("Slicing Failed", f"{stl_path.name}\n{result.error}")
        return False

    logger.info(f"  Sliced in {result.duration_seconds:.1f}s -> {result.output_path.name}")

    # Upload to PrintForge
    try:
        # Use the parent folder name as the subfolder in PrintForge
        watch_dir = Path(config["paths"]["watch_dir"]).resolve()
        relative = stl_path.parent.relative_to(watch_dir)
        subfolder = str(relative) if str(relative) != "." else ""

        upload_result = upload(
            gcode_path=result.output_path,
            subfolder=subfolder,
            url=config["printforge"]["url"],
            api_key=config["printforge"].get("api_key", ""),
        )
        logger.info(f"  Uploaded to PrintForge: {subfolder}/{result.output_path.name}")
        show_toast(
            "Sliced & Uploaded",
            f"{result.output_path.name}\nProfile: {profile}\nTime: {result.duration_seconds:.0f}s",
        )

        # Optionally remove local gcode after upload
        keep_local = config.get("slicing", {}).get("keep_local_gcode", True)
        if not keep_local and result.output_path.exists():
            result.output_path.unlink()
            logger.info(f"  Removed local gcode (keep_local_gcode=false)")

        return True

    except Exception as e:
        logger.error(f"  Upload failed: {e}")
        show_toast("Upload Failed", f"{stl_path.name}\n{e}")
        return False


class STLHandler(FileSystemEventHandler):
    """Watches for new/modified STL files and triggers processing."""

    def __init__(self, config: dict):
        self.config = config
        self.logger = logging.getLogger("auto_slice")
        self._debounce: dict[str, float] = {}
        self._debounce_seconds = config.get("watcher", {}).get("debounce_seconds", 3)

    def on_created(self, event):
        if not event.is_directory and event.src_path.lower().endswith(".stl"):
            self._handle(event.src_path)

    def on_modified(self, event):
        if not event.is_directory and event.src_path.lower().endswith(".stl"):
            self._handle(event.src_path)

    def _handle(self, filepath: str):
        path = Path(filepath).resolve()
        now = time.time()

        # Debounce: ignore duplicate events within the debounce window
        last_seen = self._debounce.get(str(path), 0)
        if now - last_seen < self._debounce_seconds * 2:
            return
        self._debounce[str(path)] = now

        # Check if gcode already exists and is newer
        existing = list(path.parent.glob(f"{path.stem}*.gcode"))
        if existing:
            newest_gcode = max(existing, key=lambda p: p.stat().st_mtime)
            if newest_gcode.stat().st_mtime > path.stat().st_mtime:
                self.logger.debug(f"Skipping {path.name}: newer gcode exists")
                return

        # Wait for file write to complete (OneDrive sync buffer)
        self.logger.info(f"New STL detected: {path.name}")
        self.logger.info(f"  Waiting {self._debounce_seconds}s for file sync...")
        time.sleep(self._debounce_seconds)

        # Verify file is readable and has content
        try:
            size = path.stat().st_size
            if size < 100:
                self.logger.warning(f"  File too small ({size} bytes), skipping")
                return
        except OSError:
            return

        process_stl(path, self.config)


def run_watcher(config: dict) -> None:
    """Start the file system watcher (runs until interrupted)."""
    logger = logging.getLogger("auto_slice")
    watch_dir = config["paths"]["watch_dir"]

    logger.info(f"Watching: {watch_dir}")
    logger.info(f"PrintForge: {config['printforge']['url']}")
    logger.info(f"Default profile: {config.get('slicing', {}).get('default_profile', 'functional')}")
    logger.info("Press Ctrl+C to stop.\n")

    handler = STLHandler(config)
    observer = Observer()
    observer.schedule(handler, watch_dir, recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("\nStopping watcher...")
        observer.stop()
    observer.join()
    logger.info("Stopped.")


def run_once(config: dict, profile: str | None = None) -> None:
    """Scan for unsliced STLs, process each, then exit."""
    logger = logging.getLogger("auto_slice")
    watch_dir = Path(config["paths"]["watch_dir"])

    logger.info(f"Scanning: {watch_dir}")
    unsliced = find_unsliced_stls(watch_dir)

    if not unsliced:
        logger.info("No unsliced STL files found. Everything is up to date!")
        return

    logger.info(f"Found {len(unsliced)} unsliced STL(s):")
    for stl in unsliced:
        logger.info(f"  - {stl.relative_to(watch_dir)}")

    success = 0
    for stl in unsliced:
        if process_stl(stl, config, profile_override=profile):
            success += 1

    logger.info(f"\nProcessed {success}/{len(unsliced)} files successfully.")


def main():
    parser = argparse.ArgumentParser(
        description="Auto-Slice: Watch for STL files, slice with CuraEngine, upload to PrintForge",
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Process all unsliced STLs and exit (don't watch)",
    )
    parser.add_argument(
        "--profile", "-p",
        help="Force a specific profile (skip the picker dialog)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    # Configure logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format=LOG_FORMAT, datefmt=LOG_DATE)

    # Also log to file
    tools_dir = Path(__file__).parent
    file_handler = logging.FileHandler(tools_dir / "auto_slice.log", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE))
    logging.getLogger("auto_slice").addHandler(file_handler)

    config = load_config()

    if args.once:
        run_once(config, profile=args.profile)
    else:
        run_watcher(config)


if __name__ == "__main__":
    main()

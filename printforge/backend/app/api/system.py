"""System information REST API endpoints."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import os
import platform
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import APIRouter, FastAPI, HTTPException, Request

from ..config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/system", tags=["system"])
host_router = APIRouter(prefix="/api/system", tags=["system"])

_start_time = time.time()

SAFE_HOST_STATES = frozenset({"idle", "disconnected"})
COMMAND_TIMEOUT_SECONDS = 30.0
PRODUCTION_ROOT = Path("/opt/printforge")
STAGING_ROOT = Path("/opt/printforge-staging")
RELEASES_ROOT = PRODUCTION_ROOT / "releases"
CURRENT_LINK = PRODUCTION_ROOT / "current"
PREVIOUS_LINK = PRODUCTION_ROOT / "previous"


def _compute_build_version() -> str:
    """Content-hash of the deployed backend + frontend build.

    Used by the UI to know whether staging's code differs from production's.
    Hashed once at import; the service restarts on every deploy/promote, so
    the value is always current. 12 hex chars is plenty for spotting a
    difference between two environments on the same host.

    Includes:
    - all .py files under the app/ directory (content-hashed)
    - the sorted list of relative paths under frontend/build/ (SvelteKit uses
      content-hashed filenames, so the filename set is itself a content hash —
      far cheaper than reading every JS chunk)
    """
    h = hashlib.sha256()
    app_dir = Path(__file__).parent.parent  # .../app

    for p in sorted(app_dir.rglob("*.py")):
        try:
            rel = p.relative_to(app_dir).as_posix()
            h.update(rel.encode() + b"\n")
            h.update(p.read_bytes())
            h.update(b"\n")
        except Exception:
            pass

    # Frontend build lives alongside app/ in deployed layouts (/opt/printforge/)
    # but may be missing in dev — skip silently if so.
    frontend_build = app_dir.parent / "frontend" / "build"
    if frontend_build.is_dir():
        for p in sorted(frontend_build.rglob("*")):
            if p.is_file():
                try:
                    rel = p.relative_to(frontend_build).as_posix()
                    h.update(rel.encode() + b"\n")
                except Exception:
                    pass
    return h.hexdigest()[:12]


_build_version = _compute_build_version()


def _read_pi_cpu_temp() -> float:
    """Read Raspberry Pi CPU temperature."""
    try:
        temp_file = Path("/sys/class/thermal/thermal_zone0/temp")
        if temp_file.exists():
            return int(temp_file.read_text().strip()) / 1000.0
    except Exception:
        pass
    return 0.0


def _read_memory_info() -> dict:
    """Read memory usage from /proc/meminfo."""
    info = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split()
                if parts[0] == "MemTotal:":
                    info["total"] = int(parts[1]) * 1024  # KB to bytes
                elif parts[0] == "MemAvailable:":
                    info["available"] = int(parts[1]) * 1024
        if "total" in info and "available" in info:
            info["used"] = info["total"] - info["available"]
            info["percent"] = round(info["used"] / info["total"] * 100, 1)
    except Exception:
        info = {"total": 0, "available": 0, "used": 0, "percent": 0}
    return info


def _read_cpu_usage() -> float:
    """Get a rough CPU usage estimate from /proc/loadavg."""
    try:
        with open("/proc/loadavg") as f:
            load1 = float(f.read().split()[0])
            # Normalize by CPU count
            cpu_count = os.cpu_count() or 1
            return round(min(100, load1 / cpu_count * 100), 1)
    except Exception:
        return 0.0


@router.get("/health")
async def health():
    """System health check.

    Public (no API key required). Includes printerStatus so the staging
    instance can check whether production is mid-print before promoting,
    without needing production's API key.
    """
    # Read printer status from the controller singleton. Kept defensive
    # because health is called during startup before the controller wires
    # everything up.
    printer_status = "unknown"
    try:
        from ..api import printer as printer_api

        ctrl = getattr(printer_api, "_controller", None)
        if ctrl is not None:
            printer_status = ctrl.state.status.value
    except Exception:
        pass

    return {
        "status": "ok",
        "uptime": round(time.time() - _start_time),
        "cpuTemp": _read_pi_cpu_temp(),
        "cpuUsage": _read_cpu_usage(),
        "memory": _read_memory_info(),
        "platform": platform.machine(),
        "python": platform.python_version(),
        "environment": settings.environment,
        "mockSerial": settings.mock_serial,
        "printerStatus": printer_status,
        "version": _build_version,
    }


@router.get("/camera-health")
async def camera_health():
    """Camera system health check.

    Reports ustreamer status, ffmpeg availability, camera device detection,
    and the active capture fallback chain.
    """

    # Get the controller from the printer API module (same singleton)
    from ..api import printer as printer_api

    ctrl = getattr(printer_api, "_controller", None)
    if ctrl and ctrl.camera:
        health = ctrl.camera.health_dict()
        # Also refresh ustreamer status
        await ctrl.camera.refresh_ustreamer_status()
        health["ustreamer"]["available"] = ctrl.camera.ustreamer_available
        return health
    return {
        "ustreamer": {"available": False, "url": ""},
        "ffmpeg": {"available": False, "path": None},
        "fswebcam": {"available": False},
        "device": {"path": None, "exists": False},
        "captureChain": ["none"],
        "error": "Camera service not initialized",
    }


@router.get("/serial-ports")
async def list_serial_ports():
    """List available serial ports."""
    ports = []
    # Check common Raspberry Pi serial port paths
    dev_path = Path("/dev")
    patterns = ["ttyUSB*", "ttyACM*", "ttyAMA*"]
    for pattern in patterns:
        for port in dev_path.glob(pattern):
            ports.append(str(port))

    # Also check for our udev symlink
    printforge_dev = Path("/dev/printforge")
    if printforge_dev.exists():
        ports.insert(0, str(printforge_dev))

    return {"ports": ports}


@router.get("/disk-usage")
async def disk_usage():
    """Get disk usage for the G-code storage partition."""
    path = settings.gcode_dir
    try:
        usage = shutil.disk_usage(path)
        return {"total": usage.total, "used": usage.used, "free": usage.free}
    except Exception:
        return {"total": 0, "used": 0, "free": 0}


def register_routers(app: FastAPI, environment: str, mock_serial: bool) -> None:
    """Register host controls only on the real production process."""
    app.include_router(router)
    if environment == "production" and not mock_serial:
        app.include_router(host_router)


@host_router.post("/restart-service")
async def restart_service():
    """Restart the PrintForge service (blocked during active prints)."""
    # Restarting tears down the serial connection and the print task, aborting
    # the job — same hazard the OS restart/shutdown endpoints already guard.
    _reject_if_printing()
    try:
        subprocess.Popen(
            ["sudo", "systemctl", "restart", "printforge"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return {"status": "restarting"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


def _require_safe_production_state() -> str:
    """Return an exact safe state or reject the host operation fail closed."""
    from ..api import printer as printer_api

    ctrl = getattr(printer_api, "_controller", None)
    if ctrl is None:
        raise HTTPException(
            503,
            "Cannot verify the production printer state. Host operation refused.",
        )

    try:
        raw_status = ctrl.state.status
        status = raw_status.value if hasattr(raw_status, "value") else raw_status
    except Exception as exc:
        raise HTTPException(
            503,
            "Cannot verify the production printer state. Host operation refused.",
        ) from exc

    if not isinstance(status, str) or status not in SAFE_HOST_STATES:
        raise HTTPException(
            409,
            f"Cannot perform this action while printer state is {status!r}. "
            f"Expected one of: {', '.join(sorted(SAFE_HOST_STATES))}.",
        )
    return status


def _reject_if_printing() -> None:
    """Backward-compatible wrapper for existing host-control call sites."""
    _require_safe_production_state()


@host_router.post("/restart-os")
async def restart_os():
    """Restart the operating system (blocked during active prints)."""
    _reject_if_printing()
    try:
        subprocess.Popen(
            ["sudo", "shutdown", "-r", "now"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return {"status": "restarting"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@host_router.post("/shutdown-os")
async def shutdown_os():
    """Shut down the operating system (blocked during active prints)."""
    _reject_if_printing()
    try:
        subprocess.Popen(
            ["sudo", "shutdown", "-h", "now"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return {"status": "shutting_down"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


async def _run(cmd: list[str], timeout: float = COMMAND_TIMEOUT_SECONDS) -> tuple[int, str]:
    """Run a subprocess with a hard timeout and collect combined output."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=2.0)
        except TimeoutError:
            proc.kill()
            await proc.wait()
        return 124, f"Command timed out after {timeout:g}s: {cmd[0]}"
    return proc.returncode or 0, out.decode("utf-8", errors="replace").strip()


@router.get("/peer-version")
async def peer_version():
    """Return the build version of the OTHER environment on this host.

    Only meaningful on staging — used by the UI to decide whether there's
    anything to promote. Fetched via 127.0.0.1 so we don't need to deal
    with the user's CORS config or production's API-key auth.
    """
    if settings.environment != "staging":
        # On production, there's no "peer" concept — just return our own.
        return {"peerEnvironment": "production", "version": None, "reachable": False}

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get("http://127.0.0.1:8000/api/system/health")
            if r.status_code == 200:
                data = r.json()
                return {
                    "peerEnvironment": "production",
                    "version": data.get("version"),
                    "reachable": True,
                }
            return {"peerEnvironment": "production", "version": None, "reachable": False}
    except Exception:
        return {"peerEnvironment": "production", "version": None, "reachable": False}


def _require_promotion_token(request: Request) -> None:
    """Require the deployment-only credential in addition to normal API auth."""
    expected = settings.promotion_token.strip()
    if not expected:
        raise HTTPException(
            503,
            "Promotion is disabled because PRINTFORGE_PROMOTION_TOKEN is not configured.",
        )

    provided = request.headers.get("x-printforge-promotion-token", "")
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(403, "Invalid or missing promotion token.")


def _release_target(link: Path) -> Path | None:
    """Resolve a release link only when it remains inside RELEASES_ROOT."""
    if not link.is_symlink():
        return None
    try:
        target = link.resolve(strict=True)
        target.relative_to(RELEASES_ROOT.resolve())
    except (OSError, ValueError):
        return None
    return target


def _atomic_release_link(target: Path, link: Path) -> None:
    """Atomically replace a release symlink without exposing a missing link."""
    target = target.resolve(strict=True)
    target.relative_to(RELEASES_ROOT.resolve())
    temporary = link.with_name(f".{link.name}-{os.getpid()}-{time.time_ns()}")
    temporary.symlink_to(target, target_is_directory=True)
    try:
        os.replace(temporary, link)
    finally:
        temporary.unlink(missing_ok=True)


async def _copy_tree(source: Path, destination: Path, label: str, log: list[str]) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    rc, out = await _run(["rsync", "-a", "--delete", f"{source}/", f"{destination}/"])
    log.append(f"rsync {label} rc={rc}")
    if out:
        log.append(out)
    if rc != 0:
        raise HTTPException(500, "\n".join(log))


async def _stage_release(log: list[str]) -> Path:
    """Build an immutable, complete release without touching the live release."""
    staging_app = STAGING_ROOT / "app"
    staging_frontend = STAGING_ROOT / "frontend" / "build"
    if not staging_app.is_dir() or not staging_frontend.is_dir():
        raise HTTPException(
            503,
            "Staging release is incomplete; both app and frontend/build are required.",
        )

    RELEASES_ROOT.mkdir(parents=True, exist_ok=True)
    # timezone.utc keeps the deployment API compatible with the Pi's Python 3.9.
    release_id = (
        f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S%f}-{_build_version}"  # noqa: UP017
    )
    release = RELEASES_ROOT / release_id
    temporary = RELEASES_ROOT / f".{release_id}-{os.getpid()}"
    temporary.mkdir(parents=False, exist_ok=False)
    try:
        await _copy_tree(staging_app, temporary / "app", "app", log)
        await _copy_tree(staging_frontend, temporary / "frontend" / "build", "frontend", log)
        os.replace(temporary, release)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return release


def _schedule_service_restart() -> None:
    """Schedule a production restart after activation."""
    subprocess.Popen(
        ["sudo", "systemctl", "restart", "printforge"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def _require_active_release_layout() -> Path:
    """Verify systemd actually launched this process from the current release."""
    current = _release_target(CURRENT_LINK)
    # system.py is <release>/app/api/system.py.
    running_release = Path(__file__).resolve().parents[2]
    if current is None or running_release != current:
        raise HTTPException(
            503,
            "Production is not running from /opt/printforge/current. "
            "Install the release-based systemd unit before promoting.",
        )
    return current


@host_router.post("/promote")
async def promote_staging_to_production(request: Request):
    """Stage and atomically activate a complete release, retaining rollback."""
    _require_promotion_token(request)
    prod_status = _require_safe_production_state()
    log = [f"production status: {prod_status}"]

    current = _require_active_release_layout()

    release = await _stage_release(log)
    try:
        _atomic_release_link(current, PREVIOUS_LINK)
        _atomic_release_link(release, CURRENT_LINK)
        _schedule_service_restart()
    except Exception as exc:
        _atomic_release_link(current, CURRENT_LINK)
        raise HTTPException(500, f"Release activation failed: {exc}") from exc

    log.append(f"activated release: {release.name}")
    log.append(f"rollback release: {current.name}")
    log.append("restart scheduled")
    return {
        "status": "promoted",
        "productionStatusBefore": prod_status,
        "release": release.name,
        "previousRelease": current.name,
        "rollbackAvailable": True,
        "log": log,
    }


@host_router.post("/promote/rollback")
async def rollback_production_release(request: Request):
    """Atomically reactivate the retained previous release and restart."""
    _require_promotion_token(request)
    prod_status = _require_safe_production_state()
    current = _release_target(CURRENT_LINK)
    previous = _release_target(PREVIOUS_LINK)
    if current is None or previous is None or current == previous:
        raise HTTPException(409, "No valid previous production release is available.")

    try:
        _atomic_release_link(previous, CURRENT_LINK)
        _atomic_release_link(current, PREVIOUS_LINK)
        _schedule_service_restart()
    except Exception as exc:
        _atomic_release_link(current, CURRENT_LINK)
        _atomic_release_link(previous, PREVIOUS_LINK)
        raise HTTPException(500, f"Rollback activation failed: {exc}") from exc

    return {
        "status": "rolled_back",
        "productionStatusBefore": prod_status,
        "release": previous.name,
        "previousRelease": current.name,
    }

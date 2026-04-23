"""System information REST API endpoints."""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import shutil
import subprocess
import time
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException

from ..config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/system", tags=["system"])

_start_time = time.time()


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
    }


@router.get("/camera-health")
async def camera_health():
    """Camera system health check.

    Reports ustreamer status, ffmpeg availability, camera device detection,
    and the active capture fallback chain.
    """
    from ..printer.controller import PrinterController

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


@router.post("/restart-service")
async def restart_service():
    """Restart the PrintForge service."""
    try:
        subprocess.Popen(
            ["sudo", "systemctl", "restart", "printforge"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return {"status": "restarting"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


def _reject_if_printing() -> None:
    """Raise HTTPException if a print is in progress — safety guard."""
    from ..api import printer as printer_api
    from fastapi import HTTPException

    ctrl = getattr(printer_api, "_controller", None)
    if ctrl and ctrl.state.status in ("printing", "paused", "finishing"):
        raise HTTPException(
            409,
            f"Cannot perform this action while printer is {ctrl.state.status}. "
            "Cancel or finish the print first.",
        )


@router.post("/restart-os")
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


@router.post("/shutdown-os")
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


async def _run(cmd: list[str]) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    out, _ = await proc.communicate()
    return proc.returncode or 0, out.decode("utf-8", errors="replace").strip()


@router.post("/promote")
async def promote_staging_to_production(force: bool = False):
    """Copy /opt/printforge-staging/ onto production and restart.

    Only callable on the staging instance. Refuses if production is currently
    printing unless force=true. If production status can't be verified, also
    requires force=true — we won't blindly restart the printer service.
    """
    if settings.environment != "staging":
        raise HTTPException(403, "Promote is only available on staging.")

    log: list[str] = []

    # Check production's printer state via the public health endpoint.
    # Using /api/printer/state would 401 when production has API-key auth
    # configured — that used to force every promote to require --force.
    prod_status = "unknown"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get("http://127.0.0.1:8000/api/system/health")
            if r.status_code == 200:
                data = r.json()
                prod_status = str(data.get("printerStatus", "unknown"))
            else:
                prod_status = f"http_{r.status_code}"
    except Exception as e:
        prod_status = f"unreachable ({e.__class__.__name__})"

    log.append(f"production status: {prod_status}")

    unsafe_states = {"printing", "paused", "finishing"}
    if prod_status in unsafe_states and not force:
        raise HTTPException(
            409,
            f"Production is {prod_status}. Promotion would interrupt the print. "
            "Re-run with force=true to proceed anyway.",
        )
    if prod_status.startswith(("unreachable", "http_")) and not force:
        raise HTTPException(
            409,
            f"Can't verify production state ({prod_status}). "
            "Re-run with force=true to proceed anyway.",
        )

    # rsync staging app → production app
    rc, out = await _run([
        "rsync", "-a", "--delete",
        "/opt/printforge-staging/app/",
        "/opt/printforge/app/",
    ])
    log.append(f"rsync app rc={rc}")
    if out:
        log.append(out)
    if rc != 0:
        raise HTTPException(500, "\n".join(log))

    # rsync frontend build if present on staging
    if Path("/opt/printforge-staging/frontend/build").is_dir():
        await _run(["mkdir", "-p", "/opt/printforge/frontend"])
        rc, out = await _run([
            "rsync", "-a", "--delete",
            "/opt/printforge-staging/frontend/build/",
            "/opt/printforge/frontend/build/",
        ])
        log.append(f"rsync frontend rc={rc}")
        if out:
            log.append(out)
        if rc != 0:
            raise HTTPException(500, "\n".join(log))

    # Restart production
    rc, out = await _run(["sudo", "systemctl", "restart", "printforge"])
    log.append(f"restart rc={rc}")
    if out:
        log.append(out)
    if rc != 0:
        raise HTTPException(500, "\n".join(log))

    return {"status": "promoted", "productionStatusBefore": prod_status, "log": log}

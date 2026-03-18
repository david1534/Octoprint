"""System information REST API endpoints."""

import os
import platform
import shutil
import subprocess
import time
from pathlib import Path

from fastapi import APIRouter

from ..config import settings

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
    """System health check."""
    return {
        "status": "ok",
        "uptime": round(time.time() - _start_time),
        "cpuTemp": _read_pi_cpu_temp(),
        "cpuUsage": _read_cpu_usage(),
        "memory": _read_memory_info(),
        "platform": platform.machine(),
        "python": platform.python_version(),
    }


@router.get("/camera-health")
async def camera_health():
    """Camera system health check.

    Reports go2rtc status, ffmpeg availability, camera device detection,
    and the active capture fallback chain.
    """
    from ..printer.controller import PrinterController

    # Get the controller from the printer API module (same singleton)
    from ..api import printer as printer_api

    ctrl = getattr(printer_api, "_controller", None)
    if ctrl and ctrl.camera:
        health = ctrl.camera.health_dict()
        # Also refresh go2rtc status
        await ctrl.camera.refresh_go2rtc_status()
        health["go2rtc"]["available"] = ctrl.camera.go2rtc_available
        return health
    return {
        "go2rtc": {"available": False, "url": ""},
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


@router.post("/restart-os")
async def restart_os():
    """Restart the operating system."""
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
    """Shut down the operating system."""
    try:
        subprocess.Popen(
            ["sudo", "shutdown", "-h", "now"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return {"status": "shutting_down"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

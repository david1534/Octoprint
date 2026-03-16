"""System monitoring utilities for Raspberry Pi."""

from pathlib import Path


def get_cpu_temperature() -> float:
    """Read Raspberry Pi CPU temperature in Celsius."""
    try:
        temp_path = Path("/sys/class/thermal/thermal_zone0/temp")
        if temp_path.exists():
            return int(temp_path.read_text().strip()) / 1000.0
    except Exception:
        pass
    return 0.0


def get_load_average() -> tuple[float, float, float]:
    """Get 1, 5, 15 minute load averages."""
    try:
        with open("/proc/loadavg") as f:
            parts = f.read().split()
            return float(parts[0]), float(parts[1]), float(parts[2])
    except Exception:
        return 0.0, 0.0, 0.0


def get_uptime_seconds() -> float:
    """Get system uptime in seconds."""
    try:
        with open("/proc/uptime") as f:
            return float(f.read().split()[0])
    except Exception:
        return 0.0

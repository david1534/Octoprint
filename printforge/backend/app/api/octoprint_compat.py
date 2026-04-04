"""OctoPrint-compatible API shim.

Implements the subset of the OctoPrint REST API that OrcaSlicer and Cura
(and other slicers using OctoPrint host type) consume. Delegates all work
to the existing PrintForge controller — no duplicate state.

Implemented endpoints:
    GET  /api/version           — connection test
    GET  /api/settings          — minimal settings (webcam URL, features)
    POST /api/login             — passive auth check
    GET  /api/printer           — printer state (temps + status flags)
    GET  /api/printerprofiles   — printer geometry for build plate viz
    GET  /api/job               — current job progress
    POST /api/job               — pause / resume / cancel
    POST /api/files/local       — upload G-code, optionally start print
    POST /api/printer/command   — send raw G-code commands
    POST /api/connection        — connect / disconnect printer
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..config import settings
from ..printer.gcode_parser import parse_gcode_file

# Reuse the controller accessor already wired up by main.py
from .printer import get_controller

logger = logging.getLogger(__name__)

router = APIRouter(tags=["octoprint-compat"])

GCODE_DIR = Path(settings.gcode_dir)
ALLOWED_EXTENSIONS = {".gcode", ".g", ".gc"}


# ── Version ──────────────────────────────────────────────────────────────────


@router.get("/api/version")
async def octoprint_version():
    """Return OctoPrint-compatible version info.

    Both OrcaSlicer and Cura hit this endpoint to verify the connection.
    """
    return {
        "api": "0.1",
        "server": "1.9.0",
        "text": "OctoPrint 1.9.0",
    }


# ── Settings ─────────────────────────────────────────────────────────────────


@router.get("/api/settings")
async def octoprint_settings():
    """Return minimal OctoPrint settings.

    Cura's OctoPrint plugin reads this on connect to discover webcam URL
    and feature flags. We return a plausible stub.
    """
    return {
        "api": {"enabled": True, "key": "n/a"},
        "feature": {
            "sdSupport": False,
            "temperatureGraph": True,
            "modelSizeDetection": False,
        },
        "webcam": {
            "webcamEnabled": True,
            "streamUrl": "/webcam/?action=stream",
            "snapshotUrl": "/webcam/?action=snapshot",
            "flipH": False,
            "flipV": False,
            "rotate90": False,
        },
        "plugins": {},
    }


# ── Login ────────────────────────────────────────────────────────────────────


@router.post("/api/login")
async def octoprint_login():
    """Passive auth check.

    Cura's plugin sends the API key and expects a user info response.
    Since PrintForge has its own auth layer, we just acknowledge.
    """
    return {
        "name": "printforge",
        "active": True,
        "admin": True,
        "user": True,
        "apikey": "n/a",
        "_is_external_client": True,
    }


# ── Printer state ─────────────────────────────────────────────────────────────


def _status_flags(status: str) -> dict:
    printing = status == "printing"
    paused = status == "paused"
    operational = status in ("idle", "printing", "paused", "finishing")
    error = status == "error"
    closed = status in ("disconnected", "connecting")
    return {
        "operational": operational,
        "paused": paused,
        "printing": printing,
        "pausing": False,
        "cancelling": False,
        "sdReady": False,
        "error": error,
        "ready": operational and not printing and not paused,
        "closedOrError": closed or error,
    }


def _status_text(status: str) -> str:
    return {
        "disconnected": "Closed",
        "connecting": "Connecting",
        "idle": "Operational",
        "printing": "Printing",
        "paused": "Paused",
        "finishing": "Finishing",
        "error": "Error",
    }.get(status, status.capitalize())


@router.get("/api/printer")
async def octoprint_printer_state():
    """Return printer state in OctoPrint format."""
    ctrl = get_controller()
    s = ctrl.state
    return {
        "temperature": {
            "tool0": {
                "actual": round(s.hotend_actual, 1),
                "target": round(s.hotend_target, 1),
                "offset": 0,
            },
            "bed": {
                "actual": round(s.bed_actual, 1),
                "target": round(s.bed_target, 1),
                "offset": 0,
            },
        },
        "sd": {"ready": False},
        "state": {
            "text": _status_text(s.status.value),
            "flags": _status_flags(s.status.value),
        },
    }


# ── Printer profiles ─────────────────────────────────────────────────────────


@router.get("/api/printerprofiles")
async def octoprint_printer_profiles():
    """Return printer profile with bed dimensions.

    Cura queries this to render a build plate visualisation. Values match
    a typical Ender-3 / 220x220 printer — adjust if your bed differs.
    """
    return {
        "profiles": {
            "_default": {
                "id": "_default",
                "name": "PrintForge Printer",
                "model": "Generic",
                "default": True,
                "current": True,
                "volume": {
                    "width": 220,
                    "depth": 220,
                    "height": 250,
                    "formFactor": "rectangular",
                    "origin": "lowerleft",
                },
                "heatedBed": True,
                "heatedChamber": False,
                "axes": {
                    "x": {"speed": 6000, "inverted": False},
                    "y": {"speed": 6000, "inverted": False},
                    "z": {"speed": 200, "inverted": False},
                    "e": {"speed": 300, "inverted": False},
                },
                "extruder": {
                    "count": 1,
                    "nozzleDiameter": 0.4,
                },
            }
        }
    }


# ── Job info ──────────────────────────────────────────────────────────────────


@router.get("/api/job")
async def octoprint_job_info():
    """Return current job info in OctoPrint format."""
    ctrl = get_controller()
    s = ctrl.state
    status = s.status.value

    file_info: dict = {"name": None, "origin": "local", "size": None, "date": None}
    progress: dict = {
        "completion": None,
        "filepos": None,
        "printTime": None,
        "printTimeLeft": None,
        "printTimeLeftOrigin": None,
    }

    if s.current_file:
        file_info["name"] = Path(s.current_file).name

        if status in ("printing", "paused", "finishing"):
            completion = s.print_progress / 100.0 if s.print_progress else None
            progress = {
                "completion": round(completion, 4) if completion is not None else None,
                "filepos": None,
                "printTime": round(s.elapsed_seconds) if s.elapsed_seconds else None,
                "printTimeLeft": round(s.estimated_remaining) if s.estimated_remaining else None,
                "printTimeLeftOrigin": "linear" if s.estimated_remaining else None,
            }

    return {
        "job": {
            "file": file_info,
            "estimatedPrintTime": None,
            "filament": None,
            "lastPrintTime": None,
        },
        "progress": progress,
        "state": _status_text(status),
        "error": s.error_message or "",
    }


# ── Job control ───────────────────────────────────────────────────────────────


class JobCommandRequest(BaseModel):
    command: str  # "pause", "resume", "cancel", "start"


@router.post("/api/job")
async def octoprint_job_command(req: JobCommandRequest):
    """OctoPrint job control: pause / resume / cancel."""
    ctrl = get_controller()
    status = ctrl.state.status.value
    cmd = req.command.lower()

    if cmd == "pause":
        if status == "printing":
            await ctrl.pause_print()
        elif status == "paused":
            await ctrl.resume_print()
        else:
            raise HTTPException(409, f"Cannot pause/resume in state: {status}")

    elif cmd == "resume":
        if status != "paused":
            raise HTTPException(409, f"Cannot resume in state: {status}")
        await ctrl.resume_print()

    elif cmd == "cancel":
        if status not in ("printing", "paused"):
            raise HTTPException(409, f"Cannot cancel in state: {status}")
        await ctrl.cancel_print()

    else:
        raise HTTPException(400, f"Unsupported command: {cmd}")

    return JSONResponse(status_code=204, content=None)


# ── File upload ───────────────────────────────────────────────────────────────


@router.post("/api/files/local", status_code=201)
async def octoprint_upload_file(
    request: Request,
    file: UploadFile,
):
    """Upload a G-code file (OctoPrint-compatible multipart endpoint).

    Supports both OrcaSlicer (sends ``print``/``select`` as query params)
    and Cura (sends them as multipart form fields in the request body).
    The endpoint checks both sources so either slicer works.
    """
    # Cura sends path/print/select as multipart form fields.
    # OrcaSlicer sends them as query params. Support both.
    form = await request.form()
    path = str(form.get("path", "") or request.query_params.get("path", ""))
    print_val = str(form.get("print", "") or request.query_params.get("print", ""))
    select_val = str(form.get("select", "") or request.query_params.get("select", ""))
    GCODE_DIR.mkdir(parents=True, exist_ok=True)

    if not file.filename:
        raise HTTPException(400, "No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            400,
            f"Invalid file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Sanitize filename (same rules as the native upload endpoint)
    safe_name = "".join(
        c for c in file.filename if c.isalnum() or c in "._- ()"
    ).strip()
    if not safe_name:
        raise HTTPException(400, "Invalid filename after sanitisation")

    # Resolve target directory safely
    if path:
        target_dir = (GCODE_DIR / path).resolve()
        if not str(target_dir).startswith(str(GCODE_DIR.resolve())):
            raise HTTPException(400, "Invalid path")
    else:
        target_dir = GCODE_DIR

    target_dir.mkdir(parents=True, exist_ok=True)
    filepath = target_dir / safe_name

    # Write file to disk (async to avoid blocking event loop on slow SD cards)
    import aiofiles

    async with aiofiles.open(filepath, "wb") as f:
        while chunk := await file.read(65536):
            await f.write(chunk)

    # Parse metadata — always build refs so OrcaSlicer can resolve the file
    rel_path = str(filepath.relative_to(GCODE_DIR)).replace("\\", "/")
    refs = {
        "resource": f"/api/files/local/{rel_path}",
        "download": f"/api/files/{rel_path}",
    }
    try:
        parse_gcode_file(filepath)
        file_resp = {
            "name": safe_name,
            "path": rel_path,
            "type": "machinecode",
            "typePath": ["machinecode", "gcode"],
            "size": filepath.stat().st_size,
            "refs": refs,
        }
    except Exception:
        file_resp = {
            "name": safe_name,
            "path": rel_path,
            "type": "machinecode",
            "size": filepath.stat().st_size,
            "refs": refs,
        }

    # Optionally start the print immediately
    start_requested = print_val.lower() in ("true", "1", "yes") if print_val else False
    if start_requested:
        ctrl = get_controller()
        if ctrl.state.status.value not in ("idle",):
            # Don't fail the upload — just skip auto-print and note it
            file_resp["_printSkipped"] = f"Printer is {ctrl.state.status.value}, not idle"
        else:
            await ctrl.start_print(filepath)

    return {
        "files": {"local": file_resp},
        "done": True,
    }


# ── Printer command ──────────────────────────────────────────────────────────


class GcodeCommandRequest(BaseModel):
    commands: Optional[list[str]] = None
    command: Optional[str] = None


@router.post("/api/printer/command")
async def octoprint_printer_command(req: GcodeCommandRequest):
    """Send raw G-code commands to the printer.

    Cura uses this for manual jog controls, preheat buttons, and the
    terminal tab. Accepts either a single ``command`` string or a list
    of ``commands``.
    """
    ctrl = get_controller()
    if ctrl.state.status.value in ("disconnected", "connecting"):
        raise HTTPException(409, "Printer is not connected")

    cmds: list[str] = []
    if req.commands:
        cmds = req.commands
    elif req.command:
        cmds = [req.command]
    else:
        raise HTTPException(400, "No command(s) provided")

    for cmd in cmds:
        await ctrl.send_command(cmd.strip())

    return JSONResponse(status_code=204, content=None)


# ── Connection management ────────────────────────────────────────────────────


class ConnectionRequest(BaseModel):
    command: str  # "connect" or "disconnect"
    port: Optional[str] = None
    baudrate: Optional[int] = None


@router.get("/api/connection")
async def octoprint_connection_state():
    """Return current connection state.

    Cura may poll this to check whether the printer is connected.
    """
    ctrl = get_controller()
    status = ctrl.state.status.value
    connected = status not in ("disconnected", "connecting")
    return {
        "current": {
            "state": _status_text(status),
            "port": ctrl.state.port if connected else None,
            "baudrate": ctrl.state.baudrate if connected else None,
            "printerProfile": "_default",
        },
        "options": {
            "ports": ["/dev/ttyUSB0", "/dev/ttyACM0"],
            "baudrates": [115200, 250000],
            "printerProfiles": [{"id": "_default", "name": "PrintForge Printer"}],
        },
    }


@router.post("/api/connection")
async def octoprint_connection_command(req: ConnectionRequest):
    """Connect or disconnect the printer.

    Cura's plugin uses this to manage the serial connection.
    """
    ctrl = get_controller()
    cmd = req.command.lower()

    if cmd == "connect":
        port = req.port or "/dev/ttyUSB0"
        baudrate = req.baudrate or 115200
        if ctrl.state.status.value not in ("disconnected", "error"):
            raise HTTPException(409, "Already connected")
        ok = await ctrl.connect(port=port, baudrate=baudrate)
        if not ok:
            raise HTTPException(500, f"Failed to connect to {port}")

    elif cmd == "disconnect":
        if ctrl.state.status.value == "disconnected":
            raise HTTPException(409, "Already disconnected")
        await ctrl.disconnect()

    else:
        raise HTTPException(400, f"Unsupported command: {cmd}")

    return JSONResponse(status_code=204, content=None)

"""OctoPrint-compatible API shim.

Implements the subset of the OctoPrint REST API that OrcaSlicer (and other
slicers using Octo/Klipper host type) consume. Delegates all work to the
existing PrintForge controller and file-upload logic — no duplicate state.

Implemented endpoints:
    GET  /api/version         — connection test ("Test" button in OrcaSlicer)
    GET  /api/printer         — printer state (temps + status flags)
    GET  /api/job             — current job progress
    POST /api/job             — pause / resume / cancel
    POST /api/files/local     — upload G-code, optionally start print
"""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..config import settings
from ..printer.gcode_parser import parse_gcode_file

# Reuse the controller accessor already wired up by main.py
from .printer import get_controller

router = APIRouter(tags=["octoprint-compat"])

GCODE_DIR = Path(settings.gcode_dir)
ALLOWED_EXTENSIONS = {".gcode", ".g", ".gc"}


# ── Version ──────────────────────────────────────────────────────────────────


@router.get("/api/version")
async def octoprint_version():
    """Return OctoPrint-compatible version info.

    OrcaSlicer's "Test" button hits this endpoint. Returning a plausible
    version string makes it show a green checkmark.
    """
    return {
        "api": "0.1",
        "server": "1.9.0",
        "text": "OctoPrint 1.9.0",
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
    file: UploadFile,
    path: str = Query("", description="Subfolder within G-code directory"),
    print: Optional[str] = Query(None, description="Set to 'true' to start print immediately"),
    select: Optional[str] = Query(None, description="Set to 'true' to select file after upload"),
):
    """Upload a G-code file (OctoPrint-compatible multipart endpoint).

    OrcaSlicer sends the file as a multipart upload to this path. If the
    ``print`` query param is ``"true"``, the print is started immediately
    after upload. If ``select`` is ``"true"``, the file is marked as the
    selected file (no-op here since PrintForge selects at print time).
    """
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

    # Write file to disk
    with open(filepath, "wb") as f:
        while chunk := await file.read(65536):
            f.write(chunk)

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
    start_requested = str(print).lower() in ("true", "1", "yes") if print else False
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

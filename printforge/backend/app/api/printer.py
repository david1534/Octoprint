"""Printer control REST API endpoints."""

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import settings
from ..printer.controller import PrinterController

router = APIRouter(prefix="/api/printer", tags=["printer"])

# The controller is injected at app startup
_controller: Optional[PrinterController] = None


def set_controller(controller: PrinterController) -> None:
    global _controller
    _controller = controller


def get_controller() -> PrinterController:
    if _controller is None:
        raise HTTPException(503, "Printer controller not initialized")
    return _controller


class ConnectRequest(BaseModel):
    port: str = "/dev/ttyUSB0"
    baudrate: int = 115200


class TemperatureRequest(BaseModel):
    hotend: Optional[float] = None
    bed: Optional[float] = None
    wait: bool = False


class JogRequest(BaseModel):
    x: float = 0
    y: float = 0
    z: float = 0
    feedrate: int = 3000


class ExtrudeRequest(BaseModel):
    length: float  # Positive = extrude, negative = retract
    feedrate: int = 300


class FanRequest(BaseModel):
    speed: int  # 0-255


class CommandRequest(BaseModel):
    command: str


class PrintRequest(BaseModel):
    filename: str
    spool_id: Optional[int] = None


@router.get("/state")
async def get_state():
    """Get current printer state."""
    ctrl = get_controller()
    return ctrl.state.to_dict()


@router.post("/connect")
async def connect(req: ConnectRequest):
    """Connect to the printer."""
    ctrl = get_controller()
    success = await ctrl.connect(port=req.port, baudrate=req.baudrate)
    if not success:
        raise HTTPException(500, f"Failed to connect to {req.port}")
    return {"status": "connected", "firmware": ctrl.state.firmware_name}


@router.post("/disconnect")
async def disconnect():
    """Disconnect from the printer."""
    ctrl = get_controller()
    await ctrl.disconnect()
    return {"status": "disconnected"}


@router.post("/home")
async def home(axes: str = "XYZ"):
    """Home specified axes."""
    ctrl = get_controller()
    result = await ctrl.home(axes)
    return {"ok": result.ok, "response": result.response_lines}


@router.post("/temperature")
async def set_temperature(req: TemperatureRequest):
    """Set target temperatures."""
    ctrl = get_controller()
    await ctrl.set_temperature(
        hotend=req.hotend, bed=req.bed, wait=req.wait
    )
    return {"ok": True}


@router.post("/jog")
async def jog(req: JogRequest):
    """Relative move."""
    ctrl = get_controller()
    await ctrl.jog(x=req.x, y=req.y, z=req.z, feedrate=req.feedrate)
    return {"ok": True}


@router.post("/extrude")
async def extrude(req: ExtrudeRequest):
    """Extrude or retract filament."""
    ctrl = get_controller()
    await ctrl.extrude(length=req.length, feedrate=req.feedrate)
    return {"ok": True}


@router.post("/fan")
async def set_fan(req: FanRequest):
    """Set fan speed."""
    ctrl = get_controller()
    await ctrl.set_fan_speed(req.speed)
    return {"ok": True}


@router.post("/command")
async def send_command(req: CommandRequest):
    """Send a raw G-code command."""
    ctrl = get_controller()
    result = await ctrl.send_command(req.command)
    return {
        "ok": result.ok,
        "command": result.command,
        "response": result.response_lines,
        "error": result.error,
    }


@router.post("/print")
async def start_print(req: PrintRequest):
    """Start printing a file."""
    ctrl = get_controller()
    gcode_dir = Path(settings.gcode_dir)
    filepath = (gcode_dir / req.filename).resolve()
    # Prevent path traversal
    if not str(filepath).startswith(str(gcode_dir.resolve())):
        raise HTTPException(400, "Invalid path")
    if not filepath.exists():
        raise HTTPException(404, f"File not found: {req.filename}")
    await ctrl.start_print(filepath, spool_id=req.spool_id)
    return {"ok": True, "file": req.filename}


@router.post("/pause")
async def pause_print():
    """Pause the current print."""
    ctrl = get_controller()
    await ctrl.pause_print()
    return {"ok": True}


@router.post("/resume")
async def resume_print():
    """Resume a paused print."""
    ctrl = get_controller()
    await ctrl.resume_print()
    return {"ok": True}


@router.post("/cancel")
async def cancel_print():
    """Cancel the current print."""
    ctrl = get_controller()
    await ctrl.cancel_print()
    return {"ok": True}


@router.post("/emergency-stop")
async def emergency_stop():
    """Emergency stop. Printer must be power-cycled after."""
    ctrl = get_controller()
    await ctrl.emergency_stop()
    return {"ok": True, "message": "Emergency stop sent. Power cycle printer."}


@router.post("/motors-off")
async def disable_motors():
    """Disable stepper motors."""
    ctrl = get_controller()
    await ctrl.disable_motors()
    return {"ok": True}


@router.get("/temperature/history")
async def temperature_history():
    """Get temperature history for charting."""
    ctrl = get_controller()
    history = ctrl.temp_monitor.history
    return {
        "hotend": [
            {"actual": s.hotend.actual, "target": s.hotend.target, "t": s.hotend.timestamp}
            for s in history
        ],
        "bed": [
            {"actual": s.bed.actual, "target": s.bed.target, "t": s.bed.timestamp}
            for s in history
        ],
    }

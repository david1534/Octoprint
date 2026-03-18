"""Printer state management.

Centralized state that all components read/write. The state is broadcast
to connected WebSocket clients on every change.
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class PrinterStatus(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    IDLE = "idle"
    PRINTING = "printing"
    PAUSED = "paused"
    ERROR = "error"
    FINISHING = "finishing"


@dataclass
class PrinterState:
    status: PrinterStatus = PrinterStatus.DISCONNECTED

    # Connection info
    port: str = ""
    baudrate: int = 115200

    # Temperatures
    hotend_actual: float = 0.0
    hotend_target: float = 0.0
    bed_actual: float = 0.0
    bed_target: float = 0.0

    # Position
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    # Print job
    current_file: Optional[str] = None
    print_progress: float = 0.0
    elapsed_seconds: float = 0.0
    estimated_remaining: float = 0.0
    current_layer: int = 0
    total_layers: int = 0
    current_line: int = 0
    total_lines: int = 0

    # Fan
    fan_speed: int = 0  # 0-255

    # Firmware
    firmware_name: str = ""

    # Error
    error_message: Optional[str] = None

    # Timestamps
    last_update: float = field(default_factory=time.time)

    # Timelapse status (set by controller)
    timelapse_recording: bool = False
    timelapse_frame_count: int = 0
    timelapse_assembling: bool = False

    # Bed mesh data (populated by G29 / M420 V response parsing)
    bed_mesh: Optional[dict] = None

    def to_dict(self) -> dict:
        """Serialize state for WebSocket transmission."""
        return {
            "status": self.status.value,
            "port": self.port,
            "baudrate": self.baudrate,
            "hotend": {
                "actual": round(self.hotend_actual, 1),
                "target": round(self.hotend_target, 1),
            },
            "bed": {
                "actual": round(self.bed_actual, 1),
                "target": round(self.bed_target, 1),
            },
            "position": {
                "x": round(self.x, 2),
                "y": round(self.y, 2),
                "z": round(self.z, 2),
            },
            "print": {
                "file": self.current_file,
                "progress": round(self.print_progress, 1),
                "elapsed": round(self.elapsed_seconds),
                "remaining": round(self.estimated_remaining),
                "currentLayer": self.current_layer,
                "totalLayers": self.total_layers,
                "currentLine": self.current_line,
                "totalLines": self.total_lines,
            },
            "fan_speed": self.fan_speed,
            "firmware": self.firmware_name,
            "error": self.error_message,
            "timelapse": {
                "recording": self.timelapse_recording,
                "frameCount": self.timelapse_frame_count,
                "assembling": self.timelapse_assembling,
            },
            "bed_mesh": self.bed_mesh,
        }

    def update_temperatures(
        self,
        hotend_actual: float,
        hotend_target: float,
        bed_actual: float,
        bed_target: float,
    ) -> None:
        self.hotend_actual = hotend_actual
        self.hotend_target = hotend_target
        self.bed_actual = bed_actual
        self.bed_target = bed_target
        self.last_update = time.time()

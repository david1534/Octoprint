"""High-level printer controller.

Orchestrates serial connection, command queue, temperature monitoring,
safety checks, and G-code sending. This is the main interface used by
the API layer.
"""

import asyncio
import glob
import logging
import re
import time as _time
from pathlib import Path
from typing import Callable, Optional

from ..serial.bed_mesh import BedMeshParser
from ..serial.command_queue import CommandPriority, CommandQueue
from ..serial.connection import SerialConnection
from ..serial.gcode_sender import GcodeSender
from ..serial.protocol import CommandResult, MarlinProtocol
from ..serial.safety import SafetyAction, SafetyAlert, SafetyMonitor
from ..serial.temperature import TemperatureMonitor, TemperatureSnapshot
from ..services.camera import CameraService
from ..services.timelapse import TimelapseRecorder
from .error_log import ErrorLog
from .state import PrinterState, PrinterStatus

logger = logging.getLogger(__name__)

# Pre-compiled regex for position parsing (called on every M114 response)
_POSITION_RE = re.compile(r"X:([\d.-]+)\s*Y:([\d.-]+)\s*Z:([\d.-]+)")


class PrinterController:
    """High-level printer control interface."""

    def __init__(self, state: PrinterState):
        self.state = state
        self._connection: Optional[SerialConnection] = None
        self._protocol: Optional[MarlinProtocol] = None
        self._queue: Optional[CommandQueue] = None
        self._sender: Optional[GcodeSender] = None
        self._temp_monitor = TemperatureMonitor()
        self._safety = SafetyMonitor()
        self._safety_task: Optional[asyncio.Task] = None
        self._error_log = ErrorLog()
        self._state_callbacks: list[Callable[[], None]] = []
        self._terminal_callbacks: list[Callable[[str, str], None]] = []
        # Print time correction
        self._slicer_estimated_seconds: float = 0.0
        self._time_correction_factor: float = 1.0
        # Current print job ID for history tracking
        self._current_job_id: Optional[int] = None
        # Spool selected for current print
        self._current_spool_id: Optional[int] = None
        # Camera and timelapse
        self._camera: Optional[CameraService] = None
        self._timelapse: Optional[TimelapseRecorder] = None
        # Bed mesh parser (fed by terminal callback)
        self._bed_mesh_parser = BedMeshParser()

    @property
    def temp_monitor(self) -> TemperatureMonitor:
        return self._temp_monitor

    @property
    def safety_monitor(self) -> SafetyMonitor:
        return self._safety

    @property
    def error_log(self) -> ErrorLog:
        return self._error_log

    @property
    def sender(self) -> Optional[GcodeSender]:
        return self._sender

    @property
    def timelapse(self) -> Optional[TimelapseRecorder]:
        return self._timelapse

    @property
    def camera(self) -> Optional[CameraService]:
        return self._camera

    async def init_camera_and_timelapse(
        self, camera_url: str, timelapse_dir: Path
    ) -> None:
        """Initialize camera service and timelapse recorder."""
        self._camera = CameraService(camera_url)
        await self._camera.init()
        self._timelapse = TimelapseRecorder(self._camera, timelapse_dir)
        logger.info(
            "Camera + timelapse initialized (chain: %s, output: %s)",
            " -> ".join(self._camera.health_dict()["captureChain"]),
            timelapse_dir,
        )

    def add_state_callback(self, callback: Callable[[], None]) -> None:
        """Register a callback for state changes (used by WebSocket)."""
        self._state_callbacks.append(callback)

    def remove_state_callback(self, callback: Callable[[], None]) -> None:
        if callback in self._state_callbacks:
            self._state_callbacks.remove(callback)

    def add_terminal_callback(self, callback: Callable[[str, str], None]) -> None:
        """Register callback for terminal lines. callback(line, direction)."""
        self._terminal_callbacks.append(callback)

    def remove_terminal_callback(self, callback: Callable[[str, str], None]) -> None:
        if callback in self._terminal_callbacks:
            self._terminal_callbacks.remove(callback)

    def _notify_state_change(self) -> None:
        for cb in self._state_callbacks:
            try:
                cb()
            except Exception:
                logger.exception("Error in state callback")

    def _notify_terminal(self, line: str, direction: str) -> None:
        for cb in self._terminal_callbacks:
            try:
                cb(line, direction)
            except Exception:
                logger.exception("Error in terminal callback")

    def _on_temp_line(self, line: str) -> None:
        """Called when temperature data is received."""
        self._safety.record_serial_activity()
        snapshot = self._temp_monitor.parse_line(line)
        if snapshot:
            self.state.update_temperatures(
                hotend_actual=snapshot.hotend.actual,
                hotend_target=snapshot.hotend.target,
                bed_actual=snapshot.bed.actual,
                bed_target=snapshot.bed.target,
            )
            alerts = self._safety.check_temperatures(snapshot)
            for alert in alerts:
                self._handle_safety_alert(alert)
            self._notify_state_change()

    def _on_terminal_line(self, line: str, direction: str) -> None:
        """Called for every terminal line (sent or received)."""
        # Record serial activity for both send and recv — sending proves the
        # connection is alive even during long-running commands where the
        # printer hasn't responded yet (G28, G29, M109, M190).
        self._safety.record_serial_activity()
        self._notify_terminal(line, direction)

        # Capture firmware error lines into the error log
        if direction == "recv" and line.startswith("Error:"):
            self._error_log.log_raw(line)
            # Check for kill/STOP errors embedded in Error: lines
            # (e.g. "Error:!! STOP called because of BLTouch error")
            if "!! " in line:
                asyncio.create_task(self._attempt_kill_recovery(line))
        elif direction == "recv" and "!! " in line:
            # Standalone Marlin emergency messages
            self._error_log.log_raw(line)
            asyncio.create_task(self._attempt_kill_recovery(line))

        # Feed received lines to the bed mesh parser
        if direction == "recv":
            mesh = self._bed_mesh_parser.feed_line(line)
            if mesh:
                self.state.bed_mesh = mesh.to_dict()
                self._notify_state_change()
            # Also check for M420 mesh activation status
            self._bed_mesh_parser.parse_m420_status(line)

    def _on_position_line(self, line: str) -> None:
        """Called when position report is received."""
        match = _POSITION_RE.search(line)
        if match:
            self.state.x = float(match.group(1))
            self.state.y = float(match.group(2))
            self.state.z = float(match.group(3))

    def _handle_safety_alert(self, alert: SafetyAlert) -> None:
        logger.warning("Safety alert: %s", alert.message)
        self._notify_terminal(f"[SAFETY] {alert.message}", "system")
        self._error_log.log_safety_alert(
            alert.message, alert.level.value, alert.action.value
        )
        if alert.action == SafetyAction.EMERGENCY_STOP:
            asyncio.create_task(self.emergency_stop())
        elif alert.action == SafetyAction.PAUSE_PRINT:
            if self._sender and self._sender.is_printing:
                asyncio.create_task(self.pause_print())

    _kill_recovery_in_progress = False

    async def _attempt_kill_recovery(self, kill_line: str) -> None:
        """Attempt to recover from a Marlin kill/STOP state via M999.

        When Marlin enters a kill state (!! STOP), it halts all command
        processing. We bypass the command queue and send M999 directly
        on the serial connection to reset the firmware. If successful,
        we re-enable temperature reporting and transition back to idle.
        """
        if self._kill_recovery_in_progress:
            return
        if not self._connection or not self._connection.connected:
            return

        self._kill_recovery_in_progress = True
        logger.warning("Kill state detected: %s — attempting M999 recovery", kill_line)
        self._notify_terminal(
            "[SYSTEM] Printer halted — attempting automatic recovery (M999)...",
            "system",
        )

        # Cancel any active print — it's dead anyway
        if self._sender and self._sender.is_printing:
            await self._sender.cancel()

        # Flush the command queue so stale commands don't pile up.
        # Await the task to ensure the process loop has fully exited
        # before we start reading from serial directly — otherwise
        # two coroutines would race on the same StreamReader.
        if self._queue:
            self._queue.stop()
            if self._queue._task:
                try:
                    await self._queue._task
                except asyncio.CancelledError:
                    pass

        try:
            # Send M999 directly on the serial line (bypasses the stopped queue)
            await self._connection.send("M999")

            # Wait for Marlin to reboot — it sends startup messages then "ok"
            recovered = False
            for _ in range(30):  # Up to 30 seconds
                try:
                    line = await self._connection.read_line(timeout=1.0)
                    if line:
                        self._notify_terminal(line, "recv")
                        logger.debug("M999 recovery: %s", line)
                        if line.strip().startswith("ok") or "start" in line.lower():
                            recovered = True
                            break
                except asyncio.TimeoutError:
                    continue
                except ConnectionError:
                    break

            if recovered:
                logger.info("M999 recovery successful — reinitializing")
                self._notify_terminal(
                    "[SYSTEM] Recovery successful — reinitializing printer",
                    "system",
                )

                # Restart the command queue
                if self._protocol:
                    self._protocol.reset_line_number()
                    self._queue = CommandQueue(self._protocol)
                    self._queue.start()
                    self._sender = GcodeSender(self._queue)

                # Re-enable temperature auto-reporting
                await self._queue.enqueue("M155 S2", CommandPriority.SYSTEM)

                self.state.status = PrinterStatus.IDLE
                self.state.error_message = None
                self._safety.record_serial_activity()
                self._notify_state_change()
            else:
                logger.error("M999 recovery failed — printer needs power cycle")
                self._notify_terminal(
                    "[SYSTEM] Recovery failed — please power cycle the printer",
                    "system",
                )
                self._error_log.log_system_error(
                    "Recovery Failed",
                    "Automatic M999 recovery failed. The printer needs a manual power cycle.",
                )
                self.state.status = PrinterStatus.ERROR
                self.state.error_message = (
                    "Printer halted — power cycle required"
                )
                self._notify_state_change()

        except Exception as e:
            logger.exception("Error during kill recovery: %s", e)
            self.state.status = PrinterStatus.ERROR
            self.state.error_message = "Printer halted — power cycle required"
            self._notify_state_change()
        finally:
            self._kill_recovery_in_progress = False

    async def auto_connect(self) -> None:
        """Auto-connect to the printer on startup if enabled in settings."""
        from ..storage.models import get_setting, set_setting

        enabled = await get_setting("auto_connect_enabled", "false")
        if enabled != "true":
            logger.info("Auto-connect disabled, skipping")
            return

        port = await get_setting("auto_connect_port", "auto")
        baudrate = int(await get_setting("auto_connect_baudrate", "115200"))

        if port == "auto":
            # Scan common serial ports
            candidates = sorted(glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*"))
            # Prefer /dev/printforge if it exists
            if Path("/dev/printforge").exists():
                candidates.insert(0, "/dev/printforge")
            if not candidates:
                logger.warning("Auto-connect: no serial ports found")
                return
            for candidate in candidates:
                logger.info("Auto-connect: trying %s @ %d", candidate, baudrate)
                try:
                    if await self.connect(candidate, baudrate):
                        await set_setting("auto_connect_port", candidate)
                        logger.info("Auto-connect: success on %s", candidate)
                        return
                except Exception as e:
                    logger.debug("Auto-connect: %s failed: %s", candidate, e)
            logger.warning("Auto-connect: all ports failed")
        else:
            logger.info("Auto-connect: connecting to %s @ %d", port, baudrate)
            try:
                if await self.connect(port, baudrate):
                    logger.info("Auto-connect: success")
                else:
                    logger.warning("Auto-connect: failed on %s", port)
            except Exception as e:
                logger.warning("Auto-connect: %s failed: %s", port, e)

    async def connect(self, port: str = "/dev/ttyUSB0", baudrate: int = 115200) -> bool:
        """Connect to the printer."""
        self.state.status = PrinterStatus.CONNECTING
        self.state.port = port
        self.state.baudrate = baudrate
        self._notify_state_change()

        self._connection = SerialConnection(port=port, baudrate=baudrate)
        if not await self._connection.connect():
            self.state.status = PrinterStatus.ERROR
            self.state.error_message = f"Failed to connect to {port}"
            self._notify_state_change()
            return False

        self._protocol = MarlinProtocol(self._connection)
        self._protocol.add_temp_callback(self._on_temp_line)
        self._protocol.add_terminal_callback(self._on_terminal_line)
        self._protocol.add_position_callback(self._on_position_line)

        self._queue = CommandQueue(self._protocol)
        self._queue.start()

        self._sender = GcodeSender(self._queue)

        # Detect firmware
        self.state.firmware_name = await self._protocol.query_firmware()

        # Enable temperature auto-reporting every 2 seconds
        await self._queue.enqueue("M155 S2", CommandPriority.SYSTEM)

        self.state.status = PrinterStatus.IDLE
        self.state.error_message = None
        self._notify_state_change()

        # Reset watchdog so it doesn't fire on stale timestamps
        self._safety.record_serial_activity()
        # Start safety monitoring loop
        self._safety_task = asyncio.create_task(self._safety_loop())

        logger.info("Printer connected: %s", self.state.firmware_name)
        return True

    async def disconnect(self) -> None:
        """Disconnect from the printer."""
        if self._safety_task:
            self._safety_task.cancel()
            try:
                await self._safety_task
            except asyncio.CancelledError:
                pass

        if self._sender and self._sender.is_printing:
            await self._sender.cancel()

        if self._queue:
            self._queue.stop()

        if self._connection:
            await self._connection.disconnect()

        self.state.status = PrinterStatus.DISCONNECTED
        self._notify_state_change()
        logger.info("Printer disconnected")

    async def send_command(self, command: str) -> CommandResult:
        """Send a manual G-code command."""
        if not self._queue:
            raise ConnectionError("Not connected")
        self._notify_terminal(command, "send")
        future = await self._queue.enqueue(command, CommandPriority.USER)
        return await future

    async def home(self, axes: str = "XYZ") -> CommandResult:
        """Home specified axes. Must not be called during printing."""
        if self.state.status in (PrinterStatus.PRINTING, PrinterStatus.PAUSED):
            raise RuntimeError("Cannot home while printing")
        cmd = "G28"
        for axis in axes.upper():
            if axis in "XYZ":
                cmd += f" {axis}"
        return await self.send_command(cmd)

    async def set_temperature(
        self,
        hotend: Optional[float] = None,
        bed: Optional[float] = None,
        wait: bool = False,
    ) -> None:
        """Set target temperatures."""
        if hotend is not None:
            cmd = f"M109 S{hotend}" if wait else f"M104 S{hotend}"
            await self.send_command(cmd)
        if bed is not None:
            cmd = f"M190 S{bed}" if wait else f"M140 S{bed}"
            await self.send_command(cmd)

    async def jog(
        self, x: float = 0, y: float = 0, z: float = 0, feedrate: int = 3000
    ) -> None:
        """Relative move. Must not be called during printing."""
        if self.state.status in (PrinterStatus.PRINTING, PrinterStatus.PAUSED):
            raise RuntimeError("Cannot jog while printing")
        await self.send_command("G91")  # Relative mode
        parts = ["G1"]
        if x:
            parts.append(f"X{x}")
        if y:
            parts.append(f"Y{y}")
        if z:
            parts.append(f"Z{z}")
        parts.append(f"F{feedrate}")
        await self.send_command(" ".join(parts))
        await self.send_command("G90")  # Back to absolute

    async def set_fan_speed(self, speed: int) -> None:
        """Set fan speed (0-255)."""
        speed = max(0, min(255, speed))
        await self.send_command(f"M106 S{speed}")
        self.state.fan_speed = speed
        self._notify_state_change()

    async def extrude(self, length: float, feedrate: int = 300) -> None:
        """Extrude or retract filament. Must not be called during printing."""
        if self.state.status in (PrinterStatus.PRINTING, PrinterStatus.PAUSED):
            raise RuntimeError("Cannot extrude while printing")
        await self.send_command("G91")
        await self.send_command(f"G1 E{length} F{feedrate}")
        await self.send_command("G90")

    async def probe_bed_mesh(self) -> dict:
        """Run G29 bed-leveling probe and return the parsed mesh.

        Homes first (G28) then probes (G29). The mesh parser picks up
        the grid from the response lines automatically via the terminal
        callback. After probing, sends M420 S1 to ensure the mesh is
        activated, then M420 V to confirm status.
        """
        if not self._queue:
            raise ConnectionError("Not connected")

        self._notify_terminal("[SYSTEM] Starting bed mesh probe...", "system")

        # Home all axes first (G29 requires known position)
        await self.send_command("G28")
        # Probe the bed
        await self.send_command("G29")
        # Activate the mesh (some firmware needs explicit activation)
        await self.send_command("M420 S1")
        # Query mesh status for confirmation
        await self.send_command("M420 V")

        self._notify_terminal("[SYSTEM] Bed mesh probe complete", "system")

        mesh = self._bed_mesh_parser.mesh
        if mesh:
            self.state.bed_mesh = mesh.to_dict()
            self._notify_state_change()
            return mesh.to_dict()
        return {}

    def get_bed_mesh(self) -> dict:
        """Return the current bed mesh data (if any)."""
        mesh = self._bed_mesh_parser.mesh
        if mesh:
            return mesh.to_dict()
        return self.state.bed_mesh or {}

    # Default start G-code for Ender 3 style printers.
    # Homes all axes, probes bed level, heats up, and prints a purge line.
    # Template variables: {nozzle_temp}, {bed_temp}
    DEFAULT_START_GCODE = """\
M140 S{bed_temp} ; Start heating bed (non-blocking)
M104 S{nozzle_temp} ; Start heating nozzle (non-blocking)
M280 P0 S160 ; Reset BLTouch (clears alarm state)
G4 P500 ; Wait 500ms for BLTouch reset
G28 ; Home all axes
G29 ; Auto bed leveling probe (remove if no ABL)
M420 S1 ; Activate mesh compensation (ensures G29 values are used)
M190 S{bed_temp} ; Wait for bed to reach temperature
M109 S{nozzle_temp} ; Wait for nozzle to reach temperature
G92 E0 ; Reset extruder position
G1 Z2.0 F3000 ; Lift nozzle
G1 X0.1 Y20 Z0.3 F5000.0 ; Move to purge line start
G1 X0.1 Y200.0 Z0.3 F1500.0 E15 ; Draw first purge line
G1 X0.4 Y200.0 Z0.3 F5000.0 ; Shift over
G1 X0.4 Y20 Z0.3 F1500.0 E30 ; Draw second purge line
G92 E0 ; Reset extruder
G1 Z2.0 F3000 ; Lift nozzle
M117 Printing..."""

    # Default end G-code: retract, present print, cool down, disable steppers
    DEFAULT_END_GCODE = """\
G91 ; Relative positioning
G1 E-5 F1800 ; Retract filament
G1 Z10 F600 ; Lift Z 10mm
G90 ; Absolute positioning
G1 X0 Y220 F3000 ; Present print (move bed forward)
M104 S0 ; Turn off nozzle
M140 S0 ; Turn off bed
M106 S0 ; Turn off fan
M84 ; Disable steppers
M117 Print Complete"""

    async def _run_gcode_sequence(
        self, gcode_text: str, nozzle_temp: float, bed_temp: float
    ) -> None:
        """Send a sequence of G-code lines (start/end gcode) through the queue.

        Supports template variables: {nozzle_temp}, {bed_temp}
        """
        if not self._queue:
            return

        # Substitute template variables
        gcode_text = gcode_text.replace("{nozzle_temp}", str(int(nozzle_temp)))
        gcode_text = gcode_text.replace("{bed_temp}", str(int(bed_temp)))

        for line in gcode_text.splitlines():
            line = line.strip()
            # Strip inline comments
            if ";" in line:
                line = line[: line.index(";")].strip()
            if not line:
                continue
            self._notify_terminal(line, "send")
            future = await self._queue.enqueue(line, CommandPriority.SYSTEM)
            result = await future
            if not result.ok:
                logger.warning(
                    "Start/end gcode command failed: %s -> %s", line, result.error
                )

    async def start_print(self, filepath: Path, spool_id: Optional[int] = None) -> None:
        """Start printing a G-code file."""
        if not self._sender:
            raise ConnectionError("Not connected")

        # Configure LCD progress from settings
        from ..storage.models import get_setting

        lcd_enabled = await get_setting("lcd_progress_enabled", "false") == "true"
        lcd_interval = int(await get_setting("lcd_progress_interval", "50"))
        self._sender.configure_lcd(enabled=lcd_enabled, interval=lcd_interval)

        # Load slicer estimate and correction factor for better time estimates
        from ..printer.gcode_parser import parse_gcode_file
        from ..storage.models import get_time_correction_factor

        try:
            meta = parse_gcode_file(filepath)
            self._slicer_estimated_seconds = meta.estimated_time_seconds or 0.0
            self._time_correction_factor = await get_time_correction_factor()
        except Exception:
            self._slicer_estimated_seconds = 0.0
            self._time_correction_factor = 1.0
            meta = None

        # Determine temperatures from file metadata or defaults
        nozzle_temp = meta.nozzle_temp if meta and meta.nozzle_temp else 200
        bed_temp = meta.bed_temp if meta and meta.bed_temp else 60

        # Prepare start G-code with temperature substitution
        from ..storage.models import set_setting

        start_gcode_raw = await get_setting("start_gcode", self.DEFAULT_START_GCODE)
        start_gcode = ""
        if start_gcode_raw.strip():
            start_gcode = start_gcode_raw.replace(
                "{nozzle_temp}", str(int(nozzle_temp))
            ).replace("{bed_temp}", str(int(bed_temp)))

            # Periodic bed probing: skip G29 if probed recently.
            # M420 S1 (already in default start gcode) loads the saved
            # mesh from EEPROM, so skipping G29 is safe.
            if any(l.strip().startswith("G29") for l in start_gcode.splitlines()):
                probe_interval = float(
                    await get_setting("bed_probe_interval_hours", "24")
                )
                last_probe = float(
                    await get_setting("last_bed_probe_timestamp", "0")
                )
                hours_since = (_time.time() - last_probe) / 3600

                if probe_interval > 0 and hours_since < probe_interval:
                    start_gcode = "\n".join(
                        l for l in start_gcode.splitlines()
                        if not l.strip().startswith("G29")
                    )
                    logger.info(
                        "Skipping G29 (probed %.1fh ago, interval %.0fh)",
                        hours_since, probe_interval,
                    )
                    self._notify_terminal(
                        f"[SYSTEM] Skipping bed probe (last probed {hours_since:.1f}h ago) — using saved mesh",
                        "system",
                    )
                else:
                    await set_setting(
                        "last_bed_probe_timestamp", str(_time.time())
                    )
                    logger.info(
                        "Running G29 (last probe %.1fh ago, interval %.0fh)",
                        hours_since, probe_interval,
                    )

            self._notify_terminal("[SYSTEM] Running start G-code...", "system")

        # Store selected spool for filament deduction on completion
        self._current_spool_id = spool_id

        # Reset line numbers on both sides to prevent "Resend: N" errors
        # after E-Stop/power cycle sequences where counters desync.
        self._protocol.reset_line_number()
        await self._queue.enqueue("M110 N0", CommandPriority.SYSTEM)
        self._safety.record_serial_activity()

        # Start timelapse recording
        if self._timelapse:
            await self._timelapse.start_recording(filepath.name)
            # Register layer change callback for frame capture
            if self._timelapse.is_recording:

                def _on_layer(layer: int) -> None:
                    if self._timelapse and self._timelapse.is_recording:
                        asyncio.create_task(self._timelapse.capture_frame())

                self._sender.add_layer_callback(_on_layer)
                # Stash ref so we can remove it later
                self._timelapse_layer_cb = _on_layer

        # Pass start gcode to sender — it runs asynchronously in the print
        # task so this method returns immediately without blocking the API.
        await self._sender.start_print(filepath, start_gcode=start_gcode)
        self.state.status = PrinterStatus.PRINTING

        # Record print job in history
        from ..storage.models import create_print_job, update_job_estimated_seconds

        try:
            self._current_job_id = await create_print_job(
                filename=filepath.name,
                total_lines=self._sender.total_lines,
                hotend_target=self.state.hotend_target,
                bed_target=self.state.bed_target,
            )
            if self._slicer_estimated_seconds > 0 and self._current_job_id:
                await update_job_estimated_seconds(
                    self._current_job_id, self._slicer_estimated_seconds
                )
        except Exception:
            logger.exception("Failed to record print job start")

        self._notify_state_change()

    async def pause_print(self) -> None:
        """Pause the current print."""
        if self._sender:
            await self._sender.pause()
            self.state.status = PrinterStatus.PAUSED
            self._notify_state_change()

    async def resume_print(self) -> None:
        """Resume a paused print."""
        if self._sender:
            await self._sender.resume()
            self.state.status = PrinterStatus.PRINTING
            self._notify_state_change()

    async def cancel_print(self) -> None:
        """Cancel the current print."""
        if self._sender:
            # Stop timelapse (mark as failed)
            await self._stop_timelapse(success=False)

            # Capture filament usage before cancel/reset clears state
            filament_used = self._sender._filament_used_mm
            elapsed = self._sender.elapsed_seconds
            lines = self._sender.current_line

            # Record cancellation in history
            if self._current_job_id:
                from ..storage.models import complete_print_job

                try:
                    await complete_print_job(
                        job_id=self._current_job_id,
                        status="cancelled",
                        duration_seconds=int(elapsed),
                        lines_printed=lines,
                        filament_used_mm=filament_used,
                    )
                except Exception:
                    logger.exception("Failed to record print cancellation")
                self._current_job_id = None

            # Deduct filament actually used before cancellation
            await self._deduct_filament(filament_used)
            self._current_spool_id = None

            await self._sender.cancel()
            self._sender.reset()
            self.state.status = PrinterStatus.IDLE
            self.state.current_file = None
            self._notify_state_change()

    async def emergency_stop(self) -> None:
        """Send M112 emergency stop. Printer must be power-cycled after."""
        logger.critical("EMERGENCY STOP triggered")
        # Send M112 directly through protocol (bypass queue for speed)
        if self._protocol:
            try:
                await self._protocol.send_command("M112")
            except Exception:
                pass
        if self._sender and self._sender.is_printing:
            self._sender._cancelled = True
        if self._queue:
            await self._queue.clear()
        self.state.status = PrinterStatus.ERROR
        self.state.error_message = (
            "Emergency stop activated. Power cycle the printer to continue."
        )
        self._notify_state_change()

    async def disable_motors(self) -> None:
        """Disable stepper motors."""
        await self.send_command("M84")

    async def _deduct_filament(self, filament_used_mm: float) -> None:
        """Deduct filament from the selected spool (or active spool fallback).

        Called on ALL print endings — success, cancel, or failure — so that
        filament tracking stays accurate regardless of outcome.
        """
        import math

        from ..storage.models import (
            deduct_filament,
            get_active_spool,
            get_setting,
            get_spool,
        )

        logger.info(
            "Filament deduction: %.1fmm extruded, spool_id=%s",
            filament_used_mm,
            self._current_spool_id,
        )
        if filament_used_mm <= 0:
            logger.info("No filament usage tracked (0mm extruded)")
            return

        try:
            spool = None
            if self._current_spool_id:
                spool = await get_spool(self._current_spool_id)
            if not spool:
                spool = await get_active_spool()
            if not spool:
                logger.warning(
                    "No spool found for filament deduction "
                    "(spool_id=%s, no active spool)",
                    self._current_spool_id,
                )
                return

            density = float(await get_setting("filament_density", "1.24"))
            radius_mm = 1.75 / 2.0
            volume_mm3 = math.pi * radius_mm * radius_mm * filament_used_mm
            grams = volume_mm3 / 1000.0 * density
            await deduct_filament(spool["id"], grams)
            logger.info(
                "Deducted %.1fg (%.0fmm) from spool '%s' (id=%d)",
                grams,
                filament_used_mm,
                spool["name"],
                spool["id"],
            )
        except Exception:
            logger.exception("Failed to deduct filament")

    async def _stop_timelapse(self, success: bool = True) -> None:
        """Stop timelapse recording and remove the layer callback."""
        if self._sender and hasattr(self, "_timelapse_layer_cb"):
            self._sender.remove_layer_callback(self._timelapse_layer_cb)
            del self._timelapse_layer_cb

        if self._timelapse and self._timelapse.is_recording:
            self._notify_terminal("[SYSTEM] Assembling timelapse video...", "system")
            video = await self._timelapse.stop_recording(success=success)
            if video:
                self._notify_terminal(f"[SYSTEM] Timelapse saved: {video}", "system")
            else:
                self._notify_terminal(
                    "[SYSTEM] Timelapse: not enough frames or assembly failed",
                    "system",
                )

    async def _on_print_complete(
        self,
        elapsed_seconds: float = 0,
        lines_printed: int = 0,
        filament_used_mm: float = 0,
    ) -> None:
        """Handle post-print actions (cooldown, filament deduction, history, notifications).

        Each action is isolated in its own try/except so that a failure in
        one step (e.g. end G-code or timelapse) cannot prevent filament
        deduction or history recording from running.
        """
        from ..storage.models import complete_print_job, get_setting

        # 1. Stop timelapse recording
        try:
            await self._stop_timelapse(success=True)
        except Exception:
            logger.exception("Error stopping timelapse after print")

        # 2. Run end G-code (retract, present, cool down, disable motors)
        try:
            end_gcode = await get_setting("end_gcode", self.DEFAULT_END_GCODE)
            if end_gcode.strip():
                self._notify_terminal("[SYSTEM] Running end G-code...", "system")
                await self._run_gcode_sequence(end_gcode, 0, 0)

            cooldown = await get_setting("post_print_cooldown", "true")
            if cooldown == "true" and not end_gcode.strip():
                logger.info("Post-print cooldown: turning off heaters")
                if self._queue:
                    await self._queue.enqueue("M104 S0", CommandPriority.SYSTEM)
                    await self._queue.enqueue("M140 S0", CommandPriority.SYSTEM)
        except Exception:
            logger.exception("Error running end G-code")

        # 3. Deduct filament — MUST run regardless of end-gcode outcome
        try:
            await self._deduct_filament(filament_used_mm)
        except Exception:
            logger.exception("Error deducting filament after print")
        finally:
            self._current_spool_id = None

        # 4. Record completion in history — MUST run regardless of above
        try:
            if self._current_job_id:
                await complete_print_job(
                    job_id=self._current_job_id,
                    status="completed",
                    duration_seconds=int(elapsed_seconds),
                    lines_printed=lines_printed,
                    filament_used_mm=filament_used_mm,
                )
                self._current_job_id = None
        except Exception:
            logger.exception("Error recording print completion in history")

        self._notify_terminal("[SYSTEM] Print complete", "system")

    async def _safety_loop(self) -> None:
        """Periodic safety checks and print state updates."""
        try:
            tick = 0
            while True:
                await asyncio.sleep(1.0)
                tick += 1

                # --- Timelapse state sync ---
                if self._timelapse:
                    self.state.timelapse_recording = self._timelapse.is_recording
                    self.state.timelapse_frame_count = self._timelapse.frame_count
                    self.state.timelapse_assembling = self._timelapse.is_assembling

                # --- Print state updates ---
                if self._sender and self._sender.is_printing:
                    self.state.current_file = self._sender.current_file
                    self.state.print_progress = self._sender.progress
                    self.state.elapsed_seconds = self._sender.elapsed_seconds

                    # Use corrected slicer estimate if available, else linear
                    if self._slicer_estimated_seconds > 0 and self._sender.progress > 0:
                        corrected_total = (
                            self._slicer_estimated_seconds
                            * self._time_correction_factor
                        )
                        self.state.estimated_remaining = max(
                            0,
                            corrected_total - self._sender.elapsed_seconds,
                        )
                    else:
                        self.state.estimated_remaining = (
                            self._sender.estimated_remaining
                        )
                    self.state.current_layer = self._sender.current_layer
                    self.state.total_layers = self._sender.total_layers
                    self.state.current_line = self._sender.current_line
                    self.state.total_lines = self._sender.total_lines
                    self._notify_state_change()

                # --- Print completion / abort detection ---
                # NOTE: This MUST be outside the is_printing guard above!
                # is_printing returns False once the async task finishes, so
                # checking for task.done() inside that block would never fire.
                if (
                    self._sender
                    and self._sender._task
                    and self._sender._task.done()
                    and self.state.status
                    in (PrinterStatus.PRINTING, PrinterStatus.PAUSED)
                ):
                    was_cancelled = self._sender._cancelled

                    if not was_cancelled:
                        # Normal completion — run end gcode and cleanup
                        logger.info("Print task completed, running post-print actions")
                        self.state.status = PrinterStatus.FINISHING
                        self._notify_state_change()
                        _elapsed = self._sender.elapsed_seconds
                        _lines = self._sender.current_line
                        _filament = self._sender._filament_used_mm
                        self._sender.reset()
                        try:
                            await self._on_print_complete(_elapsed, _lines, _filament)
                        except Exception:
                            logger.exception("Error in post-print actions")
                        self.state.status = PrinterStatus.IDLE
                    else:
                        # Aborted due to consecutive failures
                        aborted_in_start = self._sender.in_start_gcode
                        logger.warning(
                            "Print task aborted (cancelled=%s, in_start_gcode=%s)",
                            was_cancelled,
                            aborted_in_start,
                        )
                        # Stop timelapse on abort
                        await self._stop_timelapse(success=False)
                        _filament = self._sender._filament_used_mm
                        # Deduct filament used before the abort
                        await self._deduct_filament(_filament)
                        # Record failure in history
                        if self._current_job_id:
                            from ..storage.models import complete_print_job

                            try:
                                await complete_print_job(
                                    job_id=self._current_job_id,
                                    status="failed",
                                    duration_seconds=int(self._sender.elapsed_seconds),
                                    lines_printed=self._sender.current_line,
                                    filament_used_mm=_filament,
                                )
                            except Exception:
                                logger.exception("Failed to record print abort")
                            self._current_job_id = None
                        self._current_spool_id = None
                        self._sender.reset()

                        if aborted_in_start:
                            error_msg = (
                                "Print aborted: start G-code commands failed — "
                                "printer may need reconnection or power cycle"
                            )
                            self._error_log.log_system_error(
                                "Start G-code Failed",
                                "Multiple consecutive start G-code commands were "
                                "rejected by the printer. The print was safely "
                                "aborted before any movement occurred. Try "
                                "disconnecting and reconnecting, or power cycle "
                                "the printer.",
                            )
                        else:
                            error_msg = (
                                "Print aborted: communication lost with printer"
                            )
                            self._error_log.log_system_error(
                                "Print Communication Lost",
                                "Too many consecutive commands failed during "
                                "printing. The printer may have disconnected.",
                            )
                        self.state.status = PrinterStatus.ERROR
                        self.state.error_message = error_msg

                    # Clear print state in both cases
                    self.state.current_file = None
                    self.state.print_progress = 0.0
                    self.state.elapsed_seconds = 0.0
                    self.state.estimated_remaining = 0.0
                    self.state.current_layer = 0
                    self.state.total_layers = 0
                    self.state.current_line = 0
                    self.state.total_lines = 0
                    self._notify_state_change()

                # --- Serial watchdog — check every 5 seconds ---
                # Skip during start gcode since G28/G29/M109/M190 can block
                # for minutes with no intermediate serial output.
                if tick % 5 == 0:
                    is_printing = self.state.status == PrinterStatus.PRINTING
                    in_start_gcode = self._sender and self._sender.in_start_gcode
                    if is_printing and not in_start_gcode:
                        alert = self._safety.check_serial_watchdog(is_printing=True)
                        if alert:
                            self._handle_safety_alert(alert)

                # --- Keep-alive & fallback temperature polling ---
                # Sends M105 to serve two purposes:
                # 1. Ensures temperature data when M155 auto-report stops
                # 2. Keeps USB serial active to prevent Linux autosuspend
                #    which causes DTR resets and BLTouch errors after idle
                #
                # During printing: only poll if M155 data is stale (>15s)
                # During idle: poll every 30s to keep USB alive
                if self._queue and not self._kill_recovery_in_progress:
                    is_idle = self.state.status in (
                        PrinterStatus.IDLE,
                        PrinterStatus.ERROR,
                    )
                    last_temp_age = (
                        _time.time() - self._temp_monitor.hotend.timestamp
                        if self._temp_monitor.hotend.timestamp > 0
                        else float("inf")
                    )

                    should_poll = False
                    if is_idle and tick % 30 == 0:
                        # Idle keep-alive: every 30 seconds
                        should_poll = True
                    elif tick % 10 == 0 and last_temp_age > 15.0:
                        # Fallback: every 10s when M155 data is stale
                        should_poll = True

                    if should_poll:
                        try:
                            await self._queue.enqueue(
                                "M105", CommandPriority.SYSTEM
                            )
                        except Exception:
                            pass

        except asyncio.CancelledError:
            pass

"""High-level printer controller.

Orchestrates serial connection, command queue, temperature monitoring,
safety checks, and G-code sending. This is the main interface used by
the API layer.
"""

import asyncio
import glob
import logging
from pathlib import Path
from typing import Callable, Optional

from ..serial.command_queue import CommandPriority, CommandQueue
from ..serial.connection import SerialConnection
from ..serial.gcode_sender import GcodeSender
from ..serial.protocol import CommandResult, MarlinProtocol
from ..serial.safety import SafetyAction, SafetyAlert, SafetyMonitor
from ..serial.temperature import TemperatureMonitor, TemperatureSnapshot
from .state import PrinterState, PrinterStatus

logger = logging.getLogger(__name__)


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
        self._state_callbacks: list[Callable[[], None]] = []
        self._terminal_callbacks: list[Callable[[str, str], None]] = []
        # Print time correction
        self._slicer_estimated_seconds: float = 0.0
        self._time_correction_factor: float = 1.0
        # Current print job ID for history tracking
        self._current_job_id: Optional[int] = None

    @property
    def temp_monitor(self) -> TemperatureMonitor:
        return self._temp_monitor

    @property
    def safety_monitor(self) -> SafetyMonitor:
        return self._safety

    @property
    def sender(self) -> Optional[GcodeSender]:
        return self._sender

    def add_state_callback(self, callback: Callable[[], None]) -> None:
        """Register a callback for state changes (used by WebSocket)."""
        self._state_callbacks.append(callback)

    def remove_state_callback(self, callback: Callable[[], None]) -> None:
        if callback in self._state_callbacks:
            self._state_callbacks.remove(callback)

    def add_terminal_callback(
        self, callback: Callable[[str, str], None]
    ) -> None:
        """Register callback for terminal lines. callback(line, direction)."""
        self._terminal_callbacks.append(callback)

    def remove_terminal_callback(
        self, callback: Callable[[str, str], None]
    ) -> None:
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
        self._notify_terminal(line, direction)

    def _on_position_line(self, line: str) -> None:
        """Called when position report is received."""
        import re
        match = re.search(r"X:([\d.-]+)\s*Y:([\d.-]+)\s*Z:([\d.-]+)", line)
        if match:
            self.state.x = float(match.group(1))
            self.state.y = float(match.group(2))
            self.state.z = float(match.group(3))

    def _handle_safety_alert(self, alert: SafetyAlert) -> None:
        logger.warning("Safety alert: %s", alert.message)
        self._notify_terminal(f"[SAFETY] {alert.message}", "system")
        if alert.action == SafetyAction.EMERGENCY_STOP:
            asyncio.create_task(self.emergency_stop())
        elif alert.action == SafetyAction.PAUSE_PRINT:
            if self._sender and self._sender.is_printing:
                asyncio.create_task(self.pause_print())

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
            candidates = sorted(
                glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*")
            )
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

    async def connect(
        self, port: str = "/dev/ttyUSB0", baudrate: int = 115200
    ) -> bool:
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
        """Home specified axes."""
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
        """Relative move."""
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
        """Extrude or retract filament (negative length = retract)."""
        await self.send_command("G91")
        await self.send_command(f"G1 E{length} F{feedrate}")
        await self.send_command("G90")

    async def start_print(self, filepath: Path) -> None:
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

        self._protocol.reset_line_number()
        await self._sender.start_print(filepath)
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
            # Record cancellation in history before resetting
            if self._current_job_id:
                from ..storage.models import complete_print_job

                try:
                    await complete_print_job(
                        job_id=self._current_job_id,
                        status="cancelled",
                        duration_seconds=int(self._sender.elapsed_seconds),
                        lines_printed=self._sender.current_line,
                        filament_used_mm=self._sender._filament_used_mm,
                    )
                except Exception:
                    logger.exception("Failed to record print cancellation")
                self._current_job_id = None

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

    async def _on_print_complete(
        self,
        elapsed_seconds: float = 0,
        lines_printed: int = 0,
        filament_used_mm: float = 0,
    ) -> None:
        """Handle post-print actions (cooldown, filament deduction, history, notifications)."""
        import math

        from ..storage.models import (
            complete_print_job,
            deduct_filament,
            get_active_spool,
            get_setting,
        )

        try:
            cooldown = await get_setting("post_print_cooldown", "true")
            if cooldown == "true":
                logger.info("Post-print cooldown: turning off heaters")
                if self._queue:
                    await self._queue.enqueue("M104 S0", CommandPriority.SYSTEM)
                    await self._queue.enqueue("M140 S0", CommandPriority.SYSTEM)

            # Deduct filament from active spool
            if filament_used_mm > 0:
                spool = await get_active_spool()
                if spool:
                    density = float(await get_setting("filament_density", "1.24"))
                    radius_mm = 1.75 / 2.0
                    volume_mm3 = math.pi * radius_mm * radius_mm * filament_used_mm
                    grams = volume_mm3 / 1000.0 * density
                    await deduct_filament(spool["id"], grams)
                    logger.info("Deducted %.1fg from spool '%s'", grams, spool["name"])

            # Record completion in history
            if self._current_job_id:
                await complete_print_job(
                    job_id=self._current_job_id,
                    status="completed",
                    duration_seconds=int(elapsed_seconds),
                    lines_printed=lines_printed,
                    filament_used_mm=filament_used_mm,
                )
                self._current_job_id = None

            # Notify via terminal so WebSocket picks it up
            self._notify_terminal("[SYSTEM] Print complete", "system")
        except Exception:
            logger.exception("Error in post-print actions")

    async def _safety_loop(self) -> None:
        """Periodic safety checks."""
        try:
            while True:
                await asyncio.sleep(5.0)
                # Update print state
                if self._sender and self._sender.is_printing:
                    self.state.current_file = self._sender.current_file
                    self.state.print_progress = self._sender.progress
                    self.state.elapsed_seconds = self._sender.elapsed_seconds

                    # Use corrected slicer estimate if available, else linear
                    if (
                        self._slicer_estimated_seconds > 0
                        and self._sender.progress > 0
                    ):
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

                    # Check if print completed
                    if (
                        self._sender._task
                        and self._sender._task.done()
                        and not self._sender._cancelled
                    ):
                        self.state.status = PrinterStatus.IDLE
                        # Capture values before reset clears them
                        _elapsed = self._sender.elapsed_seconds
                        _lines = self._sender.current_line
                        _filament = self._sender._filament_used_mm
                        self._sender.reset()
                        # Post-print actions with captured data
                        asyncio.create_task(
                            self._on_print_complete(_elapsed, _lines, _filament)
                        )

                    self._notify_state_change()

                # Serial watchdog
                is_printing = self.state.status == PrinterStatus.PRINTING
                alert = self._safety.check_serial_watchdog(is_printing)
                if alert:
                    self._handle_safety_alert(alert)

        except asyncio.CancelledError:
            pass

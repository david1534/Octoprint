"""G-code file sender for print jobs.

Streams G-code line by line from disk through the command queue.
Handles pause, resume, and cancel operations with safe nozzle parking.
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import Optional

from .command_queue import CommandPriority, CommandQueue
from .protocol import CommandResult

logger = logging.getLogger(__name__)


class GcodeSender:
    """Streams G-code from a file through the command queue."""

    def __init__(self, command_queue: CommandQueue):
        self._queue = command_queue
        self._paused = False
        self._cancelled = False
        self._current_line = 0
        self._total_lines = 0
        self._current_file: Optional[str] = None
        self._start_time: Optional[float] = None
        self._pause_time: Optional[float] = None
        self._total_pause_duration: float = 0.0
        self._current_layer = 0
        self._total_layers = 0
        self._task: Optional[asyncio.Task] = None
        # Saved position for resume
        self._saved_x: float = 0
        self._saved_y: float = 0
        self._saved_z: float = 0
        self._saved_e: float = 0
        self._saved_feedrate: int = 1000
        # Filament usage tracking (mm of filament extruded)
        self._filament_used_mm: float = 0.0
        self._last_e_position: float = 0.0
        self._e_relative: bool = False
        # LCD progress display
        self._lcd_enabled: bool = False
        self._lcd_interval: int = 50  # lines between updates
        self._lcd_last_layer: int = -1
        # Whether start gcode preamble is currently running
        self._in_start_gcode: bool = False
        # Layer change callbacks (used by timelapse, etc.)
        self._layer_callbacks: list = []

    @property
    def is_printing(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def in_start_gcode(self) -> bool:
        return self._in_start_gcode

    @property
    def progress(self) -> float:
        if self._total_lines == 0:
            return 0.0
        return min(100.0, (self._current_line / self._total_lines) * 100)

    @property
    def current_line(self) -> int:
        return self._current_line

    @property
    def total_lines(self) -> int:
        return self._total_lines

    @property
    def current_layer(self) -> int:
        return self._current_layer

    @property
    def total_layers(self) -> int:
        return self._total_layers

    @property
    def current_file(self) -> Optional[str]:
        return self._current_file

    @property
    def elapsed_seconds(self) -> float:
        if self._start_time is None:
            return 0.0
        elapsed = time.time() - self._start_time - self._total_pause_duration
        # Subtract ongoing pause duration if currently paused
        if self._paused and self._pause_time:
            elapsed -= time.time() - self._pause_time
        return max(0.0, elapsed)

    @property
    def estimated_remaining(self) -> float:
        if self._current_line == 0 or self.elapsed_seconds == 0:
            return 0.0
        rate = self._current_line / self.elapsed_seconds
        remaining_lines = self._total_lines - self._current_line
        return remaining_lines / rate if rate > 0 else 0.0

    def add_layer_callback(self, callback) -> None:
        """Register a callback invoked on each layer change.

        The callback receives the new layer number (int).
        """
        self._layer_callbacks.append(callback)

    def remove_layer_callback(self, callback) -> None:
        if callback in self._layer_callbacks:
            self._layer_callbacks.remove(callback)

    def _notify_layer_change(self, layer: int) -> None:
        for cb in self._layer_callbacks:
            try:
                cb(layer)
            except Exception:
                logger.exception("Error in layer change callback")

    def configure_lcd(self, enabled: bool = False, interval: int = 50) -> None:
        """Configure LCD progress display (M117 messages)."""
        self._lcd_enabled = enabled
        self._lcd_interval = max(10, interval)

    async def start_print(self, filepath: Path, start_gcode: str = "") -> None:
        """Start printing a G-code file.

        Args:
            filepath: Path to the G-code file.
            start_gcode: Optional start G-code to run before the file
                         (homing, bed leveling, heating, purge line).
        """
        if self.is_printing:
            raise RuntimeError("A print is already in progress")

        self._current_file = filepath.name
        self._lcd_last_layer = -1
        self._paused = False
        self._cancelled = False
        self._current_line = 0
        self._current_layer = 0
        self._total_pause_duration = 0.0
        self._filament_used_mm = 0.0
        self._last_e_position = 0.0
        self._e_relative = False
        self._in_start_gcode = bool(start_gcode.strip())

        # Count printable lines and layers
        self._total_lines = 0
        self._total_layers = 0
        with open(filepath, "r") as f:
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith(";"):
                    self._total_lines += 1
                # Count layer changes (slicer comments)
                if ";LAYER:" in stripped or "; LAYER:" in stripped:
                    self._total_layers += 1

        self._start_time = time.time()
        self._task = asyncio.create_task(self._print_loop(filepath, start_gcode))
        logger.info(
            "Print started: %s (%d lines, %d layers)",
            filepath.name,
            self._total_lines,
            self._total_layers,
        )

    async def _print_loop(self, filepath: Path, start_gcode: str = "") -> None:
        """Stream G-code lines to the command queue."""
        try:
            # Run start G-code preamble (homing, leveling, heating, purge)
            if start_gcode.strip():
                logger.info("Running start G-code preamble...")
                preamble_start = time.time()
                consecutive_start_failures = 0
                max_start_failures = 3
                # Minimum expected duration (seconds) for commands that
                # involve physical movement — if they complete faster than
                # this, the response was almost certainly a phantom "ok".
                min_duration = {"G28": 5.0, "G29": 10.0}

                for raw_line in start_gcode.splitlines():
                    if self._cancelled:
                        await self._on_cancel()
                        return
                    # Respect pause during start gcode
                    while self._paused and not self._cancelled:
                        await asyncio.sleep(0.1)
                    if self._cancelled:
                        await self._on_cancel()
                        return
                    line = raw_line.strip()
                    if ";" in line:
                        line = line[: line.index(";")].strip()
                    if not line:
                        continue
                    cmd_start = time.time()
                    future = await self._queue.enqueue(
                        line, priority=CommandPriority.SYSTEM
                    )
                    result: CommandResult = await future
                    cmd_elapsed = time.time() - cmd_start
                    cmd_base = line.split()[0].upper() if line else ""

                    if not result.ok:
                        consecutive_start_failures += 1
                        logger.warning(
                            "Start gcode command failed (%d/%d): %s -> %s (%.1fs)",
                            consecutive_start_failures,
                            max_start_failures,
                            line,
                            result.error,
                            cmd_elapsed,
                        )
                        if consecutive_start_failures >= max_start_failures:
                            logger.critical(
                                "Aborting print: %d consecutive start gcode "
                                "failures — printer may not be responding",
                                consecutive_start_failures,
                            )
                            self._cancelled = True
                            await self._on_cancel()
                            return
                    else:
                        consecutive_start_failures = 0
                        logger.info(
                            "Start gcode OK: %s (%.1fs)", line, cmd_elapsed
                        )

                        # Sanity check: G28/G29 require physical movement.
                        # If they "succeed" in under min_duration seconds the
                        # response was a stale phantom "ok", not real.
                        expected = min_duration.get(cmd_base)
                        if expected and cmd_elapsed < expected:
                            logger.critical(
                                "Aborting print: %s completed in %.1fs "
                                "(expected >%.0fs) — phantom serial response "
                                "detected, printer did not actually execute "
                                "the command",
                                cmd_base,
                                cmd_elapsed,
                                expected,
                            )
                            self._cancelled = True
                            await self._on_cancel()
                            return

                    # Track filament used in start gcode (purge lines)
                    self._track_filament(line)

                preamble_elapsed = time.time() - preamble_start
                self._in_start_gcode = False
                logger.info(
                    "Start G-code complete (%.1fs), streaming file...",
                    preamble_elapsed,
                )

            consecutive_failures = 0
            max_consecutive_failures = 10

            # When PrintForge ran its own start gcode, skip ALL commands
            # embedded in the file by the slicer before the first ;LAYER:
            # marker. The slicer's start gcode (homing, heating, purge
            # lines, etc.) is fully redundant since PrintForge already
            # executed its own start sequence. Sending partial slicer
            # start gcode (only specific commands skipped) caused motors
            # to skip when leftover movement commands conflicted with
            # PrintForge's completed start sequence.
            skip_preamble = bool(start_gcode.strip())
            preamble_skipped = 0

            with open(filepath, "r") as f:
                for line in f:
                    if self._cancelled:
                        await self._on_cancel()
                        return

                    # Wait while paused
                    while self._paused and not self._cancelled:
                        await asyncio.sleep(0.1)
                    if self._cancelled:
                        await self._on_cancel()
                        return

                    stripped = line.strip()

                    # Track layer changes
                    if ";LAYER:" in stripped or "; LAYER:" in stripped:
                        if skip_preamble:
                            skip_preamble = False
                            if preamble_skipped > 0:
                                logger.info(
                                    "Skipped %d embedded preamble commands "
                                    "before first layer",
                                    preamble_skipped,
                                )
                        try:
                            layer_str = stripped.split("LAYER:")[-1].strip()
                            self._current_layer = int(layer_str) + 1
                        except ValueError:
                            self._current_layer += 1
                        self._notify_layer_change(self._current_layer)

                    # Skip empty lines and comments
                    if not stripped or stripped.startswith(";"):
                        continue

                    # Strip inline comments
                    if ";" in stripped:
                        stripped = stripped[: stripped.index(";")].strip()
                    if not stripped:
                        continue

                    # Skip ALL slicer-embedded commands before first layer
                    if skip_preamble:
                        preamble_skipped += 1
                        logger.debug(
                            "Skipping preamble command: %s", stripped
                        )
                        continue

                    # Send through command queue (plain G-code, no
                    # checksums — USB serial has its own CRC layer and
                    # the line-number system caused more failures than
                    # it prevented).
                    future = await self._queue.enqueue(
                        stripped,
                        priority=CommandPriority.PRINT,
                    )
                    # Wait for command to complete before sending next
                    result: CommandResult = await future
                    if not result.ok:
                        consecutive_failures += 1
                        logger.error(
                            "Print command failed at line %d (%d consecutive): %s -> %s",
                            self._current_line,
                            consecutive_failures,
                            stripped,
                            result.error,
                        )
                        if consecutive_failures >= max_consecutive_failures:
                            logger.critical(
                                "Aborting print: %d consecutive command failures — "
                                "printer may be disconnected",
                                consecutive_failures,
                            )
                            self._cancelled = True
                            await self._on_cancel()
                            return
                    else:
                        consecutive_failures = 0
                        # Only advance progress on success — prevents
                        # progress from racing to 100% if commands are
                        # being silently rejected by the printer.
                        self._current_line += 1

                    # Track filament usage from E values
                    self._track_filament(stripped)

                    # Send LCD progress update (M117)
                    if self._lcd_enabled and (
                        self._current_line % self._lcd_interval == 0
                        or self._current_layer != self._lcd_last_layer
                    ):
                        self._lcd_last_layer = self._current_layer
                        pct = self.progress
                        layer_str = (
                            f"L{self._current_layer}/{self._total_layers}"
                            if self._total_layers > 0
                            else ""
                        )
                        msg = f"M117 {layer_str} {pct:.0f}%".strip()
                        await self._queue.enqueue(msg, CommandPriority.PRINT)

            # Clear LCD at end
            if self._lcd_enabled:
                await self._queue.enqueue("M117 Print Complete", CommandPriority.PRINT)

            elapsed = time.time() - self._start_time if self._start_time else 0
            logger.info(
                "Print completed: %s (%d/%d lines in %.1fs)",
                filepath.name,
                self._current_line,
                self._total_lines,
                elapsed,
            )
        except asyncio.CancelledError:
            logger.info("Print task cancelled (CancelledError)")
        except Exception:
            logger.exception("Error during print (unhandled exception)")

    async def pause(self) -> None:
        """Pause the print with safe nozzle parking."""
        if not self.is_printing or self._paused:
            return
        self._paused = True
        self._pause_time = time.time()
        self._queue.pause()

        # Safe parking sequence
        # Retract filament slightly to prevent ooze
        await self._queue.enqueue("G91", CommandPriority.SYSTEM)
        await self._queue.enqueue("G1 E-2 F1800", CommandPriority.SYSTEM)
        # Lift Z to clear the print
        await self._queue.enqueue("G1 Z5 F600", CommandPriority.SYSTEM)
        await self._queue.enqueue("G90", CommandPriority.SYSTEM)
        # Park to front-left corner
        await self._queue.enqueue("G1 X5 Y5 F3000", CommandPriority.SYSTEM)

        logger.info("Print paused at line %d", self._current_line)

    async def resume(self) -> None:
        """Resume the print from paused state."""
        if not self.is_printing or not self._paused:
            return

        # Return to print position
        # Move back to X/Y first (Z stays lifted)
        await self._queue.enqueue("G90", CommandPriority.SYSTEM)
        # Lower Z back (relative -5 to undo the lift)
        await self._queue.enqueue("G91", CommandPriority.SYSTEM)
        await self._queue.enqueue("G1 Z-5 F600", CommandPriority.SYSTEM)
        # Prime filament (push back what we retracted)
        await self._queue.enqueue("G1 E2 F1800", CommandPriority.SYSTEM)
        await self._queue.enqueue("G90", CommandPriority.SYSTEM)

        if self._pause_time:
            self._total_pause_duration += time.time() - self._pause_time
        self._paused = False
        self._queue.resume()
        logger.info("Print resumed at line %d", self._current_line)

    async def cancel(self) -> None:
        """Cancel the current print."""
        if not self.is_printing:
            return
        self._cancelled = True
        self._paused = False
        self._queue.resume()
        # Wait for the print task to finish its cleanup
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=10.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._task.cancel()
        logger.info("Print cancelled")

    async def _on_cancel(self) -> None:
        """Clean up after cancellation."""
        await self._queue.clear()
        # Retract, lift, and cool down
        await self._queue.enqueue("G91", CommandPriority.SYSTEM)
        await self._queue.enqueue("G1 E-5 F1800", CommandPriority.SYSTEM)
        await self._queue.enqueue("G1 Z10 F600", CommandPriority.SYSTEM)
        await self._queue.enqueue("G90", CommandPriority.SYSTEM)
        await self._queue.enqueue("G28 X Y", CommandPriority.SYSTEM)
        # Turn off heaters
        await self._queue.enqueue("M104 S0", CommandPriority.SYSTEM)
        await self._queue.enqueue("M140 S0", CommandPriority.SYSTEM)
        # Turn off fan
        await self._queue.enqueue("M106 S0", CommandPriority.SYSTEM)
        # Disable steppers after a delay
        await self._queue.enqueue("M84", CommandPriority.SYSTEM)

    def _track_filament(self, command: str) -> None:
        """Track filament usage from G0/G1 E values."""
        import re

        upper = command.upper()

        # Detect relative/absolute extrusion mode
        if upper.startswith("M83"):
            self._e_relative = True
            return
        if upper.startswith("M82"):
            self._e_relative = False
            return
        # G92 E0 resets extruder position
        if upper.startswith("G92"):
            match = re.search(r"E([-\d.]+)", upper)
            if match:
                self._last_e_position = float(match.group(1))
            return

        # Only track G0/G1 moves with E parameter
        if not (
            upper.startswith("G0 ")
            or upper.startswith("G1 ")
            or upper.startswith("G0\t")
            or upper.startswith("G1\t")
        ):
            return

        match = re.search(r"E([-\d.]+)", upper)
        if not match:
            return

        e_value = float(match.group(1))
        if self._e_relative:
            if e_value > 0:
                self._filament_used_mm += e_value
        else:
            delta = e_value - self._last_e_position
            if delta > 0:
                self._filament_used_mm += delta
            self._last_e_position = e_value

    def reset(self) -> None:
        """Reset state after print completes or is cancelled.

        NOTE: _filament_used_mm is intentionally NOT reset here so that
        _on_print_complete() can read it after reset is called.
        """
        self._current_file = None
        self._current_line = 0
        self._total_lines = 0
        self._current_layer = 0
        self._total_layers = 0
        self._start_time = None
        self._paused = False
        self._cancelled = False
        self._in_start_gcode = False
        self._task = None
        self._layer_callbacks.clear()

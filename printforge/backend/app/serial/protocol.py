"""Marlin serial protocol handler.

Implements the send-acknowledge protocol, line numbering, checksums,
and error recovery (resend requests). This is the most critical file
in the project.
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field

from .connection import SerialConnection

logger = logging.getLogger(__name__)


# Marlin's host-keepalive output explicitly distinguishes a printer that has
# gone silent from one that is intentionally waiting for the operator.  Once
# one of these signals is seen, the current command must stay in flight until
# Marlin finally replies with ``ok``; sending another print line while an M600
# dialog is active can make the host run ahead and eventually abort the job.
_USER_WAIT_RE = re.compile(
    r"(busy:\s*paused\s+for\s+(user|input)|"
    r"action:(out_of_filament|filament_runout|filament_change|prompt_begin))",
    re.IGNORECASE,
)
_USER_WAIT_COMMANDS = {"M0", "M1", "M600"}


class PrinterError(Exception):
    pass


@dataclass
class CommandResult:
    command: str
    ok: bool
    response_lines: list[str] = field(default_factory=list)
    error: str | None = None


class MarlinProtocol:
    def __init__(self, connection: SerialConnection):
        self._conn = connection
        self._line_number = 0
        self._last_numbered_line: str = ""
        self.default_timeout = 10.0
        self.long_timeout = 300.0
        self._long_commands = {"G28", "G29", "M109", "M190", "M303"}
        self._temp_callbacks: list = []
        self._terminal_callbacks: list = []
        self._position_callbacks: list = []

    @property
    def line_number(self) -> int:
        return self._line_number

    def reset_line_number(self) -> None:
        """Reset the local line-number counter to zero.

        Call this only when Marlin is known to be at zero already (e.g.
        right after a USB-serial connect resets the board).  For runtime
        resets (between prints), send ``M110 N0`` through the command
        queue instead — ``send_command`` auto-detects M110 and syncs the
        counter so both sides stay in lock-step.
        """
        self._line_number = 0

    def add_temp_callback(self, callback) -> None:
        self._temp_callbacks.append(callback)

    def remove_temp_callback(self, callback) -> None:
        if callback in self._temp_callbacks:
            self._temp_callbacks.remove(callback)

    def add_terminal_callback(self, callback) -> None:
        self._terminal_callbacks.append(callback)

    def remove_terminal_callback(self, callback) -> None:
        if callback in self._terminal_callbacks:
            self._terminal_callbacks.remove(callback)

    def add_position_callback(self, callback) -> None:
        self._position_callbacks.append(callback)

    def _compute_checksum(self, line: str) -> int:
        checksum = 0
        for char in line:
            checksum ^= ord(char)
        return checksum & 0xFF

    def _add_line_number(self, command: str) -> str:
        self._line_number += 1
        line = f"N{self._line_number} {command}"
        checksum = self._compute_checksum(line)
        result = f"{line}*{checksum}"
        self._last_numbered_line = result
        return result

    def _get_timeout(self, command: str) -> float:
        cmd_base = command.split()[0].upper() if command else ""
        if cmd_base in self._long_commands:
            return self.long_timeout
        return self.default_timeout

    @staticmethod
    def _is_user_wait_command(command: str) -> bool:
        """Return whether a command intentionally waits for LCD input."""
        cmd_base = command.split()[0].upper() if command else ""
        return cmd_base in _USER_WAIT_COMMANDS

    @staticmethod
    def _is_user_wait_signal(line: str) -> bool:
        """Return whether Marlin says it is intentionally waiting for input."""
        return bool(_USER_WAIT_RE.search(line))

    async def send_command(
        self, command: str, with_checksum: bool = False, timeout: float | None = None
    ) -> CommandResult:
        original_command = command.strip()
        if with_checksum:
            wire_command = self._add_line_number(original_command)
        else:
            wire_command = original_command
        if timeout is None:
            timeout = self._get_timeout(original_command)
        self._emit_terminal(original_command, "send")
        try:
            await self._conn.send(wire_command)
        except ConnectionError as e:
            return CommandResult(command=original_command, ok=False, error=str(e))
        response_lines = []
        max_retries = 3
        retry_count = 0
        waiting_for_user = self._is_user_wait_command(original_command)
        # Total wall-clock deadline for this command. The per-read timeout
        # resets every time data arrives (e.g. M155 temp reports), so a
        # command can hang forever if the printer sends temp data but never
        # "ok". This deadline catches that case. The one intentional exception
        # is an LCD/user-input wait (such as M600): Marlin's keepalive signal
        # proves it is alive, and the command must remain open until the user
        # completes the firmware-controlled resume sequence.
        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if not waiting_for_user and remaining <= 0:
                return CommandResult(
                    command=original_command,
                    ok=False,
                    response_lines=response_lines,
                    error=f"Timeout after {timeout}s (no ok received)",
                )
            read_timeout = (
                self.default_timeout if waiting_for_user else min(remaining, self.default_timeout)
            )
            try:
                line = await self._conn.read_line(timeout=read_timeout)
            except TimeoutError:
                if waiting_for_user:
                    # A physical filament swap has no useful upper time limit.
                    # Keep polling so disconnect() can still cancel the queue
                    # task and a real serial failure can still surface.
                    continue
                return CommandResult(
                    command=original_command,
                    ok=False,
                    response_lines=response_lines,
                    error=f"Timeout after {timeout}s",
                )
            except ConnectionError as e:
                return CommandResult(
                    command=original_command, ok=False, response_lines=response_lines, error=str(e)
                )
            if not line:
                continue
            self._emit_terminal(line, "recv")
            if not waiting_for_user and self._is_user_wait_signal(line):
                waiting_for_user = True
                logger.info(
                    "Printer is waiting for user input; holding command open: %s",
                    original_command,
                )
            if self._is_temp_report(line):
                self._emit_temp(line)
                if not line.startswith("ok"):
                    continue
            if line.startswith("X:") and "Y:" in line and "Z:" in line:
                self._emit_position(line)
                response_lines.append(line)
                continue
            if line.startswith("ok"):
                # Auto-sync line counter when M110 succeeds so the next
                # checksummed command uses the right sequence number.
                if original_command.upper().startswith("M110"):
                    match = re.search(r"N(\d+)", original_command, re.IGNORECASE)
                    self._line_number = int(match.group(1)) if match else 0
                    logger.info("Line number reset to %d (M110)", self._line_number)
                return CommandResult(
                    command=original_command, ok=True, response_lines=response_lines
                )
            if line.lower().startswith("resend:") or line.lower().startswith("rs:"):
                retry_count += 1
                if retry_count > max_retries:
                    return CommandResult(
                        command=original_command,
                        ok=False,
                        response_lines=response_lines,
                        error=f"Checksum failed after {max_retries} retries",
                    )
                logger.warning("Resend requested: %s (retry %d)", line, retry_count)
                if self._last_numbered_line:
                    await self._conn.send(self._last_numbered_line)
                continue
            if line.startswith("Error:"):
                error_msg = line[6:].strip()
                logger.error("Printer error: %s", error_msg)
                # Marlin often follows error responses with
                # "Resend: N\nok".  Drain those trailing lines so
                # they don't contaminate the next command's read loop.
                for _ in range(5):
                    try:
                        drain = await self._conn.read_line(timeout=0.1)
                        if drain:
                            self._emit_terminal(drain, "recv")
                            if self._is_temp_report(drain):
                                self._emit_temp(drain)
                            if drain.startswith("ok"):
                                break
                    except (TimeoutError, ConnectionError):
                        break
                return CommandResult(
                    command=original_command,
                    ok=False,
                    response_lines=response_lines,
                    error=error_msg,
                )
            response_lines.append(line)

    def _is_temp_report(self, line: str) -> bool:
        return " T:" in line or line.startswith("T:") or " T0:" in line or line.startswith("T0:")

    def _emit_temp(self, line: str) -> None:
        for cb in self._temp_callbacks:
            try:
                cb(line)
            except Exception:
                logger.exception("Error in temp callback")

    def _emit_terminal(self, line: str, direction: str) -> None:
        for cb in self._terminal_callbacks:
            try:
                cb(line, direction)
            except Exception:
                logger.exception("Error in terminal callback")

    def _emit_position(self, line: str) -> None:
        for cb in self._position_callbacks:
            try:
                cb(line)
            except Exception:
                logger.exception("Error in position callback")

    async def query_firmware(self) -> str:
        result = await self.send_command("M115")
        if result.ok and result.response_lines:
            for line in result.response_lines:
                if "FIRMWARE_NAME:" in line:
                    match = re.search(r"FIRMWARE_NAME:([^\s]+)", line)
                    if match:
                        return match.group(1)
                    return line
        return "Unknown"

    async def drain_unsolicited(self) -> None:
        """Read and process any unsolicited serial data (e.g. M155 auto-reports).

        Called by the command queue during idle periods so that temperature
        auto-reports, position updates, and other asynchronous printer output
        are processed even when no commands are being sent.
        """
        while True:
            try:
                line = await self._conn.read_line(timeout=0.1)
            except TimeoutError:
                break
            except ConnectionError:
                break
            if not line:
                continue
            self._emit_terminal(line, "recv")
            if self._is_temp_report(line):
                self._emit_temp(line)
            if line.startswith("X:") and "Y:" in line and "Z:" in line:
                self._emit_position(line)

    async def enable_auto_temp_report(self, interval: int = 2) -> None:
        await self.send_command(f"M155 S{interval}")

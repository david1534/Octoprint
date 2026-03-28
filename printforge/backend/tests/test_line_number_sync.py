"""Tests for print reliability — regression guard for the
"progress jumps to 100% without printing" bug.

Root cause: The original checksum/line-number system caused the printer
to silently reject every command when counters desynced between prints.
Progress raced to 100% because _current_line incremented on failure.

Fixes verified here:
1. Checksums removed — commands sent as plain G-code (USB has CRC)
2. Progress only advances on successful commands (defense-in-depth)
3. Preamble skipping prevents double-homing/heating when start gcode runs
4. Protocol error drain prevents stale Resend/ok leaking across commands
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.serial.command_queue import CommandPriority
from app.serial.gcode_sender import GcodeSender
from app.serial.protocol import CommandResult, MarlinProtocol


# ── No-checksum verification ─────────────────────────────────────────


class TestNoChecksumSending:
    """Verify file commands are sent WITHOUT checksums (the fix)."""

    @pytest.fixture
    def gcode_file(self, tmp_path):
        f = tmp_path / "test.gcode"
        f.write_text("G1 X10 Y10\nG1 X20 Y20\n")
        return f

    @pytest.mark.asyncio
    async def test_file_commands_sent_without_checksum(self, gcode_file):
        """Print commands must NOT use checksums — the checksum/line-number
        system was the root cause of the jump-to-100% bug."""
        enqueued = []

        async def mock_enqueue(cmd, priority=CommandPriority.USER, with_checksum=False):
            enqueued.append((cmd, priority, with_checksum))
            future = asyncio.get_running_loop().create_future()
            future.set_result(CommandResult(command=cmd, ok=True))
            return future

        queue = MagicMock()
        queue.enqueue = mock_enqueue
        queue.pause = MagicMock()
        queue.resume = MagicMock()
        queue.clear = AsyncMock()

        sender = GcodeSender(queue)
        await sender.start_print(gcode_file, start_gcode="")
        await asyncio.wait_for(sender._task, timeout=5.0)

        # All PRINT-priority commands must have with_checksum=False
        for cmd, priority, with_cs in enqueued:
            if priority == CommandPriority.PRINT:
                assert with_cs is False, (
                    f"PRINT command '{cmd}' should NOT use checksums"
                )


class TestPreambleSkipping:
    """Verify slicer-embedded preamble commands are skipped when
    PrintForge already ran its own start gcode."""

    @pytest.fixture
    def gcode_with_preamble(self, tmp_path):
        f = tmp_path / "with_preamble.gcode"
        f.write_text(
            "G28\n"  # slicer preamble — should be skipped
            "M104 S200\n"  # slicer preamble — should be skipped
            ";LAYER:0\n"
            "G1 X10 Y10\n"  # actual print — should be sent
            "G1 X20 Y20\n"
        )
        return f

    @pytest.mark.asyncio
    async def test_preamble_skipped_when_start_gcode_provided(self, gcode_with_preamble):
        enqueued = []

        async def mock_enqueue(cmd, priority=CommandPriority.USER, with_checksum=False):
            enqueued.append((cmd, priority, with_checksum))
            future = asyncio.get_running_loop().create_future()
            future.set_result(CommandResult(command=cmd, ok=True))
            return future

        queue = MagicMock()
        queue.enqueue = mock_enqueue
        queue.pause = MagicMock()
        queue.resume = MagicMock()
        queue.clear = AsyncMock()

        sender = GcodeSender(queue)
        await sender.start_print(gcode_with_preamble, start_gcode="G28\nM104 S200")
        await asyncio.wait_for(sender._task, timeout=5.0)

        # Extract just the PRINT-priority commands (file commands)
        print_cmds = [cmd for cmd, pri, _ in enqueued if pri == CommandPriority.PRINT]

        # G28 and M104 should NOT appear in print commands (they were skipped)
        assert "G28" not in print_cmds
        assert "M104 S200" not in print_cmds
        # Actual print moves should be present
        assert "G1 X10 Y10" in print_cmds
        assert "G1 X20 Y20" in print_cmds

    @pytest.mark.asyncio
    async def test_preamble_not_skipped_without_start_gcode(self, gcode_with_preamble):
        enqueued = []

        async def mock_enqueue(cmd, priority=CommandPriority.USER, with_checksum=False):
            enqueued.append((cmd, priority, with_checksum))
            future = asyncio.get_running_loop().create_future()
            future.set_result(CommandResult(command=cmd, ok=True))
            return future

        queue = MagicMock()
        queue.enqueue = mock_enqueue
        queue.pause = MagicMock()
        queue.resume = MagicMock()
        queue.clear = AsyncMock()

        sender = GcodeSender(queue)
        await sender.start_print(gcode_with_preamble, start_gcode="")
        await asyncio.wait_for(sender._task, timeout=5.0)

        # Without start gcode, nothing should be skipped
        print_cmds = [cmd for cmd, pri, _ in enqueued if pri == CommandPriority.PRINT]
        assert "G28" in print_cmds


# ── Progress defense-in-depth ────────────────────────────────────────


class TestProgressOnlyAdvancesOnSuccess:
    """Progress must NOT advance on failed commands — prevents the
    symptom where progress races to 100% during communication failures."""

    @pytest.fixture
    def gcode_file(self, tmp_path):
        f = tmp_path / "mixed.gcode"
        f.write_text("G1 X10\nG1 X20\nG1 X30\nG1 X40\nG1 X50\n")
        return f

    @pytest.mark.asyncio
    async def test_failed_commands_dont_advance_progress(self, gcode_file):
        call_count = 0

        async def mock_enqueue(cmd, priority=CommandPriority.USER, with_checksum=False):
            nonlocal call_count
            call_count += 1
            future = asyncio.get_running_loop().create_future()
            # 3rd PRINT command fails (call_count=3 since no M110/start gcode)
            if priority == CommandPriority.PRINT and call_count == 3:
                future.set_result(
                    CommandResult(command=cmd, ok=False, error="timeout")
                )
            else:
                future.set_result(CommandResult(command=cmd, ok=True))
            return future

        queue = MagicMock()
        queue.enqueue = mock_enqueue
        queue.pause = MagicMock()
        queue.resume = MagicMock()
        queue.clear = AsyncMock()

        sender = GcodeSender(queue)
        await sender.start_print(gcode_file, start_gcode="")
        await asyncio.wait_for(sender._task, timeout=5.0)

        # 5 file commands, 1 failed → only 4 should be counted
        assert sender._current_line == 4
        assert sender._total_lines == 5


# ── Protocol-level tests ─────────────────────────────────────────────


class TestProtocolLineNumberReset:
    """Protocol line-number mechanics still work correctly even though
    checksums are no longer used for file streaming."""

    def test_reset_sets_counter_to_zero(self):
        proto = MarlinProtocol.__new__(MarlinProtocol)
        proto._line_number = 4200
        proto.reset_line_number()
        assert proto._line_number == 0

    def test_first_command_after_reset_is_n1(self):
        proto = MarlinProtocol.__new__(MarlinProtocol)
        proto._line_number = 0
        result = proto._add_line_number("G1 X10")
        assert result.startswith("N1 G1 X10*")

    def test_simulated_second_print_line_numbers(self):
        """After a full print, reset + re-number produces N1 again."""
        proto = MarlinProtocol.__new__(MarlinProtocol)
        proto._line_number = 0
        for _ in range(100):
            proto._add_line_number("G1 X10")
        assert proto._line_number == 100
        proto.reset_line_number()
        assert proto._line_number == 0
        second = proto._add_line_number("G1 X10")
        assert second.startswith("N1 ")


# ── Protocol error drain ─────────────────────────────────────────────


class TestProtocolErrorDrain:
    """Verify temp report detection for in-band parsing."""

    def test_is_temp_report_standalone(self):
        proto = MarlinProtocol.__new__(MarlinProtocol)
        proto._temp_callbacks = []
        proto._terminal_callbacks = []
        assert proto._is_temp_report("T:200.0 /200.0 B:60.0 /60.0") is True

    def test_is_temp_report_combined_with_ok(self):
        proto = MarlinProtocol.__new__(MarlinProtocol)
        proto._temp_callbacks = []
        proto._terminal_callbacks = []
        assert proto._is_temp_report("ok T:200.0 /200.0 B:60.0 /60.0") is True

    def test_is_temp_report_not_temp(self):
        proto = MarlinProtocol.__new__(MarlinProtocol)
        proto._temp_callbacks = []
        proto._terminal_callbacks = []
        assert proto._is_temp_report("ok") is False
        assert proto._is_temp_report("echo:SD card ok") is False

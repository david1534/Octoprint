"""Tests for the G-code sender - filament tracking, progress, LCD, callbacks."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.serial.command_queue import CommandPriority
from app.serial.gcode_sender import GcodeSender, PrintResult
from app.serial.protocol import CommandResult


def _sender_with_successful_queue() -> GcodeSender:
    queue = MagicMock()

    async def enqueue(command, *args, **kwargs):
        future = asyncio.get_running_loop().create_future()
        future.set_result(CommandResult(command=command, ok=True))
        return future

    queue.enqueue = AsyncMock(side_effect=enqueue)
    return GcodeSender(queue)


class TestFilamentTracking:
    """Test filament usage tracking from G-code E values."""

    def _make_sender(self):
        """Create a GcodeSender with a mocked queue (only testing tracking)."""
        sender = GcodeSender.__new__(GcodeSender)
        sender._filament_used_mm = 0.0
        sender._last_e_position = 0.0
        sender._e_relative = False
        return sender

    def test_absolute_extrusion_forward(self):
        sender = self._make_sender()
        sender._track_filament("G1 X10 Y10 E5.0 F1500")
        assert sender._filament_used_mm == pytest.approx(5.0)
        sender._track_filament("G1 X20 Y20 E10.0 F1500")
        assert sender._filament_used_mm == pytest.approx(10.0)

    def test_absolute_extrusion_retract_not_counted(self):
        """Retractions (negative delta) should NOT be counted as usage."""
        sender = self._make_sender()
        sender._track_filament("G1 E5.0")
        sender._track_filament("G1 E3.0")  # retraction of 2mm
        assert sender._filament_used_mm == pytest.approx(5.0)

    def test_relative_extrusion_mode(self):
        sender = self._make_sender()
        sender._track_filament("M83")  # Switch to relative
        assert sender._e_relative is True
        sender._track_filament("G1 E1.5")
        assert sender._filament_used_mm == pytest.approx(1.5)
        sender._track_filament("G1 E2.0")
        assert sender._filament_used_mm == pytest.approx(3.5)

    def test_relative_retract_not_counted(self):
        sender = self._make_sender()
        sender._track_filament("M83")
        sender._track_filament("G1 E3.0")
        sender._track_filament("G1 E-1.0")  # retraction
        assert sender._filament_used_mm == pytest.approx(3.0)

    def test_m82_switches_to_absolute(self):
        sender = self._make_sender()
        sender._track_filament("M83")
        assert sender._e_relative is True
        sender._track_filament("M82")
        assert sender._e_relative is False

    def test_g92_resets_e_position(self):
        sender = self._make_sender()
        sender._track_filament("G1 E10.0")
        assert sender._filament_used_mm == pytest.approx(10.0)
        sender._track_filament("G92 E0")
        assert sender._last_e_position == pytest.approx(0.0)
        # Now E5 from 0 = 5mm more
        sender._track_filament("G1 E5.0")
        assert sender._filament_used_mm == pytest.approx(15.0)

    def test_non_move_commands_ignored(self):
        sender = self._make_sender()
        sender._track_filament("M104 S210")
        sender._track_filament("M140 S60")
        sender._track_filament("G28")
        sender._track_filament("G90")
        sender._track_filament("G91")
        assert sender._filament_used_mm == 0.0

    def test_g0_moves_also_tracked(self):
        sender = self._make_sender()
        sender._track_filament("G0 E2.0 F3000")
        assert sender._filament_used_mm == pytest.approx(2.0)

    def test_move_without_e_ignored(self):
        sender = self._make_sender()
        sender._track_filament("G1 X10 Y10 F3000")
        assert sender._filament_used_mm == 0.0


class TestGcodeSenderTerminalResult:
    """A done sender task is successful only after the whole loop completes."""

    async def test_file_io_failure_is_failed(self, monkeypatch, tmp_path):
        sender = _sender_with_successful_queue()
        sender._result = PrintResult.RUNNING

        def fail_open(*args, **kwargs):
            raise OSError("SD card read failed")

        monkeypatch.setattr("builtins.open", fail_open)
        await sender._print_loop(tmp_path / "broken.gcode")

        assert sender.result == PrintResult.FAILED
        assert isinstance(sender.failure, OSError)

    async def test_decode_error_is_failed(self, tmp_path):
        path = tmp_path / "invalid-utf8.gcode"
        path.write_bytes(b"G1 X1\n\xff\n")
        sender = _sender_with_successful_queue()
        sender._result = PrintResult.RUNNING

        await sender._print_loop(path)

        assert sender.result == PrintResult.FAILED
        assert isinstance(sender.failure, UnicodeDecodeError)

    async def test_escaping_callback_exception_is_failed(self, tmp_path):
        path = tmp_path / "callback.gcode"
        path.write_text(";LAYER:0\nG1 X1\n", encoding="utf-8")
        sender = _sender_with_successful_queue()
        sender._result = PrintResult.RUNNING
        sender._notify_layer_change = MagicMock(
            side_effect=RuntimeError("callback dispatch failed")
        )

        await sender._print_loop(path)

        assert sender.result == PrintResult.FAILED
        assert isinstance(sender.failure, RuntimeError)

    async def test_unexpected_queue_failure_is_failed(self, tmp_path):
        path = tmp_path / "queue.gcode"
        path.write_text("G1 X1\n", encoding="utf-8")
        queue = MagicMock()
        queue.enqueue = AsyncMock(side_effect=RuntimeError("queue stopped"))
        sender = GcodeSender(queue)
        sender._result = PrintResult.RUNNING

        await sender._print_loop(path)

        assert sender.result == PrintResult.FAILED
        assert isinstance(sender.failure, RuntimeError)

    async def test_success_sets_completed(self, tmp_path):
        path = tmp_path / "valid.gcode"
        path.write_text("G1 X1\n", encoding="utf-8")
        sender = _sender_with_successful_queue()
        sender._result = PrintResult.RUNNING

        await sender._print_loop(path)

        assert sender.result == PrintResult.COMPLETED
        assert sender.failure is None


class TestPauseResumeExtrusionSafety:
    """Pause/cancel helper moves must be safe in both M82 and M83 modes."""

    def _make_sender(self):
        queue = MagicMock()

        async def enqueue(*args, **kwargs):
            future = asyncio.get_running_loop().create_future()
            future.set_result(MagicMock(ok=True))
            return future

        queue.enqueue = AsyncMock(side_effect=enqueue)
        queue.clear = AsyncMock()
        sender = GcodeSender(queue)
        sender._task = MagicMock()
        sender._task.done.return_value = False
        return sender, queue

    async def test_absolute_extrusion_pause_resume_restores_large_e(self):
        sender, queue = self._make_sender()
        sender._track_filament("M82")
        sender._track_filament("G1 X100 Y100 E1200.12345 F1800")

        await sender.pause()
        await sender.resume()

        commands = [call.args[0] for call in queue.enqueue.await_args_list]
        retract = commands.index("G1 E-2 F1800")
        prime = commands.index("G1 E2 F1800")

        assert commands[retract - 2] == "M83"
        assert commands[retract + 1 : retract + 3] == [
            "M82",
            "G92 E1200.12345",
        ]
        assert commands[prime - 1] == "M83"
        assert commands[prime + 1 : prime + 3] == [
            "M82",
            "G92 E1200.12345",
        ]

    async def test_relative_extrusion_pause_resume_restores_m83(self):
        sender, queue = self._make_sender()
        sender._track_filament("M83")

        await sender.pause()
        await sender.resume()

        commands = [call.args[0] for call in queue.enqueue.await_args_list]
        retract = commands.index("G1 E-2 F1800")
        prime = commands.index("G1 E2 F1800")

        assert commands[retract - 2] == "M83"
        assert commands[retract + 1] == "M83"
        assert commands[prime - 1] == "M83"
        assert commands[prime + 1] == "M83"
        assert not any(command.startswith("G92 E") for command in commands)

    async def test_cancel_retract_uses_m83_and_restores_absolute_e(self):
        sender, queue = self._make_sender()
        sender._track_filament("G1 E9876.54321")

        await sender._on_cancel()

        commands = [call.args[0] for call in queue.enqueue.await_args_list]
        retract = commands.index("G1 E-5 F1800")
        assert commands[retract - 2] == "M83"
        assert commands[retract + 1 : retract + 3] == [
            "M82",
            "G92 E9876.54321",
        ]

    async def test_cancel_restores_relative_extrusion_mode(self):
        sender, queue = self._make_sender()
        sender._track_filament("M83")

        await sender._on_cancel()

        commands = [call.args[0] for call in queue.enqueue.await_args_list]
        retract = commands.index("G1 E-5 F1800")
        assert commands[retract - 2] == "M83"
        assert commands[retract + 1] == "M83"
        assert not any(command.startswith("G92 E") for command in commands)


class TestGcodeSenderProgress:
    """Test progress calculation properties."""

    def _make_sender_with_state(self):
        sender = GcodeSender.__new__(GcodeSender)
        sender._current_line = 0
        sender._total_lines = 0
        sender._current_layer = 0
        sender._total_layers = 0
        sender._current_file = None
        sender._start_time = None
        sender._paused = False
        sender._cancelled = False
        sender._pause_time = None
        sender._total_pause_duration = 0.0
        sender._task = None
        sender._in_start_gcode = False
        sender._result = PrintResult.IDLE
        sender._failure = None
        return sender

    def test_progress_zero_when_no_lines(self):
        sender = self._make_sender_with_state()
        sender._total_lines = 0
        assert sender.progress == 0.0

    def test_progress_percentage(self):
        sender = self._make_sender_with_state()
        sender._total_lines = 200
        sender._current_line = 100
        assert sender.progress == pytest.approx(50.0)

    def test_progress_capped_at_100(self):
        sender = self._make_sender_with_state()
        sender._total_lines = 100
        sender._current_line = 150  # edge case
        assert sender.progress == 100.0

    def test_is_printing_false_when_no_task(self):
        sender = self._make_sender_with_state()
        assert sender.is_printing is False

    def test_is_paused_default_false(self):
        sender = self._make_sender_with_state()
        assert sender.is_paused is False

    def test_elapsed_zero_when_not_started(self):
        sender = self._make_sender_with_state()
        assert sender.elapsed_seconds == 0.0

    def test_estimated_remaining_zero_when_not_started(self):
        sender = self._make_sender_with_state()
        assert sender.estimated_remaining == 0.0

    def test_current_file_initially_none(self):
        sender = self._make_sender_with_state()
        assert sender.current_file is None


class TestGcodeSenderLCD:
    """Test LCD progress display configuration."""

    def _make_sender(self):
        sender = GcodeSender.__new__(GcodeSender)
        sender._lcd_enabled = False
        sender._lcd_interval = 50
        return sender

    def test_default_lcd_disabled(self):
        sender = self._make_sender()
        assert sender._lcd_enabled is False

    def test_configure_lcd_enables(self):
        sender = self._make_sender()
        sender.configure_lcd(enabled=True, interval=25)
        assert sender._lcd_enabled is True
        assert sender._lcd_interval == 25

    def test_lcd_interval_minimum_enforced(self):
        sender = self._make_sender()
        sender.configure_lcd(enabled=True, interval=3)
        assert sender._lcd_interval == 10  # clamped to minimum


class TestGcodeSenderLayerCallbacks:
    """Test layer change callback system."""

    def _make_sender(self):
        sender = GcodeSender.__new__(GcodeSender)
        sender._layer_callbacks = []
        return sender

    def test_add_callback(self):
        sender = self._make_sender()
        callback = lambda layer: None
        sender.add_layer_callback(callback)
        assert callback in sender._layer_callbacks

    def test_remove_callback(self):
        sender = self._make_sender()
        callback = lambda layer: None
        sender.add_layer_callback(callback)
        sender.remove_layer_callback(callback)
        assert callback not in sender._layer_callbacks

    def test_remove_nonexistent_callback_safe(self):
        sender = self._make_sender()
        sender.remove_layer_callback(lambda layer: None)  # should not raise

    def test_notify_fires_callbacks(self):
        sender = self._make_sender()
        results = []
        sender.add_layer_callback(lambda layer: results.append(layer))
        sender._notify_layer_change(5)
        assert results == [5]

    def test_notify_multiple_callbacks(self):
        sender = self._make_sender()
        a, b = [], []
        sender.add_layer_callback(lambda l: a.append(l))
        sender.add_layer_callback(lambda l: b.append(l))
        sender._notify_layer_change(3)
        assert a == [3]
        assert b == [3]

    def test_callback_exception_doesnt_crash(self):
        sender = self._make_sender()
        results = []
        sender.add_layer_callback(lambda l: (_ for _ in ()).throw(ValueError("boom")))
        sender.add_layer_callback(lambda l: results.append(l))
        # Should not raise, and second callback still fires
        sender._notify_layer_change(1)
        assert results == [1]


class TestGcodeSenderReset:
    """Test state cleanup after print."""

    def test_reset_clears_state(self):
        sender = GcodeSender.__new__(GcodeSender)
        sender._current_file = "test.gcode"
        sender._current_line = 500
        sender._total_lines = 1000
        sender._current_layer = 10
        sender._total_layers = 50
        sender._start_time = 12345.0
        sender._paused = True
        sender._cancelled = True
        sender._in_start_gcode = True
        sender._task = "fake"
        sender._result = PrintResult.FAILED
        sender._failure = RuntimeError("boom")
        sender._layer_callbacks = [lambda: None]
        sender._filament_used_mm = 250.0

        sender.reset()

        assert sender._current_file is None
        assert sender._current_line == 0
        assert sender._total_lines == 0
        assert sender._current_layer == 0
        assert sender._total_layers == 0
        assert sender._start_time is None
        assert sender._paused is False
        assert sender._cancelled is False
        assert sender._in_start_gcode is False
        assert sender._task is None
        assert sender.result == PrintResult.IDLE
        assert sender.failure is None
        assert sender._layer_callbacks == []

    def test_reset_preserves_filament_used(self):
        """Filament usage is intentionally NOT reset (read by _on_print_complete)."""
        sender = GcodeSender.__new__(GcodeSender)
        sender._current_file = "x.gcode"
        sender._current_line = 0
        sender._total_lines = 0
        sender._current_layer = 0
        sender._total_layers = 0
        sender._start_time = None
        sender._paused = False
        sender._cancelled = False
        sender._in_start_gcode = False
        sender._task = None
        sender._result = PrintResult.COMPLETED
        sender._failure = None
        sender._layer_callbacks = []
        sender._filament_used_mm = 123.456

        sender.reset()
        assert sender._filament_used_mm == pytest.approx(123.456)


class _ControlledCancelQueue:
    def __init__(self):
        self.calls = []
        self.heater_futures = {}
        self.clear = AsyncMock()
        self.resume = MagicMock()

    async def enqueue(self, command, priority, **kwargs):
        self.calls.append((command, priority, kwargs))
        future = asyncio.get_running_loop().create_future()
        if command in {"M104 S0", "M140 S0"}:
            self.heater_futures[command] = future
        elif command != "G28 X Y":
            future.set_result(CommandResult(command=command, ok=True))
        return future


class TestCancelSafetyOrdering:
    async def test_heaters_are_safety_priority_and_acknowledged_before_park(self):
        queue = _ControlledCancelQueue()
        sender = GcodeSender(queue)

        cleanup = asyncio.create_task(sender._on_cancel())
        while len(queue.calls) < 3:
            await asyncio.sleep(0)

        assert [call[0] for call in queue.calls] == [
            "M104 S0",
            "M140 S0",
            "M106 S0",
        ]
        assert all(call[1] == CommandPriority.SAFETY for call in queue.calls)
        assert queue.calls[0][2]["timeout"] == 3.0
        assert queue.calls[1][2]["timeout"] == 3.0

        for command, future in queue.heater_futures.items():
            future.set_result(CommandResult(command=command, ok=True))

        # G28 deliberately never acknowledges. Cancellation still finishes
        # because parking is queued only after heater ack and is not awaited.
        await asyncio.wait_for(cleanup, timeout=0.2)
        commands = [call[0] for call in queue.calls]
        assert commands.index("M104 S0") < commands.index("G28 X Y")
        assert commands.index("M140 S0") < commands.index("G28 X Y")

    async def test_failed_heater_ack_skips_all_parking_motion(self):
        queue = _ControlledCancelQueue()
        sender = GcodeSender(queue)

        cleanup = asyncio.create_task(sender._on_cancel())
        while len(queue.heater_futures) < 2:
            await asyncio.sleep(0)
        for command, future in queue.heater_futures.items():
            future.set_result(
                CommandResult(command=command, ok=False, error="disconnected")
            )

        await cleanup
        commands = [call[0] for call in queue.calls]
        assert commands == ["M104 S0", "M140 S0", "M106 S0"]

    def test_request_cancel_releases_paused_sender_immediately(self):
        queue = _ControlledCancelQueue()
        sender = GcodeSender(queue)
        sender._paused = True

        sender.request_cancel()

        assert sender._cancelled is True
        assert sender._paused is False
        queue.resume.assert_called_once_with()

"""Tests for the G-code sender - filament tracking, progress, LCD, callbacks."""

import pytest

from app.serial.gcode_sender import GcodeSender
from app.serial.command_queue import CommandPriority, CommandQueue


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
        sender._layer_callbacks = []
        sender._filament_used_mm = 123.456

        sender.reset()
        assert sender._filament_used_mm == pytest.approx(123.456)

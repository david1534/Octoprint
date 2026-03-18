"""Tests for printer state management."""

import time
import pytest

from app.printer.state import PrinterState, PrinterStatus


class TestPrinterStatus:
    """Test the PrinterStatus enum."""

    def test_all_statuses_exist(self):
        statuses = {s.value for s in PrinterStatus}
        expected = {
            "disconnected",
            "connecting",
            "idle",
            "printing",
            "paused",
            "error",
            "finishing",
        }
        assert statuses == expected

    def test_status_is_string_enum(self):
        assert PrinterStatus.IDLE == "idle"
        assert PrinterStatus.PRINTING == "printing"


class TestPrinterState:
    """Test PrinterState dataclass."""

    def test_default_state(self):
        state = PrinterState()
        assert state.status == PrinterStatus.DISCONNECTED
        assert state.port == ""
        assert state.baudrate == 115200
        assert state.hotend_actual == 0.0
        assert state.hotend_target == 0.0
        assert state.bed_actual == 0.0
        assert state.bed_target == 0.0
        assert state.x == 0.0
        assert state.y == 0.0
        assert state.z == 0.0
        assert state.current_file is None
        assert state.print_progress == 0.0
        assert state.fan_speed == 0
        assert state.firmware_name == ""
        assert state.error_message is None
        assert state.bed_mesh is None

    def test_update_temperatures(self):
        state = PrinterState()
        before = time.time()
        state.update_temperatures(210.5, 215.0, 60.3, 65.0)
        after = time.time()

        assert state.hotend_actual == pytest.approx(210.5)
        assert state.hotend_target == pytest.approx(215.0)
        assert state.bed_actual == pytest.approx(60.3)
        assert state.bed_target == pytest.approx(65.0)
        assert before <= state.last_update <= after

    def test_to_dict_structure(self):
        state = PrinterState()
        state.status = PrinterStatus.PRINTING
        state.hotend_actual = 210.0
        state.hotend_target = 215.0
        state.bed_actual = 60.0
        state.bed_target = 65.0
        state.x = 100.123
        state.y = 50.456
        state.z = 0.2
        state.current_file = "benchy.gcode"
        state.print_progress = 42.5
        state.fan_speed = 255
        state.firmware_name = "Marlin 2.1.2.1"
        state.current_layer = 5
        state.total_layers = 100

        d = state.to_dict()

        assert d["status"] == "printing"
        assert d["hotend"]["actual"] == 210.0
        assert d["hotend"]["target"] == 215.0
        assert d["bed"]["actual"] == 60.0
        assert d["bed"]["target"] == 65.0
        assert d["position"]["x"] == 100.12
        assert d["position"]["y"] == 50.46
        assert d["position"]["z"] == 0.2
        assert d["print"]["file"] == "benchy.gcode"
        assert d["print"]["progress"] == 42.5
        assert d["print"]["currentLayer"] == 5
        assert d["print"]["totalLayers"] == 100
        assert d["fan_speed"] == 255
        assert d["firmware"] == "Marlin 2.1.2.1"
        assert d["error"] is None

    def test_to_dict_rounds_temperatures(self):
        state = PrinterState()
        state.hotend_actual = 210.456
        state.bed_actual = 60.789
        d = state.to_dict()
        assert d["hotend"]["actual"] == 210.5
        assert d["bed"]["actual"] == 60.8

    def test_to_dict_rounds_position(self):
        state = PrinterState()
        state.x = 123.4567
        state.y = 45.6789
        state.z = 0.12345
        d = state.to_dict()
        assert d["position"]["x"] == 123.46
        assert d["position"]["y"] == 45.68
        assert d["position"]["z"] == 0.12

    def test_to_dict_includes_timelapse(self):
        state = PrinterState()
        state.timelapse_recording = True
        state.timelapse_frame_count = 42
        state.timelapse_assembling = False
        d = state.to_dict()
        assert d["timelapse"]["recording"] is True
        assert d["timelapse"]["frameCount"] == 42
        assert d["timelapse"]["assembling"] is False

    def test_to_dict_includes_bed_mesh(self):
        state = PrinterState()
        state.bed_mesh = {"grid": [[0.1]], "rows": 1, "cols": 1}
        d = state.to_dict()
        assert d["bed_mesh"]["grid"] == [[0.1]]

    def test_disconnected_default_no_print_info(self):
        state = PrinterState()
        d = state.to_dict()
        assert d["print"]["file"] is None
        assert d["print"]["progress"] == 0.0
        assert d["print"]["elapsed"] == 0
        assert d["print"]["remaining"] == 0

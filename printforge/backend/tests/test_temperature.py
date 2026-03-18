"""Tests for temperature parsing and monitoring."""

import time
import pytest

from app.serial.temperature import (
    TEMP_REGEX,
    BED_REGEX,
    TemperatureMonitor,
    TemperatureReading,
    TemperatureSnapshot,
)


class TestTempRegex:
    """Verify temperature regex patterns match real Marlin output."""

    def test_hotend_regex_standard(self):
        line = " T:205.3 /210.0 B:60.1 /60.0 @:127 B@:64"
        match = TEMP_REGEX.search(line)
        assert match is not None
        assert match.group("hotend_actual") == "205.3"
        assert match.group("hotend_target") == "210.0"

    def test_bed_regex_standard(self):
        line = " T:205.3 /210.0 B:60.1 /60.0 @:127 B@:64"
        match = BED_REGEX.search(line)
        assert match is not None
        assert match.group("bed_actual") == "60.1"
        assert match.group("bed_target") == "60.0"

    def test_hotend_regex_no_spaces_around_slash(self):
        line = "T:22.0/0.0 B:21.0/0.0"
        match = TEMP_REGEX.search(line)
        assert match is not None
        assert match.group("hotend_actual") == "22.0"
        assert match.group("hotend_target") == "0.0"

    def test_regex_does_not_match_non_temp_line(self):
        line = "ok"
        assert TEMP_REGEX.search(line) is None
        assert BED_REGEX.search(line) is None

    def test_regex_no_bed_data(self):
        """Some firmware reports may omit bed temps."""
        line = "T:100.0 /100.0"
        assert TEMP_REGEX.search(line) is not None
        assert BED_REGEX.search(line) is None


class TestTemperatureMonitor:
    """Test the TemperatureMonitor state machine."""

    def test_parse_standard_temp_line(self):
        mon = TemperatureMonitor()
        snap = mon.parse_line(" T:205.3 /210.0 B:60.1 /60.0 @:0 B@:0")
        assert snap is not None
        assert snap.hotend.actual == pytest.approx(205.3)
        assert snap.hotend.target == pytest.approx(210.0)
        assert snap.bed.actual == pytest.approx(60.1)
        assert snap.bed.target == pytest.approx(60.0)

    def test_parse_returns_none_for_non_temp_line(self):
        mon = TemperatureMonitor()
        assert mon.parse_line("ok") is None
        assert mon.parse_line("echo:Compiled: Jun 2023") is None
        assert mon.parse_line("X:0.00 Y:0.00 Z:0.00 E:0.00") is None

    def test_history_accumulates(self):
        mon = TemperatureMonitor(history_size=5)
        for i in range(3):
            mon.parse_line(f" T:{100 + i}.0 /200.0 B:50.0 /60.0")
        assert len(mon.history) == 3

    def test_history_respects_max_size(self):
        mon = TemperatureMonitor(history_size=3)
        for i in range(10):
            mon.parse_line(f" T:{100 + i}.0 /200.0 B:50.0 /60.0")
        assert len(mon.history) == 3
        # Latest entry should be the last one parsed
        assert mon.history[-1].hotend.actual == pytest.approx(109.0)

    def test_latest_returns_most_recent(self):
        mon = TemperatureMonitor()
        mon.parse_line(" T:100.0 /200.0 B:50.0 /60.0")
        mon.parse_line(" T:150.0 /200.0 B:55.0 /60.0")
        latest = mon.latest
        assert latest is not None
        assert latest.hotend.actual == pytest.approx(150.0)
        assert latest.bed.actual == pytest.approx(55.0)

    def test_latest_returns_none_when_empty(self):
        mon = TemperatureMonitor()
        assert mon.latest is None

    def test_hotend_and_bed_properties(self):
        mon = TemperatureMonitor()
        mon.parse_line(" T:210.0 /215.0 B:60.0 /65.0")
        assert mon.hotend.actual == pytest.approx(210.0)
        assert mon.hotend.target == pytest.approx(215.0)
        assert mon.bed.actual == pytest.approx(60.0)
        assert mon.bed.target == pytest.approx(65.0)

    def test_missing_bed_uses_last_known(self):
        """If bed data is missing, use the last known bed values."""
        mon = TemperatureMonitor()
        mon.parse_line(" T:200.0 /210.0 B:60.0 /65.0")
        # Line without bed data
        snap = mon.parse_line(" T:205.0 /210.0")
        assert snap is not None
        # Should carry forward the last bed values
        assert snap.bed.actual == pytest.approx(60.0)
        assert snap.bed.target == pytest.approx(65.0)

    def test_initial_readings_are_zero(self):
        mon = TemperatureMonitor()
        assert mon.hotend.actual == 0.0
        assert mon.hotend.target == 0.0
        assert mon.bed.actual == 0.0
        assert mon.bed.target == 0.0

    def test_snapshot_timestamp_is_recent(self):
        mon = TemperatureMonitor()
        before = time.time()
        snap = mon.parse_line(" T:100.0 /200.0 B:50.0 /60.0")
        after = time.time()
        assert snap is not None
        assert before <= snap.hotend.timestamp <= after

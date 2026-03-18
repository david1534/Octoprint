"""Tests for safety monitoring."""

import time
import pytest

from app.serial.safety import AlertLevel, SafetyAction, SafetyMonitor
from app.serial.temperature import TemperatureReading, TemperatureSnapshot


def _make_snapshot(
    hotend_actual: float,
    hotend_target: float,
    bed_actual: float,
    bed_target: float,
) -> TemperatureSnapshot:
    now = time.time()
    return TemperatureSnapshot(
        hotend=TemperatureReading(
            actual=hotend_actual, target=hotend_target, timestamp=now
        ),
        bed=TemperatureReading(actual=bed_actual, target=bed_target, timestamp=now),
    )


class TestAbsoluteTemperatureLimits:
    def test_hotend_over_limit_triggers_emergency(self):
        monitor = SafetyMonitor(max_hotend_temp=260.0)
        snapshot = _make_snapshot(265.0, 210.0, 60.0, 60.0)
        alerts = monitor.check_temperatures(snapshot)
        assert len(alerts) >= 1
        assert any(a.action == SafetyAction.EMERGENCY_STOP for a in alerts)

    def test_bed_over_limit_triggers_emergency(self):
        monitor = SafetyMonitor(max_bed_temp=110.0)
        snapshot = _make_snapshot(200.0, 200.0, 115.0, 100.0)
        alerts = monitor.check_temperatures(snapshot)
        assert len(alerts) >= 1
        assert any(a.action == SafetyAction.EMERGENCY_STOP for a in alerts)

    def test_normal_temps_no_alerts(self):
        monitor = SafetyMonitor()
        snapshot = _make_snapshot(205.0, 210.0, 60.0, 60.0)
        alerts = monitor.check_temperatures(snapshot)
        assert len(alerts) == 0


class TestSerialWatchdog:
    def test_no_alert_when_not_printing(self):
        monitor = SafetyMonitor(serial_watchdog_timeout=5.0)
        monitor._last_serial_activity = time.time() - 60
        alert = monitor.check_serial_watchdog(is_printing=False)
        assert alert is None

    def test_alert_when_printing_and_silent(self):
        monitor = SafetyMonitor(serial_watchdog_timeout=5.0)
        monitor._last_serial_activity = time.time() - 60
        alert = monitor.check_serial_watchdog(is_printing=True)
        assert alert is not None
        assert alert.action == SafetyAction.PAUSE_PRINT

    def test_no_alert_when_printing_and_active(self):
        monitor = SafetyMonitor(serial_watchdog_timeout=5.0)
        monitor._last_serial_activity = time.time()
        alert = monitor.check_serial_watchdog(is_printing=True)
        assert alert is None


class TestThermalRunawayHotend:
    """Test hotend thermal runaway detection."""

    def test_no_runaway_within_threshold(self):
        """Temp slightly above target but within threshold = no alert."""
        monitor = SafetyMonitor(thermal_runaway_threshold=15.0)
        snapshot = _make_snapshot(220.0, 210.0, 60.0, 60.0)  # +10, below 15
        alerts = monitor.check_temperatures(snapshot)
        runaway_alerts = [a for a in alerts if "runaway" in a.message.lower()]
        assert len(runaway_alerts) == 0

    def test_runaway_not_immediate(self):
        """Deviation above threshold must persist for duration before alert."""
        monitor = SafetyMonitor(
            thermal_runaway_threshold=15.0,
            thermal_runaway_duration=45.0,
        )
        # First check: starts the clock
        snapshot = _make_snapshot(230.0, 210.0, 60.0, 60.0)  # +20 > 15
        alerts = monitor.check_temperatures(snapshot)
        runaway_alerts = [a for a in alerts if "runaway" in a.message.lower()]
        assert len(runaway_alerts) == 0  # Not yet, timer just started

    def test_runaway_triggers_after_duration(self):
        """Alert fires after deviation persists for the full duration."""
        monitor = SafetyMonitor(
            thermal_runaway_threshold=15.0,
            thermal_runaway_duration=5.0,  # short for testing
        )
        # First check: starts the clock
        snap1 = _make_snapshot(230.0, 210.0, 60.0, 60.0)
        monitor.check_temperatures(snap1)

        # Simulate time passing
        monitor._runaway_start_hotend = time.time() - 10  # 10s ago

        # Second check: duration exceeded
        snap2 = _make_snapshot(230.0, 210.0, 60.0, 60.0)
        alerts = monitor.check_temperatures(snap2)
        runaway_alerts = [a for a in alerts if "runaway" in a.message.lower()]
        assert len(runaway_alerts) >= 1
        assert runaway_alerts[0].action == SafetyAction.EMERGENCY_STOP

    def test_runaway_resets_when_temp_normalizes(self):
        """Timer resets if temp comes back within threshold."""
        monitor = SafetyMonitor(
            thermal_runaway_threshold=15.0,
            thermal_runaway_duration=45.0,
        )
        # Start runaway timer
        snap1 = _make_snapshot(230.0, 210.0, 60.0, 60.0)
        monitor.check_temperatures(snap1)
        assert monitor._runaway_start_hotend is not None

        # Temp normalizes
        snap2 = _make_snapshot(212.0, 210.0, 60.0, 60.0)
        monitor.check_temperatures(snap2)
        assert monitor._runaway_start_hotend is None

    def test_no_runaway_check_when_target_zero(self):
        """No runaway detection when heater is off (target=0)."""
        monitor = SafetyMonitor(thermal_runaway_threshold=15.0)
        snapshot = _make_snapshot(100.0, 0.0, 60.0, 60.0)
        alerts = monitor.check_temperatures(snapshot)
        assert monitor._runaway_start_hotend is None


class TestThermalRunawayBed:
    """Test bed thermal runaway detection."""

    def test_bed_runaway_triggers(self):
        monitor = SafetyMonitor(
            thermal_runaway_threshold=15.0,
            thermal_runaway_duration=5.0,
        )
        # Start timer
        snap1 = _make_snapshot(210.0, 210.0, 80.0, 60.0)  # bed +20 > 15
        monitor.check_temperatures(snap1)

        # Simulate time
        monitor._runaway_start_bed = time.time() - 10

        snap2 = _make_snapshot(210.0, 210.0, 80.0, 60.0)
        alerts = monitor.check_temperatures(snap2)
        bed_runaway = [
            a
            for a in alerts
            if "bed" in a.message.lower() and "runaway" in a.message.lower()
        ]
        assert len(bed_runaway) >= 1

    def test_bed_runaway_resets(self):
        monitor = SafetyMonitor(thermal_runaway_threshold=15.0)
        snap1 = _make_snapshot(210.0, 210.0, 80.0, 60.0)
        monitor.check_temperatures(snap1)
        assert monitor._runaway_start_bed is not None

        snap2 = _make_snapshot(210.0, 210.0, 62.0, 60.0)
        monitor.check_temperatures(snap2)
        assert monitor._runaway_start_bed is None


class TestAlertCallbacks:
    """Test alert callback system."""

    def test_callback_fires_on_alert(self):
        monitor = SafetyMonitor(max_hotend_temp=260.0)
        received = []
        monitor.add_alert_callback(lambda a: received.append(a))
        snapshot = _make_snapshot(270.0, 210.0, 60.0, 60.0)
        monitor.check_temperatures(snapshot)
        assert len(received) >= 1
        assert received[0].level == AlertLevel.CRITICAL

    def test_recent_alerts_within_window(self):
        monitor = SafetyMonitor(max_hotend_temp=260.0)
        snapshot = _make_snapshot(270.0, 210.0, 60.0, 60.0)
        monitor.check_temperatures(snapshot)
        assert len(monitor.recent_alerts) >= 1

    def test_record_serial_activity(self):
        monitor = SafetyMonitor()
        old_time = monitor._last_serial_activity
        time.sleep(0.01)
        monitor.record_serial_activity()
        assert monitor._last_serial_activity > old_time

    def test_alerts_capped_at_100(self):
        monitor = SafetyMonitor(max_hotend_temp=260.0)
        for _ in range(120):
            snapshot = _make_snapshot(270.0, 210.0, 60.0, 60.0)
            monitor.check_temperatures(snapshot)
        assert len(monitor._alerts) <= 100

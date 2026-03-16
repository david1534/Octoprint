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
        bed=TemperatureReading(
            actual=bed_actual, target=bed_target, timestamp=now
        ),
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

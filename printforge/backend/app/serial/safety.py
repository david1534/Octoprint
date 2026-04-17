"""Safety monitoring for 3D printer operation.

IMPORTANT: Marlin firmware is the PRIMARY safety system. This module is a
SECONDARY monitoring layer that provides additional alerts and can trigger
emergency stop as a last resort. It does NOT replace firmware-level
thermal runaway protection.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .temperature import TemperatureMonitor, TemperatureSnapshot

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    WARNING = "warning"
    CRITICAL = "critical"


class SafetyAction(Enum):
    ALERT_ONLY = "alert_only"
    PAUSE_PRINT = "pause_print"
    EMERGENCY_STOP = "emergency_stop"


@dataclass
class SafetyAlert:
    level: AlertLevel
    message: str
    action: SafetyAction
    timestamp: float


class SafetyMonitor:
    """Secondary safety monitoring layer."""

    def __init__(
        self,
        max_hotend_temp: float = 290.0,
        max_bed_temp: float = 110.0,
        thermal_runaway_threshold: float = 15.0,
        thermal_runaway_duration: float = 45.0,
        serial_watchdog_timeout: float = 30.0,
    ):
        self.max_hotend_temp = max_hotend_temp
        self.max_bed_temp = max_bed_temp
        self.thermal_runaway_threshold = thermal_runaway_threshold
        self.thermal_runaway_duration = thermal_runaway_duration
        self.serial_watchdog_timeout = serial_watchdog_timeout

        self._runaway_start_hotend: Optional[float] = None
        self._runaway_start_bed: Optional[float] = None
        self._last_serial_activity: float = time.time()
        self._alerts: list[SafetyAlert] = []
        self._alert_callbacks: list = []

    @property
    def recent_alerts(self) -> list[SafetyAlert]:
        cutoff = time.time() - 300  # Last 5 minutes
        return [a for a in self._alerts if a.timestamp >= cutoff]

    def add_alert_callback(self, callback) -> None:
        self._alert_callbacks.append(callback)

    def record_serial_activity(self) -> None:
        """Call this whenever data is received from the printer."""
        self._last_serial_activity = time.time()

    def _emit_alert(self, alert: SafetyAlert) -> None:
        self._alerts.append(alert)
        # Keep only last 100 alerts
        if len(self._alerts) > 100:
            self._alerts = self._alerts[-100:]
        for cb in self._alert_callbacks:
            try:
                cb(alert)
            except Exception:
                logger.exception("Error in alert callback")

    def check_temperatures(
        self, snapshot: TemperatureSnapshot
    ) -> list[SafetyAlert]:
        """Check a temperature reading for safety violations.

        Returns list of any alerts generated.
        """
        alerts = []
        now = time.time()

        # Absolute temperature limits
        if snapshot.hotend.actual > self.max_hotend_temp:
            alert = SafetyAlert(
                level=AlertLevel.CRITICAL,
                message=(
                    f"Hotend temperature {snapshot.hotend.actual:.1f}C "
                    f"exceeds limit of {self.max_hotend_temp}C"
                ),
                action=SafetyAction.EMERGENCY_STOP,
                timestamp=now,
            )
            alerts.append(alert)
            self._emit_alert(alert)

        if snapshot.bed.actual > self.max_bed_temp:
            alert = SafetyAlert(
                level=AlertLevel.CRITICAL,
                message=(
                    f"Bed temperature {snapshot.bed.actual:.1f}C "
                    f"exceeds limit of {self.max_bed_temp}C"
                ),
                action=SafetyAction.EMERGENCY_STOP,
                timestamp=now,
            )
            alerts.append(alert)
            self._emit_alert(alert)

        # Thermal runaway detection (temp far above target while target > 0)
        alerts.extend(self._check_runaway_hotend(snapshot, now))
        alerts.extend(self._check_runaway_bed(snapshot, now))

        return alerts

    def _check_runaway_hotend(
        self, snapshot: TemperatureSnapshot, now: float
    ) -> list[SafetyAlert]:
        if snapshot.hotend.target <= 0:
            self._runaway_start_hotend = None
            return []

        deviation = snapshot.hotend.actual - snapshot.hotend.target
        if deviation > self.thermal_runaway_threshold:
            if self._runaway_start_hotend is None:
                self._runaway_start_hotend = now
            elif now - self._runaway_start_hotend >= self.thermal_runaway_duration:
                alert = SafetyAlert(
                    level=AlertLevel.CRITICAL,
                    message=(
                        f"Possible hotend thermal runaway: {snapshot.hotend.actual:.1f}C "
                        f"(target {snapshot.hotend.target:.1f}C) for "
                        f"{now - self._runaway_start_hotend:.0f}s"
                    ),
                    action=SafetyAction.EMERGENCY_STOP,
                    timestamp=now,
                )
                self._emit_alert(alert)
                return [alert]
        else:
            self._runaway_start_hotend = None
        return []

    def _check_runaway_bed(
        self, snapshot: TemperatureSnapshot, now: float
    ) -> list[SafetyAlert]:
        if snapshot.bed.target <= 0:
            self._runaway_start_bed = None
            return []

        deviation = snapshot.bed.actual - snapshot.bed.target
        if deviation > self.thermal_runaway_threshold:
            if self._runaway_start_bed is None:
                self._runaway_start_bed = now
            elif now - self._runaway_start_bed >= self.thermal_runaway_duration:
                alert = SafetyAlert(
                    level=AlertLevel.CRITICAL,
                    message=(
                        f"Possible bed thermal runaway: {snapshot.bed.actual:.1f}C "
                        f"(target {snapshot.bed.target:.1f}C) for "
                        f"{now - self._runaway_start_bed:.0f}s"
                    ),
                    action=SafetyAction.EMERGENCY_STOP,
                    timestamp=now,
                )
                self._emit_alert(alert)
                return [alert]
        else:
            self._runaway_start_bed = None
        return []

    def check_serial_watchdog(self, is_printing: bool) -> Optional[SafetyAlert]:
        """Check if the serial connection has gone silent during a print."""
        if not is_printing:
            return None

        elapsed = time.time() - self._last_serial_activity
        if elapsed > self.serial_watchdog_timeout:
            alert = SafetyAlert(
                level=AlertLevel.CRITICAL,
                message=(
                    f"No serial data received for {elapsed:.0f}s during print"
                ),
                action=SafetyAction.PAUSE_PRINT,
                timestamp=time.time(),
            )
            self._emit_alert(alert)
            return alert
        return None

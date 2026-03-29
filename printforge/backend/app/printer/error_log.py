"""Error logging service with known error catalog.

Captures, categorizes, and stores printer errors with human-readable
descriptions and suggested fixes. Errors are broadcast to the frontend
in real-time via WebSocket.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    SERIAL = "serial"
    TEMPERATURE = "temperature"
    MECHANICAL = "mechanical"
    FIRMWARE = "firmware"
    PRINT = "print"
    SAFETY = "safety"
    SYSTEM = "system"


@dataclass
class ErrorEntry:
    id: int
    severity: ErrorSeverity
    category: ErrorCategory
    title: str
    message: str
    description: str
    fixes: list[str]
    timestamp: float
    dismissed: bool = False
    raw: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "severity": self.severity.value,
            "category": self.category.value,
            "title": self.title,
            "message": self.message,
            "description": self.description,
            "fixes": self.fixes,
            "timestamp": self.timestamp,
            "dismissed": self.dismissed,
            "raw": self.raw,
        }


# ── Known Error Catalog ─────────────────────────────────────────

@dataclass
class ErrorPattern:
    """A known error pattern with regex match, description, and fixes."""
    pattern: re.Pattern
    title: str
    severity: ErrorSeverity
    category: ErrorCategory
    description: str
    fixes: list[str]


KNOWN_ERRORS: list[ErrorPattern] = [
    # BLTouch / probe errors
    ErrorPattern(
        pattern=re.compile(r"STOP called because of BLTouch error", re.IGNORECASE),
        title="BLTouch Probe Error",
        severity=ErrorSeverity.CRITICAL,
        category=ErrorCategory.MECHANICAL,
        description=(
            "The BLTouch auto bed leveling probe reported an error. This usually "
            "happens when the probe is triggered unexpectedly, deployed too quickly "
            "in succession, or the wiring has a loose connection."
        ),
        fixes=[
            "Power cycle the printer to reset the BLTouch",
            "Check the BLTouch wiring for loose connections",
            "Ensure the probe pin moves freely and isn't bent",
            "Avoid running G28 (home) multiple times in quick succession",
            "If persistent, try M999 to reset the firmware error state",
        ],
    ),
    ErrorPattern(
        pattern=re.compile(r"Probing Failed", re.IGNORECASE),
        title="Bed Probing Failed",
        severity=ErrorSeverity.ERROR,
        category=ErrorCategory.MECHANICAL,
        description=(
            "The auto bed leveling probe failed to trigger during a probing "
            "sequence. The probe may not be deploying properly, or the bed "
            "is too far from the nozzle for the probe to reach."
        ),
        fixes=[
            "Check that the BLTouch probe pin deploys and retracts correctly",
            "Verify the bed height — the nozzle may be too far from the bed",
            "Clean the probe pin and ensure it moves freely",
            "Re-run G28 to home the printer before retrying",
        ],
    ),
    # Thermal errors
    ErrorPattern(
        pattern=re.compile(r"Thermal Runaway", re.IGNORECASE),
        title="Thermal Runaway Detected",
        severity=ErrorSeverity.CRITICAL,
        category=ErrorCategory.TEMPERATURE,
        description=(
            "The firmware detected a thermal runaway condition — the heater "
            "temperature deviated dangerously from the target. This is a critical "
            "safety feature that prevents fires."
        ),
        fixes=[
            "Check the thermistor wiring on the affected heater",
            "Ensure the heater cartridge is properly seated",
            "Check for drafts or cooling that could cause rapid temperature drops",
            "If the thermistor reads erratic values, it may need replacement",
            "Power cycle the printer and monitor temperatures during next heat-up",
        ],
    ),
    ErrorPattern(
        pattern=re.compile(r"Heating Failed", re.IGNORECASE),
        title="Heating Failed",
        severity=ErrorSeverity.ERROR,
        category=ErrorCategory.TEMPERATURE,
        description=(
            "The heater could not reach the target temperature within the "
            "firmware's timeout period. This usually indicates a hardware "
            "issue with the heater or thermistor."
        ),
        fixes=[
            "Check that the heater cartridge is properly seated in the hotend",
            "Verify thermistor wiring connections",
            "If the bed fails to heat, check the bed heater cable under the bed",
            "Ensure adequate power supply voltage (should be ~24V for most printers)",
            "Try heating to a lower temperature first as a test",
        ],
    ),
    ErrorPattern(
        pattern=re.compile(r"MINTEMP", re.IGNORECASE),
        title="Minimum Temperature Error",
        severity=ErrorSeverity.CRITICAL,
        category=ErrorCategory.TEMPERATURE,
        description=(
            "The thermistor reading dropped below the minimum safe temperature. "
            "This almost always means the thermistor is disconnected or has a "
            "broken wire."
        ),
        fixes=[
            "Check the thermistor connector — it may be loose or unplugged",
            "Inspect thermistor wires for breaks, especially near the connector",
            "If the thermistor is damaged, replace it",
            "Power cycle after fixing the wiring issue",
        ],
    ),
    ErrorPattern(
        pattern=re.compile(r"MAXTEMP", re.IGNORECASE),
        title="Maximum Temperature Exceeded",
        severity=ErrorSeverity.CRITICAL,
        category=ErrorCategory.TEMPERATURE,
        description=(
            "The temperature reading exceeded the firmware's maximum safe limit. "
            "This could indicate a short in the thermistor wiring or a runaway "
            "heater."
        ),
        fixes=[
            "Disconnect power immediately if temperature is genuinely too high",
            "Check for a short circuit in the thermistor wiring",
            "Verify the thermistor type matches the firmware configuration",
            "Replace the thermistor if readings are erratic",
        ],
    ),
    ErrorPattern(
        pattern=re.compile(r"Temperature reading (invalid|abnormal)", re.IGNORECASE),
        title="Invalid Temperature Reading",
        severity=ErrorSeverity.WARNING,
        category=ErrorCategory.TEMPERATURE,
        description=(
            "The thermistor returned an unexpected reading. This may be "
            "intermittent noise or indicate a failing thermistor."
        ),
        fixes=[
            "Check thermistor wire connections for looseness",
            "Monitor readings — occasional glitches are normal, persistent ones indicate a failing sensor",
            "Ensure thermistor wires are routed away from stepper motors and heater wires",
        ],
    ),
    # Mechanical / endstop errors
    ErrorPattern(
        pattern=re.compile(r"Homing Failed", re.IGNORECASE),
        title="Homing Failed",
        severity=ErrorSeverity.ERROR,
        category=ErrorCategory.MECHANICAL,
        description=(
            "The printer could not complete the homing sequence. An axis "
            "failed to trigger its endstop within the expected travel distance."
        ),
        fixes=[
            "Check that the endstop switches are functioning (press and listen for click)",
            "Verify the endstop wiring connections on the control board",
            "Ensure no physical obstructions are blocking axis movement",
            "Check that belts are properly tensioned — a loose belt can slip",
            "For BLTouch Z-homing: ensure probe deploys correctly before homing",
        ],
    ),
    ErrorPattern(
        pattern=re.compile(r"Endstop .+ (hit|triggered)", re.IGNORECASE),
        title="Unexpected Endstop Trigger",
        severity=ErrorSeverity.WARNING,
        category=ErrorCategory.MECHANICAL,
        description=(
            "An endstop was triggered unexpectedly during movement. This can "
            "indicate a wiring issue or physical interference."
        ),
        fixes=[
            "Check the endstop wiring for shorts or loose connections",
            "Verify that nothing is physically pressing the endstop switch",
            "Check for EMI interference from stepper motor wires near endstop cables",
        ],
    ),
    # Serial / communication errors
    ErrorPattern(
        pattern=re.compile(r"Line Number is not Last Line Number", re.IGNORECASE),
        title="Line Number Desync",
        severity=ErrorSeverity.WARNING,
        category=ErrorCategory.SERIAL,
        description=(
            "The printer's expected command line number doesn't match what "
            "was sent. This indicates a communication desync between "
            "PrintForge and the printer firmware."
        ),
        fixes=[
            "This is usually recovered automatically via resend requests",
            "If persistent, check the USB cable for a secure connection",
            "Try a shorter or higher-quality USB cable",
            "Avoid using USB hubs — connect directly to the Pi",
        ],
    ),
    ErrorPattern(
        pattern=re.compile(r"checksum mismatch|Wrong checksum", re.IGNORECASE),
        title="Checksum Mismatch",
        severity=ErrorSeverity.WARNING,
        category=ErrorCategory.SERIAL,
        description=(
            "The command checksum didn't match what the printer expected. "
            "This usually indicates electrical noise on the USB connection."
        ),
        fixes=[
            "Use a shorter USB cable (under 1 meter ideal)",
            "Use a shielded/ferrite-core USB cable",
            "Ensure the USB cable is not running alongside power cables",
            "Avoid using USB hubs between the Pi and printer",
        ],
    ),
    ErrorPattern(
        pattern=re.compile(r"kill\(\)|Printer halted|KILLED", re.IGNORECASE),
        title="Printer Halted (Kill State)",
        severity=ErrorSeverity.CRITICAL,
        category=ErrorCategory.FIRMWARE,
        description=(
            "The printer firmware has entered a halted state and stopped all "
            "operations. This is typically triggered by a critical safety "
            "error that requires a full restart."
        ),
        fixes=[
            "Power cycle the printer to clear the kill state",
            "Check the printer's LCD screen for the specific error message",
            "Review the terminal log for errors that preceded the halt",
            "Send M999 to attempt a firmware reset without power cycling",
        ],
    ),
    ErrorPattern(
        pattern=re.compile(r"cold extrusion prevented", re.IGNORECASE),
        title="Cold Extrusion Prevented",
        severity=ErrorSeverity.WARNING,
        category=ErrorCategory.FIRMWARE,
        description=(
            "The firmware blocked an extrusion move because the hotend "
            "temperature is below the minimum extrusion temperature "
            "(typically 170°C). This is a safety feature."
        ),
        fixes=[
            "Heat the hotend to the correct temperature before extruding",
            "Wait for the nozzle to reach target temperature (check temp display)",
            "If you need to extrude at a lower temp (e.g., for cleaning), send M302 S0 to temporarily allow cold extrusion",
        ],
    ),
    ErrorPattern(
        pattern=re.compile(r"SD (card|init|read|write) (fail|error)", re.IGNORECASE),
        title="SD Card Error",
        severity=ErrorSeverity.WARNING,
        category=ErrorCategory.FIRMWARE,
        description=(
            "The printer's SD card reported an error. Note: PrintForge "
            "streams G-code over USB and does not use the SD card, so "
            "this error may be from the printer's own interface."
        ),
        fixes=[
            "This error does not affect USB printing via PrintForge",
            "If you need the SD card: remove, clean contacts, and reinsert",
            "Format the SD card as FAT32 if corruption is suspected",
        ],
    ),
]


# ── Timeout / Communication Patterns (generated programmatically) ──

TIMEOUT_PATTERN = ErrorPattern(
    pattern=re.compile(r"Timeout after [\d.]+s"),
    title="Command Timeout",
    severity=ErrorSeverity.WARNING,
    category=ErrorCategory.SERIAL,
    description=(
        "A command did not receive a response within the expected time. "
        "This can happen during long operations (heating, homing) or if "
        "communication is interrupted."
    ),
    fixes=[
        "Check the USB cable connection",
        "If this happened during heating, the timeout may simply be too short — the command may still succeed",
        "If persistent, try disconnecting and reconnecting to the printer",
        "Consider if the printer is busy with a long operation (bed leveling, homing)",
    ],
)

CONSECUTIVE_FAILURE_PATTERN = ErrorPattern(
    pattern=re.compile(r"consecutive command failures|communication lost", re.IGNORECASE),
    title="Communication Lost",
    severity=ErrorSeverity.CRITICAL,
    category=ErrorCategory.SERIAL,
    description=(
        "Multiple consecutive commands failed without a response. The USB "
        "serial connection to the printer may be physically disconnected "
        "or the printer may have frozen."
    ),
    fixes=[
        "Check the USB cable — it may have come loose",
        "Check if the printer is powered on and responsive",
        "The printer may need a power cycle if it's frozen",
        "After reconnecting, check print status — the print may need to be restarted",
    ],
)

KNOWN_ERRORS.extend([TIMEOUT_PATTERN, CONSECUTIVE_FAILURE_PATTERN])


class ErrorLog:
    """In-memory error log with pattern matching and catalog lookups."""

    MAX_ENTRIES = 200

    def __init__(self) -> None:
        self._entries: list[ErrorEntry] = []
        self._next_id: int = 1
        self._callbacks: list = []

    @property
    def entries(self) -> list[ErrorEntry]:
        return self._entries

    @property
    def active_entries(self) -> list[ErrorEntry]:
        return [e for e in self._entries if not e.dismissed]

    def add_callback(self, callback) -> None:
        """Register a callback for new error entries: callback(entry)."""
        self._callbacks.append(callback)

    def remove_callback(self, callback) -> None:
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def log_raw(self, raw_message: str) -> Optional[ErrorEntry]:
        """Try to match a raw error string against the catalog and log it."""
        for pattern in KNOWN_ERRORS:
            if pattern.pattern.search(raw_message):
                return self._add_entry(
                    severity=pattern.severity,
                    category=pattern.category,
                    title=pattern.title,
                    message=raw_message.strip(),
                    description=pattern.description,
                    fixes=pattern.fixes,
                    raw=raw_message.strip(),
                )

        # Unknown error — still log it with generic info
        return self._add_entry(
            severity=ErrorSeverity.WARNING,
            category=ErrorCategory.FIRMWARE,
            title="Printer Error",
            message=raw_message.strip(),
            description=(
                "The printer reported an error that isn't in the known error "
                "catalog. Check the raw message for details."
            ),
            fixes=[
                "Check the terminal log for more context",
                "Power cycle the printer if it's unresponsive",
                "Send M999 to attempt a firmware reset",
            ],
            raw=raw_message.strip(),
        )

    def log_safety_alert(
        self, message: str, level: str, action: str
    ) -> ErrorEntry:
        """Log a safety monitor alert."""
        severity = (
            ErrorSeverity.CRITICAL if level == "critical" else ErrorSeverity.WARNING
        )

        # Try to match against catalog for better descriptions
        for pattern in KNOWN_ERRORS:
            if pattern.pattern.search(message):
                return self._add_entry(
                    severity=severity,
                    category=ErrorCategory.SAFETY,
                    title=f"Safety: {pattern.title}",
                    message=message,
                    description=pattern.description,
                    fixes=pattern.fixes,
                    raw=message,
                )

        # Safety-specific descriptions based on action
        if action == "emergency_stop":
            description = (
                "The safety monitor triggered an emergency stop. The printer "
                "heaters and motors have been disabled to prevent damage."
            )
            fixes = [
                "Review the terminal log for what caused the safety trigger",
                "Check temperatures — ensure heaters and thermistors are working",
                "Power cycle the printer before attempting to print again",
            ]
        elif action == "pause_print":
            description = (
                "The safety monitor paused the print as a precaution. "
                "The printer should be checked before resuming."
            )
            fixes = [
                "Check the USB connection if a serial watchdog triggered",
                "Verify temperatures are reading correctly",
                "Resume the print once the issue is resolved, or cancel if needed",
            ]
        else:
            description = "The safety monitor generated an alert."
            fixes = ["Review the terminal log for details."]

        return self._add_entry(
            severity=severity,
            category=ErrorCategory.SAFETY,
            title="Safety Alert",
            message=message,
            description=description,
            fixes=fixes,
            raw=message,
        )

    def log_print_error(self, message: str) -> ErrorEntry:
        """Log a print-specific error."""
        # Try catalog match first
        for pattern in KNOWN_ERRORS:
            if pattern.pattern.search(message):
                return self._add_entry(
                    severity=pattern.severity,
                    category=ErrorCategory.PRINT,
                    title=pattern.title,
                    message=message,
                    description=pattern.description,
                    fixes=pattern.fixes,
                    raw=message,
                )

        return self._add_entry(
            severity=ErrorSeverity.ERROR,
            category=ErrorCategory.PRINT,
            title="Print Error",
            message=message,
            description="An error occurred during the print job.",
            fixes=[
                "Check the terminal log for the specific error",
                "Verify the G-code file is valid",
                "Ensure the printer is still connected and responsive",
            ],
            raw=message,
        )

    def log_system_error(self, title: str, message: str) -> ErrorEntry:
        """Log a system-level error (connection failures, etc.)."""
        return self._add_entry(
            severity=ErrorSeverity.ERROR,
            category=ErrorCategory.SYSTEM,
            title=title,
            message=message,
            description=message,
            fixes=[],
            raw=message,
        )

    def dismiss(self, entry_id: int) -> bool:
        """Dismiss an error entry by ID."""
        for entry in self._entries:
            if entry.id == entry_id:
                entry.dismissed = True
                return True
        return False

    def dismiss_all(self) -> int:
        """Dismiss all active errors. Returns count dismissed."""
        count = 0
        for entry in self._entries:
            if not entry.dismissed:
                entry.dismissed = True
                count += 1
        return count

    def clear(self) -> None:
        """Clear all error entries."""
        self._entries.clear()

    def _add_entry(
        self,
        severity: ErrorSeverity,
        category: ErrorCategory,
        title: str,
        message: str,
        description: str,
        fixes: list[str],
        raw: str = "",
    ) -> ErrorEntry:
        entry = ErrorEntry(
            id=self._next_id,
            severity=severity,
            category=category,
            title=title,
            message=message,
            description=description,
            fixes=fixes,
            timestamp=time.time(),
            raw=raw,
        )
        self._next_id += 1
        self._entries.append(entry)

        # Trim old entries
        if len(self._entries) > self.MAX_ENTRIES:
            self._entries = self._entries[-self.MAX_ENTRIES:]

        logger.info(
            "Error logged [%s/%s]: %s — %s",
            severity.value,
            category.value,
            title,
            message[:100],
        )

        # Notify callbacks
        for cb in self._callbacks:
            try:
                cb(entry)
            except Exception:
                logger.exception("Error in error_log callback")

        return entry

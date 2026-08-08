"""Shared safety guards for G-code commands reaching the serial wire.

These are pure functions (no I/O, no controller import) so they can be unit
tested in isolation and, more importantly, reused by BOTH the native printer
API and the OctoPrint-compat shim. Previously the during-print command guard and
the temperature ceiling lived only in ``api/printer.py``; the compat endpoint
(``/api/printer/command``) sent raw G-code with no guards at all, so a client
could home the printer or drive a heater past its limit mid-print by going
through the shim. Keeping the logic here makes the guards impossible to
bypass by choosing a different endpoint.
"""

from __future__ import annotations

import re
from typing import Optional

# Raw commands accepted from external clients while a print is active or
# paused. This is intentionally an allowlist: Marlin has many movement paths
# beyond G0/G1 (arcs, firmware retract, tool changes, stored macros, filament
# load/unload, etc.), so a denylist will inevitably miss a way to invalidate
# the sender's position/extrusion assumptions.
#
# Controller-owned print, pause, resume, cancel, and emergency-stop sequences
# enqueue or write their commands internally and do not pass through this
# external-command guard.
ALLOWED_DURING_PRINT = frozenset(
    {
        # Read-only status/reporting commands.
        "M27",   # SD print status
        "M31",   # Elapsed print time
        "M105",  # Temperatures
        "M114",  # Current position
        "M115",  # Firmware information
        "M119",  # Endstop states
        "M408",  # Machine status
        "M503",  # Current settings
        # Bounded print-time controls exposed by PrintForge's own UI.
        "M104",  # Set hotend temperature
        "M106",  # Set fan speed
        "M107",  # Fan off
        "M109",  # Set/wait for hotend temperature
        "M140",  # Set bed temperature
        "M155",  # Temperature auto-report interval
        "M190",  # Set/wait for bed temperature
        "M220",  # Feed-rate percentage
        "M221",  # Flow percentage
        # Display/host feedback and synchronization; none changes position.
        "M73",
        "M117",
        "M118",
        "M300",
        "M400",
    }
)

# Commands that set a heater target (the S/R parameter is a temperature in C).
_HOTEND_TEMP_COMMANDS = frozenset({"M104", "M109"})
_BED_TEMP_COMMANDS = frozenset({"M140", "M190"})
_TEMP_SET_COMMANDS = _HOTEND_TEMP_COMMANDS | _BED_TEMP_COMMANDS

# S = target (heat), R = target used by M109/M190's wait-including-cooling form.
# Both express the target temperature, so both must be checked against the cap.
_TEMP_PARAM_RE = re.compile(r"\b[SR](-?\d+(?:\.\d+)?)", re.IGNORECASE)


def command_base(command: str) -> str:
    """Return the upper-cased opcode of a G-code line (e.g. 'M104'), or ''."""
    stripped = command.strip()
    if not stripped:
        return ""
    return stripped.split()[0].upper()


def is_allowed_during_print(command: str) -> bool:
    """True if an external raw command is safe during an active/paused print.

    One call represents exactly one serial line. Reject embedded newlines even
    when the first opcode is allowed, otherwise ``M105\nG1 X0`` could smuggle a
    second command past the opcode check.
    """
    if "\r" in command or "\n" in command:
        return False
    return command_base(command) in ALLOWED_DURING_PRINT


def temperature_command_error(
    command: str, max_hotend: float, max_bed: float
) -> Optional[str]:
    """Validate a raw temperature-set command against the safety ceilings.

    Returns an error string if the command targets a heater above its limit,
    else None (not a temperature command, or within limits). Checks every S/R
    value so ``M109 R500`` is caught as well as ``M104 S500``.
    """
    base = command_base(command)
    if base not in _TEMP_SET_COMMANDS:
        return None
    if base in _HOTEND_TEMP_COMMANDS:
        ceiling, label = max_hotend, "Hotend"
    else:
        ceiling, label = max_bed, "Bed"
    for match in _TEMP_PARAM_RE.finditer(command):
        value = float(match.group(1))
        if value > ceiling:
            return (
                f"{label} target {value:.0f}C exceeds the safety limit of "
                f"{ceiling:.0f}C"
            )
    return None


def temperature_value_error(
    hotend: Optional[float],
    bed: Optional[float],
    max_hotend: float,
    max_bed: float,
) -> Optional[str]:
    """Validate structured hotend/bed targets against the safety ceilings.

    Returns an error string for the first target that exceeds its limit, else
    None. Used by the structured ``set_temperature`` path.
    """
    if hotend is not None and hotend > max_hotend:
        return (
            f"Hotend target {hotend:.0f}C exceeds the safety limit of "
            f"{max_hotend:.0f}C"
        )
    if bed is not None and bed > max_bed:
        return f"Bed target {bed:.0f}C exceeds the safety limit of {max_bed:.0f}C"
    return None

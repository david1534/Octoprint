"""Shared safety guards for G-code commands reaching the serial wire.

These are pure functions (no I/O, no controller import) so they can be unit
tested in isolation and, more importantly, reused by BOTH the native printer
API and the OctoPrint-compat shim. Previously the during-print block list and
the temperature ceiling lived only in ``api/printer.py``; the compat endpoint
(``/api/printer/command``) sent raw G-code with no guards at all, so a client
could home the printer or drive a heater past its limit mid-print by going
through the shim. Keeping the logic here makes the guards impossible to
bypass by choosing a different endpoint.
"""

from __future__ import annotations

import re
from typing import Optional

# Commands that corrupt an in-progress print if injected mid-stream: homing
# drives the toolhead across the part, G92 rewrites the coordinate origin,
# G90/G91 flip positioning mode, M84/M18 drop the steppers (lost position).
DANGEROUS_DURING_PRINT = frozenset({"G28", "G29", "G90", "G91", "G92", "M84", "M18"})

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


def is_dangerous_during_print(command: str) -> bool:
    """True if `command` must not be sent while a print is active/paused."""
    return command_base(command) in DANGEROUS_DURING_PRINT


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

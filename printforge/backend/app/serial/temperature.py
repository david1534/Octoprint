"""Temperature parsing and monitoring."""

import logging
import re
import time
from collections import deque
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

TEMP_REGEX = re.compile(r"T\d*:(?P<hotend_actual>[\d.]+)\s*/\s*(?P<hotend_target>[\d.]+)")
BED_REGEX = re.compile(r"B:(?P<bed_actual>[\d.]+)\s*/\s*(?P<bed_target>[\d.]+)")


@dataclass
class TemperatureReading:
    actual: float
    target: float
    timestamp: float


@dataclass
class TemperatureSnapshot:
    hotend: TemperatureReading
    bed: TemperatureReading


class TemperatureMonitor:
    """Parses temperature reports and maintains a history buffer."""

    def __init__(self, history_size: int = 300):
        self._history: deque[TemperatureSnapshot] = deque(maxlen=history_size)
        self._last_hotend = TemperatureReading(0.0, 0.0, 0.0)
        self._last_bed = TemperatureReading(0.0, 0.0, 0.0)

    @property
    def history(self) -> list[TemperatureSnapshot]:
        return list(self._history)

    @property
    def latest(self) -> Optional[TemperatureSnapshot]:
        if self._history:
            return self._history[-1]
        return None

    @property
    def hotend(self) -> TemperatureReading:
        return self._last_hotend

    @property
    def bed(self) -> TemperatureReading:
        return self._last_bed

    def parse_line(self, line: str) -> Optional[TemperatureSnapshot]:
        now = time.time()
        hotend_match = TEMP_REGEX.search(line)
        bed_match = BED_REGEX.search(line)
        if not hotend_match:
            return None
        hotend = TemperatureReading(
            actual=float(hotend_match.group("hotend_actual")),
            target=float(hotend_match.group("hotend_target")),
            timestamp=now,
        )
        self._last_hotend = hotend
        if bed_match:
            bed = TemperatureReading(
                actual=float(bed_match.group("bed_actual")),
                target=float(bed_match.group("bed_target")),
                timestamp=now,
            )
        else:
            bed = TemperatureReading(
                actual=self._last_bed.actual,
                target=self._last_bed.target,
                timestamp=now,
            )
        self._last_bed = bed
        snapshot = TemperatureSnapshot(hotend=hotend, bed=bed)
        self._history.append(snapshot)
        return snapshot

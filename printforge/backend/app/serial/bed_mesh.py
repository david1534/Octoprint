"""Bed mesh parser and storage.

Parses G29 / M420 V output from Marlin firmware to extract the auto
bed-leveling probe grid.  The parsed mesh is kept in memory so the
frontend can visualise the bed topography at any time.

Supported output formats
========================

Bilinear ABL (most common on Ender 3 with BLTouch)::

    Bilinear Leveling Grid:
          0      1      2      3      4
     0 +0.125 +0.087 +0.050 +0.012 -0.025
     1 +0.100 +0.062 +0.025 -0.012 -0.050
     ...

UBL (Unified Bed Leveling)::

    Bed Topography Report:
            0       1       2       3
     0  +0.120  +0.090  +0.050  +0.010
     ...

Manual Mesh Bed Leveling::

    Mesh Bed Leveling:
          0      1      2
     0 +0.050 +0.020 -0.010
     ...

The parser detects the header, then reads subsequent numeric rows until a
non-matching line (usually "ok") terminates the grid.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Patterns for mesh grid headers emitted by Marlin
_HEADER_PATTERNS = [
    re.compile(r"Bilinear Leveling Grid", re.IGNORECASE),
    re.compile(r"Bed Topography Report", re.IGNORECASE),
    re.compile(r"Mesh Bed Leveling", re.IGNORECASE),
    re.compile(r"Mesh Leveling", re.IGNORECASE),
]

# A mesh data row:  optional row index followed by signed floats
# e.g. " 0 +0.125 -0.050 +0.000  0.012"
_ROW_PATTERN = re.compile(r"^\s*\d+\s+([-+]?\d+\.\d+(?:\s+[-+]?\d+\.\d+)+)\s*$")

# Column index header line (just integers):  "  0   1   2   3   4"
_COL_HEADER = re.compile(r"^\s*(\d+\s+)+\d+\s*$")


@dataclass
class BedMesh:
    """Parsed bed mesh data."""

    grid: list[list[float]] = field(default_factory=list)
    rows: int = 0
    cols: int = 0
    min_z: float = 0.0
    max_z: float = 0.0
    mean_z: float = 0.0
    range_z: float = 0.0
    mesh_active: bool = False
    timestamp: float = 0.0

    def to_dict(self) -> dict:
        return {
            "grid": self.grid,
            "rows": self.rows,
            "cols": self.cols,
            "min": round(self.min_z, 4),
            "max": round(self.max_z, 4),
            "mean": round(self.mean_z, 4),
            "range": round(self.range_z, 4),
            "active": self.mesh_active,
            "timestamp": self.timestamp,
        }


class BedMeshParser:
    """Accumulates serial lines and detects / parses bed mesh output."""

    def __init__(self) -> None:
        self._collecting = False
        self._raw_rows: list[list[float]] = []
        self._mesh: Optional[BedMesh] = None

    @property
    def mesh(self) -> Optional[BedMesh]:
        return self._mesh

    def feed_line(self, line: str) -> Optional[BedMesh]:
        """Process a single serial line.

        Returns a ``BedMesh`` when a complete grid has been parsed,
        otherwise ``None``.
        """
        stripped = line.strip()

        # ── Detect mesh header ──
        if not self._collecting:
            for pat in _HEADER_PATTERNS:
                if pat.search(stripped):
                    logger.info("Bed mesh header detected: %s", stripped)
                    self._collecting = True
                    self._raw_rows = []
                    return None
            return None

        # ── Collecting rows ──

        # Skip column index header (e.g. "  0   1   2   3")
        if _COL_HEADER.match(stripped):
            return None

        # Try to match a data row
        m = _ROW_PATTERN.match(stripped)
        if m:
            values = [float(v) for v in m.group(1).split()]
            self._raw_rows.append(values)
            return None

        # Non-matching line terminates the grid
        self._collecting = False

        if not self._raw_rows:
            logger.warning("Mesh header found but no data rows followed")
            return None

        # Build BedMesh
        mesh = self._build_mesh(self._raw_rows)
        self._mesh = mesh
        self._raw_rows = []
        logger.info(
            "Bed mesh parsed: %dx%d grid, range %.4f mm (%.4f to %.4f)",
            mesh.rows,
            mesh.cols,
            mesh.range_z,
            mesh.min_z,
            mesh.max_z,
        )
        return mesh

    # ── Mesh status from M420 ──

    def parse_m420_status(self, line: str) -> Optional[bool]:
        """Detect mesh activation from M420 response.

        Marlin replies like::

            echo:Bed Leveling ON
            echo:Bed Leveling OFF

        Returns ``True`` / ``False`` if detected, else ``None``.
        """
        lower = line.lower()
        if "bed leveling on" in lower:
            if self._mesh:
                self._mesh.mesh_active = True
            return True
        if "bed leveling off" in lower:
            if self._mesh:
                self._mesh.mesh_active = False
            return False
        return None

    # ── Internal ──

    @staticmethod
    def _build_mesh(rows: list[list[float]]) -> BedMesh:
        flat = [v for row in rows for v in row]
        return BedMesh(
            grid=[list(row) for row in rows],
            rows=len(rows),
            cols=len(rows[0]) if rows else 0,
            min_z=min(flat),
            max_z=max(flat),
            mean_z=sum(flat) / len(flat),
            range_z=max(flat) - min(flat),
            mesh_active=True,  # G29 activates the mesh by default
            timestamp=time.time(),
        )

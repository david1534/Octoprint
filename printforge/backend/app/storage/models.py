"""Database models and queries for print history and settings."""

import asyncio
from datetime import datetime, timezone
from typing import Optional

from .database import get_db

# ── In-memory settings cache ──────────────────────────────────────
# Settings rarely change but are read frequently (every print start,
# safety loop, etc.). This cache eliminates redundant SQLite queries.
# Invalidated on every set_setting() call.
_settings_cache: dict[str, str] = {}
_settings_cache_loaded = False
_settings_lock = asyncio.Lock()


async def create_print_job(
    filename: str,
    total_lines: int,
    hotend_target: float = 0,
    bed_target: float = 0,
) -> int:
    """Record a new print job. Returns the job ID."""
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO print_jobs
           (filename, started_at, status, total_lines, hotend_target, bed_target)
           VALUES (?, ?, 'printing', ?, ?, ?)""",
        (
            filename,
            datetime.now(timezone.utc).isoformat(),
            total_lines,
            hotend_target,
            bed_target,
        ),
    )
    await db.commit()
    return cursor.lastrowid


async def complete_print_job(
    job_id: int,
    status: str,
    duration_seconds: int,
    lines_printed: int,
    filament_used_mm: float = 0,
) -> None:
    """Mark a print job as completed/cancelled/failed."""
    db = await get_db()
    await db.execute(
        """UPDATE print_jobs SET
           completed_at = ?, status = ?, duration_seconds = ?,
           lines_printed = ?, filament_used_mm = ?
           WHERE id = ?""",
        (
            datetime.now(timezone.utc).isoformat(),
            status,
            duration_seconds,
            lines_printed,
            filament_used_mm,
            job_id,
        ),
    )
    await db.commit()


async def get_print_history(limit: int = 50) -> list[dict]:
    """Get recent print history."""
    db = await get_db()
    cursor = await db.execute(
        """SELECT * FROM print_jobs ORDER BY started_at DESC LIMIT ?""",
        (limit,),
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def _ensure_settings_cache() -> None:
    """Load all settings into the in-memory cache if not already loaded.

    Uses an asyncio.Lock to prevent concurrent first-load races where
    a set_setting() could be silently reverted by a stale load.
    """
    global _settings_cache, _settings_cache_loaded
    if _settings_cache_loaded:
        return
    async with _settings_lock:
        # Double-check after acquiring lock
        if _settings_cache_loaded:
            return
        db = await get_db()
        cursor = await db.execute("SELECT key, value FROM settings")
        rows = await cursor.fetchall()
        _settings_cache = {row["key"]: row["value"] for row in rows}
        _settings_cache_loaded = True


async def get_setting(key: str, default: str = "") -> str:
    """Get a setting value (cached — avoids DB hit on repeated reads)."""
    await _ensure_settings_cache()
    return _settings_cache.get(key, default)


async def set_setting(key: str, value: str) -> None:
    """Set a setting value (writes through to DB and updates cache)."""
    global _settings_cache
    db = await get_db()
    await db.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (key, value),
    )
    await db.commit()
    # Update cache immediately
    _settings_cache[key] = value


async def get_all_settings() -> dict:
    """Get all settings as a dict (cached)."""
    await _ensure_settings_cache()
    return dict(_settings_cache)


# ── Filament spool management ──────────────────────────────────


async def create_spool(
    name: str,
    material: str = "PLA",
    color: str = "#CCCCCC",
    total_weight_g: float = 1000,
    cost_per_kg: float = 18,
    notes: str = "",
) -> int:
    """Create a new filament spool. Returns the spool ID."""
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO filament_spools
           (name, material, color, total_weight_g, cost_per_kg, notes)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (name, material, color, total_weight_g, cost_per_kg, notes),
    )
    await db.commit()
    return cursor.lastrowid


async def get_spools() -> list[dict]:
    """Get all filament spools."""
    db = await get_db()
    cursor = await db.execute("SELECT * FROM filament_spools ORDER BY active DESC, name ASC")
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_active_spool() -> Optional[dict]:
    """Get the currently active spool."""
    db = await get_db()
    cursor = await db.execute("SELECT * FROM filament_spools WHERE active = 1 LIMIT 1")
    row = await cursor.fetchone()
    return dict(row) if row else None


async def get_spool(spool_id: int) -> Optional[dict]:
    """Get a specific spool by ID."""
    db = await get_db()
    cursor = await db.execute("SELECT * FROM filament_spools WHERE id = ?", (spool_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


_SPOOL_COLUMNS = frozenset({
    "name", "material", "color", "total_weight_g", "used_weight_g",
    "cost_per_kg", "active", "notes", "density",
})


async def update_spool(spool_id: int, **kwargs) -> None:
    """Update spool fields (column names are whitelisted to prevent injection)."""
    if not kwargs:
        return
    for k in kwargs:
        if k not in _SPOOL_COLUMNS:
            raise ValueError(f"Invalid spool column: {k}")
    db = await get_db()
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [spool_id]
    await db.execute(f"UPDATE filament_spools SET {sets} WHERE id = ?", values)
    await db.commit()


async def set_active_spool(spool_id: int) -> None:
    """Set a spool as active (deactivates all others) atomically."""
    db = await get_db()
    await db.execute("BEGIN")
    try:
        await db.execute("UPDATE filament_spools SET active = 0")
        await db.execute("UPDATE filament_spools SET active = 1 WHERE id = ?", (spool_id,))
        await db.execute("COMMIT")
    except Exception:
        await db.execute("ROLLBACK")
        raise


async def deduct_filament(spool_id: int, grams: float) -> None:
    """Deduct filament usage from a spool."""
    db = await get_db()
    await db.execute(
        "UPDATE filament_spools SET used_weight_g = used_weight_g + ? WHERE id = ?",
        (grams, spool_id),
    )
    await db.commit()


async def delete_spool(spool_id: int) -> None:
    """Delete a filament spool."""
    db = await get_db()
    await db.execute("DELETE FROM filament_spools WHERE id = ?", (spool_id,))
    await db.commit()


# ── Print time correction factor ─────────────────────────────────


async def get_time_correction_factor() -> float:
    """Calculate average actual/estimated time ratio from completed prints.

    Returns 1.0 if there are fewer than 2 data points. Only considers
    completed prints where both estimated_seconds and duration_seconds are
    positive.
    """
    db = await get_db()
    cursor = await db.execute(
        """SELECT duration_seconds, estimated_seconds FROM print_jobs
           WHERE status = 'completed'
             AND estimated_seconds > 0
             AND duration_seconds > 0
           ORDER BY completed_at DESC
           LIMIT 20"""
    )
    rows = await cursor.fetchall()
    if len(rows) < 2:
        return 1.0
    ratios = [row["duration_seconds"] / row["estimated_seconds"] for row in rows]
    return sum(ratios) / len(ratios)


async def update_job_estimated_seconds(job_id: int, estimated_seconds: float) -> None:
    """Store the slicer's estimated time on a print job."""
    db = await get_db()
    await db.execute(
        "UPDATE print_jobs SET estimated_seconds = ? WHERE id = ?",
        (estimated_seconds, job_id),
    )
    await db.commit()

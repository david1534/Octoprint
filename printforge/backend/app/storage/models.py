"""Database models and queries for print history and settings."""

from datetime import datetime, timezone
from typing import Optional

from .database import get_db


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


async def get_setting(key: str, default: str = "") -> str:
    """Get a setting value."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT value FROM settings WHERE key = ?", (key,)
    )
    row = await cursor.fetchone()
    return row["value"] if row else default


async def set_setting(key: str, value: str) -> None:
    """Set a setting value."""
    db = await get_db()
    await db.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (key, value),
    )
    await db.commit()


async def get_all_settings() -> dict:
    """Get all settings as a dict."""
    db = await get_db()
    cursor = await db.execute("SELECT key, value FROM settings")
    rows = await cursor.fetchall()
    return {row["key"]: row["value"] for row in rows}

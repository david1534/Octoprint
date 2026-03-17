"""SQLite database management for print history and settings."""
from __future__ import annotations

import logging
from pathlib import Path

import os

import aiosqlite

logger = logging.getLogger(__name__)

_data_dir = os.environ.get("PRINTFORGE_DATA_DIR", os.path.expanduser("~/printforge/data"))
DB_PATH = Path(_data_dir) / "printforge.db"

_db: aiosqlite.Connection | None = None


async def init_db() -> None:
    """Initialize the database and create tables."""
    global _db
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    _db = await aiosqlite.connect(str(DB_PATH))
    _db.row_factory = aiosqlite.Row

    await _db.executescript("""
        CREATE TABLE IF NOT EXISTS print_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            status TEXT NOT NULL DEFAULT 'printing',
            duration_seconds INTEGER,
            lines_printed INTEGER,
            total_lines INTEGER,
            filament_used_mm REAL,
            hotend_target REAL,
            bed_target REAL
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS filament_spools (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            material TEXT NOT NULL DEFAULT 'PLA',
            color TEXT DEFAULT '#CCCCCC',
            total_weight_g REAL NOT NULL DEFAULT 1000,
            used_weight_g REAL NOT NULL DEFAULT 0,
            cost_per_kg REAL NOT NULL DEFAULT 18,
            active INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            notes TEXT DEFAULT ''
        );

        CREATE INDEX IF NOT EXISTS idx_print_jobs_started
            ON print_jobs(started_at DESC);
    """)

    # Add columns that may not exist in older databases
    for alter in [
        "ALTER TABLE print_jobs ADD COLUMN estimated_seconds REAL",
        "ALTER TABLE print_jobs ADD COLUMN spool_id INTEGER",
    ]:
        try:
            await _db.execute(alter)
        except Exception:
            pass  # Column already exists

    await _db.commit()
    logger.info("Database initialized at %s", DB_PATH)


async def close_db() -> None:
    global _db
    if _db:
        await _db.close()
        _db = None


async def get_db() -> aiosqlite.Connection:
    if _db is None:
        await init_db()
    return _db
